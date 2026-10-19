"""Anhaenge als echte Datei (Lifecycle-MCP attach_file entityType=product|order|shipment, id, url, fileName) -- nur fuer OEFFENTLICH erreichbare Dateien.

  python3 -m plm_intake.attachments_p2     TROCKENLAUF: prueft je Techpack-Link (output/phase2/B10/techpack_links_plan.json), ob die Datei ohne Anmeldung abrufbar ist
                                           (Drive-Links: nein -> 'Freigabe noetig'), und ob der Name schon als Anhang existiert; Bericht output/phase2/attachments_p2.md

Drive-Dateien werden NIE freigegeben/geteilt (Techpacks nie). Schreiben selbst nur per MCP attach_file durch Claude, wenn public=True und kein Namens-Duplikat."""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "phase2"
ENDPOINT = {"product": "products", "order": "orders", "shipment": "shipments"}
FILE_TYPES = ("application/pdf", "application/octet-stream", "application/vnd", "image/", "application/zip")


def is_public(url, fetch=None):
    """True nur, wenn die URL OHNE Anmeldung eine Datei liefert (HTTP 200 und kein HTML/Anmeldeseite)."""
    if fetch is None:
        def fetch(u):
            r = subprocess.run(["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}|%{content_type}|%{url_effective}", "--max-time", "20", u], capture_output=True, text=True)
            code, ctype, final = (r.stdout.split("|") + ["", "", ""])[:3]
            return int(code or 0), ctype, final
    code, ctype, final = fetch(url)
    return code == 200 and "accounts.google.com" not in final and str(ctype).lower().startswith(FILE_TYPES)


def has_attachment(existing, name):
    """Dublettenpruefung ueber den Dateinamen (GET <entity>/<id>/attachments), ohne Gross/Klein und Endung-Unterschiede."""
    n = lambda s: str(s or "").lower().rsplit(".", 1)[0].strip()
    return any(n(a.get("name")) == n(name) for a in existing or [])


def attachment_status(entity, eid, name, url, call, fetch=None):
    """-> 'duplikat' | 'nicht oeffentlich (Freigabe noetig)' | 'bereit' (-> attach_file entityType=entity id=eid url=url fileName=name)."""
    st, existing = call("GET", "%s/%s/attachments" % (ENDPOINT[entity], eid))
    if st == 200 and has_attachment(existing, name):
        return "duplikat"
    return "bereit" if is_public(url, fetch) else "nicht oeffentlich (Freigabe noetig)"


def main():
    import collections
    import plm_client
    todo = json.load(open(OUT / "B10" / "techpack_links_plan.json"))["todo"]
    cnt = collections.Counter(); rep = ["# Anhaenge als Datei (TROCKENLAUF)", "", "Stand %s, %d Techpack/Spec-Dateien" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), len(todo)), ""]
    for r in todo:
        s = attachment_status("product", r["productId"], r["name"], "https://drive.google.com/uc?export=download&id=" + r["driveId"], plm_client.call)
        cnt[s] += 1; rep.append("- %s %s: %s" % (r["sku"], r["name"], s))
    rep.append(""); rep.append("Summe: %s" % dict(cnt))
    f = OUT / "attachments_p2.md"; f.write_text("\n".join(rep)); print(rep[-1]); print(f)


if __name__ == "__main__":
    main()
