"""Falsch zugeordnete Ereignis-Zeilen (Marker ev:xxxxxxxx) aus der Notiz einer Order entfernen (Muster der Korrektur PLM #85 am 23.10.).

  .venv/bin/python -m plm_intake.notiz_marker_entfernen --order <id> --marker af070f19 --marker 8e70253e [--backup output/backup/notes_X.txt] [--apply]

Dry-Run Standard (liest nur, zeigt die zu entfernenden Zeilen). --apply: (1) vollstaendige Notiz VORHER in die Backup-Datei, (2) __updOrder nur mit notes,
(3) Zuruecklesen: uebrige Notiz = Notiz ohne die Marker-Zeilen, Positionen/Menge/Summe/Zahlungen unveraendert. Entfernt nur ganze Zeilen mit 'ev:<marker>]'.
Chat-Kommentare (Chats & Updates) fasst das Skript NICHT an (keine Einzel-Loeschung moeglich; ganze Threads nur von Hand/nach Pruefung)."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

READ_JS = """(async()=>{const r=await window.__fetchOrder(%s);const d=r.d;
 return {notes:d.notes||'',core:JSON.stringify({t:d.title,c:d.currency,tc:d.totalCost,tp:d.totalNumberOfPieces,m:d.manufacturer&&d.manufacturer.id,items:d.items,pay:d.payments,st:d.status&&d.status.status},(k,v)=>k==='__typename'?undefined:v)};})()"""
WRITE_JS = """(async()=>{const id=%s,notes=%s;const a=await window.__fetchOrder(id);const before=JSON.stringify({tc:a.d.totalCost,tp:a.d.totalNumberOfPieces,items:a.d.items,pay:a.d.payments},(k,v)=>k==='__typename'?undefined:v);
 const r=await window.__updOrder(id,{notes});if(r.err&&(Array.isArray(r.err)?r.err.length:r.err))return {error:r.err};
 const b=await window.__fetchOrder(id);const after=JSON.stringify({tc:b.d.totalCost,tp:b.d.totalNumberOfPieces,items:b.d.items,pay:b.d.payments},(k,v)=>k==='__typename'?undefined:v);
 return {notes:b.d.notes||'',dataUnchanged:before===after};})()"""


def strip_lines(notes, markers):
    """-> (neue Notiz, entfernte Zeilen). Nur Zeilen, die 'ev:<marker>]' enthalten."""
    rx = re.compile(r"ev:(%s)\]" % "|".join(re.escape(m) for m in markers))
    keep, gone = [], []
    for ln in notes.split("\n"):
        (gone if rx.search(ln) else keep).append(ln)
    return "\n".join(keep).rstrip("\n"), gone


def _run(js, name, runner=None):
    from plm_intake.auto_run import browser
    runner = runner or browser
    p = ROOT / "output" / "intake" / name
    p.write_text(js)
    for i in range(8):   # Profil-Lock: Start scheitert vor jedem Schreiben
        try:
            return runner(p)
        except SystemExit as e:
            if "rocessSingleton" not in str(e) or i == 7:
                raise
            time.sleep(20)


def main(argv=None, runner=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True); ap.add_argument("--marker", action="append", required=True)
    ap.add_argument("--backup"); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    cur = _run(READ_JS % json.dumps(a.order), "notiz_lesen.js", runner)
    new, gone = strip_lines(cur["notes"], a.marker)
    print("zu entfernen: %d Zeilen" % len(gone)); [print("  -", g[:160]) for g in gone]
    if not a.apply:
        print("Dry-Run, nichts geschrieben"); return 0
    if not gone:
        print("nichts zu tun"); return 0
    if not a.backup:
        raise SystemExit("--backup fehlt")
    Path(a.backup).write_text(cur["notes"])   # vollstaendige Notiz VORHER
    res = _run(WRITE_JS % (json.dumps(a.order), json.dumps(new)), "notiz_schreiben.js", runner)
    print(json.dumps({k: (v if k != "notes" else "...") for k, v in res.items()}, ensure_ascii=False))
    ok = res.get("notes") == new and res.get("dataUnchanged") is True and not any(m in res.get("notes", "") for m in ["ev:%s]" % m for m in a.marker])
    print("Zuruecklesen:", "OK" if ok else "ABWEICHUNG")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
