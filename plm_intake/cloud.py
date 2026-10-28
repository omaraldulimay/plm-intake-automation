"""Cloud-Betrieb (GitHub Actions): Inbox per Google Drive API holen, Zustand zwischen Laeufen sichern.

Inbox: env PLM_INBOX_MODE=drive_api -> Dateien aus dem Drive-Ordner PLM-Mails/Inbox (nur LESEN) in ein temporaeres Verzeichnis laden.
  Zugang: Service Account, JSON-Schluessel in env GOOGLE_SA_JSON (Inhalt der Datei, nicht der Pfad). Scope drive.readonly.
  Optional: PLM_DRIVE_ROOT_ID (Standard: Ordner PLM-Mails), PLM_DRIVE_INBOX_NAME (Standard: Inbox).
  Die Mail-Sammeldateien mails_*.txt braucht der Alltagslauf nicht (nur klaerfaelle.mail_dirs als optionale Fundort-Angabe) -> werden nicht geladen.
Zustand: liegt im Git-Zweig "einpflege-zustand" (Workflow holt/schreibt ihn); pull/push kopieren nur die erlaubten Dateien (STATE_FILES).
Keine Geheimnisse in Logs: nur Dateinamen.
"""
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVE = "https://www.googleapis.com/drive/v3"
DEFAULT_ROOT_ID = "REPLACE_WITH_GOOGLE_ID"   # Ordner PLM-Mails
FOLDER = "application/vnd.google-apps.folder"

# relativ zu output/ ; Zustand, der zwischen Laeufen erhalten bleiben muss (Merkbuch, Status, Aliase, Klaerfaelle, Heartbeat ...)
STATE_FILES = [
    "intake/ledger.json", "intake/status.json", "intake/STATUS.md", "intake/auto_report.md", "intake/alerts.log",
    "intake/po_aliases.json", "intake/vendor_aliases.json", "intake/style_aliases.json", "intake/overrides.json", "intake/event_overrides.json",
    "intake/klaerfaelle.json", "intake/last_run.json", "intake/lokaler_lauf_heartbeat.json",
    "phase2/lieferanten.json", "intake/techpack_daily.json", "intake/po_ids.json", "intake/tagesbericht.md", "intake/tagesbericht_verlauf.json", "intake/lieferanten_ids.json", "intake/klaerfaelle_erledigt.json", "intake/order_attachments_ledger.json", "intake/vendor_domains.json", "intake/mail_threads.json",
]


def inbox_mode():
    return os.environ.get("PLM_INBOX_MODE", "local").strip().lower()


def is_cloud_inbox():
    return inbox_mode() == "drive_api"


class DriveHTTP:
    """Duenne Huelle um google-auth + requests (zum Testen austauschbar). Nur GET."""

    def __init__(self, sa_json=None):
        raw = sa_json or os.environ.get("GOOGLE_SA_JSON")
        if not raw:
            raise RuntimeError("GOOGLE_SA_JSON fehlt (GitHub Secret mit dem JSON-Schluessel des Service Accounts)")
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        self.s = AuthorizedSession(creds)

    def get_json(self, url, params=None):
        for attempt in range(4):
            r = self.s.get(url, params=params, timeout=60)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt); continue
            if r.status_code != 200:
                raise RuntimeError("Drive-API %s -> HTTP %s: %s" % (url.split("/drive/v3")[-1], r.status_code, r.text[:200]))
            return r.json()

    def get_bytes(self, url, params=None):
        for attempt in range(4):
            r = self.s.get(url, params=params, timeout=120)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt); continue
            if r.status_code != 200:
                raise RuntimeError("Drive-Download -> HTTP %s" % r.status_code)
            return r.content


def _q(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def list_children(http, folder_id, extra=""):
    out, token = [], None
    while True:
        p = {"q": "'%s' in parents and trashed=false%s" % (folder_id, extra), "fields": "nextPageToken, files(id,name,mimeType,modifiedTime,size)",
             "pageSize": 1000, "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if token:
            p["pageToken"] = token
        d = http.get_json(DRIVE + "/files", p)
        out += d.get("files", [])
        token = d.get("nextPageToken")
        if not token:
            return out


def find_inbox_id(http, root_id=None, name=None):
    root_id = root_id or os.environ.get("PLM_DRIVE_ROOT_ID") or DEFAULT_ROOT_ID
    name = name or os.environ.get("PLM_DRIVE_INBOX_NAME") or "Inbox"
    hits = [f for f in list_children(http, root_id, " and name='%s' and mimeType='%s'" % (_q(name), FOLDER))]
    if not hits:
        raise RuntimeError("Drive: Unterordner '%s' im Ordner PLM-Mails nicht gefunden (Ordner fuer die Service-Account-Mail freigegeben?)" % name)
    return hits[0]["id"]


def download_inbox(dest=None, http=None):
    """Laedt alle *.json aus PLM-Mails/Inbox nach dest (Standard: neues Temp-Verzeichnis). Rueckgabe: Path. Datei-mtime = Drive-modifiedTime (fuer die Alterspruefung)."""
    http = http or DriveHTTP()
    dest = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="plm_inbox_"))
    dest.mkdir(parents=True, exist_ok=True)
    files = [f for f in list_children(http, find_inbox_id(http)) if f["name"].endswith(".json") and f.get("mimeType") != FOLDER]
    for f in files:
        data = http.get_bytes("%s/files/%s" % (DRIVE, f["id"]), {"alt": "media", "supportsAllDrives": "true"})
        p = dest / Path(f["name"]).name   # nie aus dem Zielordner ausbrechen
        p.write_bytes(data)
        try:
            t = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00")).timestamp()
            os.utime(p, (t, t))
        except (KeyError, ValueError):
            pass
    print("Drive-Inbox: %d Dateien nach %s geladen" % (len(files), dest), file=sys.stderr)
    return dest


_cached = {}


def inbox_dir():
    """Einmal je Prozess laden (resolve_inbox wird mehrfach aufgerufen)."""
    if "d" not in _cached:
        _cached["d"] = download_inbox()
    return _cached["d"]


def pull_state(state_dir, out_dir=None):
    """Zustand aus dem Zustandsordner (Git-Zweig-Checkout) nach output/ kopieren. Rueckgabe: Anzahl Dateien."""
    out_dir = Path(out_dir) if out_dir else ROOT / "output"
    n = 0
    for rel in STATE_FILES:
        src = Path(state_dir) / rel
        if src.is_file():
            (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_dir / rel); n += 1
    return n


def push_state(state_dir, out_dir=None):
    """Zustand von output/ in den Zustandsordner kopieren (+ Berichte/Protokolle der letzten Laeufe). Rueckgabe: Anzahl Dateien."""
    out_dir = Path(out_dir) if out_dir else ROOT / "output"
    n = 0
    for rel in STATE_FILES:
        src = out_dir / rel
        if src.is_file():
            (Path(state_dir) / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, Path(state_dir) / rel); n += 1
    logs = out_dir / "intake" / "logs"
    if logs.is_dir():
        dst = Path(state_dir) / "intake" / "logs"
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(logs.glob("report_*.md"))[-1:]:   # nur der letzte Bericht, sonst waechst das Repo
            shutil.copy2(f, dst / f.name); n += 1
        for old in sorted(dst.glob("report_*.md"))[:-20]:
            old.unlink()
    return n


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] in ("pull", "push"):
        print({"pull": pull_state, "push": push_state}[a[0]](a[1]), "Dateien")
    else:
        print("Aufruf: python3 -m plm_intake.cloud pull|push <Zustandsordner>"); sys.exit(2)
