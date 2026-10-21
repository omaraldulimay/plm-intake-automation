"""Taeglicher Abschnitt "Techpacks": NEUE Techpack-/Spec-Anhaenge aus Lieferanten-Mails als echte Datei ans passende PLM-Produkt haengen.

Quelle der Anhaenge: lokal Drive-Desktop-Ordner PLM-Mails/Anhaenge, in der Cloud (PLM_INBOX_MODE=drive_api) die Drive-API (nur lesen, Dienstkonto).
Neu = Aenderungszeit/modifiedTime nach dem Merker "since" in <intake>/techpack_daily.json (wird mit gesichert, siehe cloud.STATE_FILES).
Erstlauf ohne Merker: Merker auf jetzt setzen, KEIN Nachholen (den Rueckstand erledigt techpack_upload).
Zuordnung: techpack_map.resolve; vorhandene echte Datei gleichen Namens am Produkt -> uebersprungen. Nie loeschen. Max. 30 Uploads je Lauf, max. 20 MB je Datei.
Trockenlauf (apply=False) laedt nichts hoch und schreibt keinen Merker."""
import base64
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from plm_intake import techpack_map as tm

ROOT = Path(__file__).resolve().parents[1]
STATE_NAME = "techpack_daily.json"
MAX_UPLOADS = 30
MAXB = 20 * 1024 * 1024
EXTS = (".pdf", ".xlsx", ".xls", ".xlsm", ".docx")
ATT_RX = re.compile(r"^\d{4}-\d{2}-\d{2}_[0-9a-f]{16}_(.+)$")
DONE_KEEP = 500


def display_name(datei):
    m = ATT_RX.match(datei)
    return m.group(1) if m else datei


def is_techpack_name(datei):
    """Dateiname = Techpack/Spec (Regeln aus phase2_sources.typ_of) und ein Dokumentformat, das Lifecycle als Datei nimmt."""
    from plm_intake.phase2_sources import typ_of
    n = display_name(datei)
    return n.lower().endswith(EXTS) and typ_of(n) in ("TP", "Spec")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state(path):
    try:
        d = json.loads(Path(path).read_text())
        return {"since": d.get("since"), "done": list(d.get("done") or [])}
    except (OSError, ValueError):
        return {"since": None, "done": []}


def save_state(path, st):
    st = dict(st); st["done"] = st["done"][-DONE_KEEP:]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(st, indent=1))


def _ts(iso):
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()


# ---- Quellen: je Eintrag {"name","mtime"(ISO),"size","get"()->bytes} ----
def local_source(folder=None):
    from plm_intake.techpack_links import ANH
    folder = Path(folder or ANH)
    out = []
    for p in folder.iterdir() if folder.is_dir() else []:
        try:
            s = p.stat()
        except OSError:
            continue
        out.append({"name": p.name, "mtime": datetime.fromtimestamp(s.st_mtime, timezone.utc).isoformat(), "size": s.st_size, "get": p.read_bytes, "path": p})
    return out


def drive_source(http=None, since=None):
    """Drive-API: Ordner PLM-Mails/Anhaenge, nur Dateien mit modifiedTime > since (serverseitig gefiltert)."""
    from plm_intake import cloud
    http = http or cloud.DriveHTTP()
    root = os.environ.get("PLM_DRIVE_ROOT_ID") or cloud.DEFAULT_ROOT_ID
    hits = cloud.list_children(http, root, " and name='Anhaenge' and mimeType='%s'" % cloud.FOLDER)
    if not hits:
        raise RuntimeError("Drive: Unterordner 'Anhaenge' im Ordner PLM-Mails nicht gefunden")
    extra = " and mimeType!='%s'" % cloud.FOLDER + (" and modifiedTime > '%s'" % since if since else "")
    out = []
    for f in cloud.list_children(http, hits[0]["id"], extra):
        out.append({"name": f["name"], "mtime": f.get("modifiedTime") or "", "size": int(f.get("size") or 0),
                    "get": (lambda i=f["id"]: http.get_bytes("%s/files/%s" % (cloud.DRIVE, i), {"alt": "media", "supportsAllDrives": "true"}))})
    return out


def default_source(since=None):
    from plm_intake import cloud
    return drive_source(since=since) if cloud.is_cloud_inbox() else local_source()


def find_new(files, state):
    """Neue Techpack/Spec-Dateien: Aenderungszeit nach Merker, noch nicht in 'done'. Aelteste zuerst."""
    since = state.get("since")
    if not since:
        return []
    done = set(state.get("done") or [])
    new = [f for f in files if f["name"] not in done and f.get("mtime") and _ts(f["mtime"]) > _ts(since) and is_techpack_name(f["name"])]
    return sorted(new, key=lambda f: (f["mtime"], f["name"]))


def has_real_file(atts, name):
    """Echte Datei (kein Drive-Link) gleichen Namens am Produkt? Vergleich ohne Endung wie techpack_upload."""
    from plm_intake.techpack_upload import real
    base = os.path.splitext(name)[0].lower()
    return any(real(a) and (a.get("name") or "").lower() == base for a in atts or [])


def read_existing(pids, bc=None):
    from plm_intake import barcodes
    from plm_intake.techpack_upload import READ_JS
    return (bc or barcodes).run_js(READ_JS.replace("__PIDS__", json.dumps(sorted(pids))))


def upload_one(product_id, name, data, bc=None):
    """Eine Datei per upload_helpers.js hochladen (gleicher Weg wie techpack_upload). -> (ok, Fehlertext)."""
    from plm_intake import barcodes
    from plm_intake.techpack_links import MIME
    from plm_intake.techpack_upload import HELP
    ext = os.path.splitext(name)[1].lower()
    js = "(async()=>{" + HELP.read_text() + "\nreturn await window.__uploadProductFile(%s,%s,%s,'%s');})()" % (
        json.dumps(product_id), json.dumps(name), json.dumps(MIME.get(ext, "application/octet-stream")), base64.b64encode(data).decode())
    r = (bc or barcodes).run_js(js)
    return (True, "") if isinstance(r, dict) and r.get("ok") else (False, str(r)[:150])


def run(products, state_path, apply=False, source=None, reader=None, uploader=None, aliases=None, text_of=None):
    """-> (Berichtszeilen, Ergebnis-Dict). source: Funktion(since)->Dateiliste; reader(pids)->{pid:[attachments]}; uploader(pid,name,bytes)->(ok,err)."""
    reader = reader or read_existing
    uploader = uploader or upload_one
    text_of = text_of or tm.file_text
    st = load_state(state_path)
    start = now_iso()
    res = {"neu": 0, "hochgeladen": 0, "vorhanden": 0, "ohne_produkt": [], "fehler": [], "rest": 0}
    if not st["since"]:
        if apply:
            st["since"] = start; save_state(state_path, st)
        return ["- Erstlauf: Merker %s, kein Nachholen (Rueckstand macht techpack_upload)" % ("auf jetzt gesetzt" if apply else "wird im Echtlauf gesetzt (Trockenlauf)")], res
    files = (source or default_source)(st["since"])
    new = find_new(files, st)
    res["neu"] = len(new)
    al = aliases if aliases is not None else tm.load_aliases()
    jobs, processed = [], []   # processed = Dateien, die abschliessend behandelt sind (zugeordnet+erledigt/uebersprungen oder unzuordenbar gemeldet)
    for f in new:
        name = display_name(f["name"])
        if f["size"] > MAXB:
            res["fehler"].append("%s: groesser als 20 MB" % name); processed.append(f["name"]); continue
        try:
            data = f["get"]()
        except Exception as e:
            res["fehler"].append("%s: Download %s" % (name, str(e)[:100])); continue   # nicht als erledigt merken
        r = tm.resolve(name, products, al)
        if not r[0]:
            with tempfile.TemporaryDirectory() as td:
                tp = Path(td) / name
                tp.write_bytes(data)
                r = tm.resolve(name, products, al, text_of(tp))
        if not r[0]:
            res["ohne_produkt"].append("%s (%s)" % (name, r[2])); processed.append(f["name"]); continue
        jobs.append({"f": f, "name": name, "data": data, "prods": r[0], "methode": r[1]})
    seen, uniq = set(), []   # gleicher Name mehrfach (mehrere Mails): nur die neueste Fassung, aeltere gelten als erledigt
    for j in reversed(jobs):
        left = [p for p in j["prods"] if (p["id"], j["name"].lower()) not in seen]
        seen |= {(p["id"], j["name"].lower()) for p in j["prods"]}
        if left:
            j["prods"] = left; uniq.append(j)
        else:
            processed.append(j["f"]["name"])
    jobs = list(reversed(uniq))
    ex = reader({p["id"] for j in jobs for p in j["prods"]}) if jobs else {}
    todo, lines = [], []
    for j in jobs:
        left = [p for p in j["prods"] if ex.get(p["id"]) is not None and not has_real_file(ex[p["id"]], j["name"])]
        if not left:
            res["vorhanden"] += 1; processed.append(j["f"]["name"]); continue
        todo.append((j, left))
    budget = MAX_UPLOADS
    for j, left in todo:
        if len(left) > budget:
            res["rest"] += 1; continue   # bleibt fuer den naechsten Lauf (nicht in processed)
        ok_all = True
        for p in left:
            budget -= 1
            if not apply:
                lines.append("- wuerde hochladen: %s -> %s (%s)" % (j["name"][:70], p["sku"], j["methode"])); continue
            ok, err = uploader(p["id"], j["name"], j["data"])
            if ok:
                res["hochgeladen"] += 1; lines.append("- hochgeladen: %s -> %s (%s)" % (j["name"][:70], p["sku"], j["methode"]))
            else:
                ok_all = False; res["fehler"].append("%s -> %s: %s" % (j["name"][:60], p["sku"], err))
        if apply and ok_all:
            processed.append(j["f"]["name"])
    if apply and res["hochgeladen"]:   # Rueckpruefung
        pids = {p["id"] for j, left in todo for p in left}
        after = reader(pids)
        miss = [j["name"] for j, left in todo for p in left if not has_real_file(after.get(p["id"]) or [], j["name"])]
        res["fehlt_nach_upload"] = miss
        lines.append("- Rueckpruefung: %s" % ("alle als Datei am Produkt" if not miss else "FEHLEN %d: %s" % (len(miss), miss[:5])))
    if apply:
        st["done"] += processed
        if res["rest"] == 0 and not res["fehler"]:
            st["since"] = start
        save_state(state_path, st)
    head = ["- neue Techpack/Spec-Dateien seit %s: %d | hochgeladen %d | schon als Datei vorhanden %d | ohne Produkt %d | Limit-Rest %d" % (
        st["since"][:16] if not apply else (load_state(state_path)["since"] or "")[:16], res["neu"], res["hochgeladen"], res["vorhanden"], len(res["ohne_produkt"]), res["rest"])]
    out = head + lines + (["- Fehler: " + x for x in res["fehler"]])
    if res["ohne_produkt"]:
        out += ["", "### Techpacks ohne Produkt"] + ["- " + x for x in res["ohne_produkt"]]
    return out, res
