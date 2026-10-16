"""Ereignis-Lauf: Inbox/*_events.json -> Zuordnung zu Orders -> Bericht + Browser-Skript (Notes/Termine/Zahlungsstatus).
  python3 -m plm_intake.events_run [--inbox DIR] [--ctx snapshot.json] [--out DIR]
Danach: output/intake/events_<zeit>.js im Chrome-Tab (nach chrome_order_helpers.js) per javascript_tool ausfuehren."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import events  # noqa: E402

INTAKE = ROOT / "output" / "intake"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=str(INTAKE / "inbox"))
    ap.add_argument("--ctx")
    ap.add_argument("--out", default=str(INTAKE))
    a = ap.parse_args(argv)
    files = sorted(Path(a.inbox).glob("*_events.json"))
    if not files:
        print("Keine Ereignis-Dateien in", a.inbox)
        return 0
    if a.ctx:
        ctx = json.load(open(a.ctx))
    else:
        from plm_intake.context import load_context
        ctx = load_context()
    alias_file = Path(a.out) / "po_aliases.json"
    aliases = json.load(open(alias_file)) if alias_file.exists() else {}
    evs = events.load_events(files)
    pl = events.plan(evs, ctx["orders"], ctx["vendors"], aliases)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = events.report(pl)
    (out / "events_report.md").write_text(rep)
    if pl["orders"]:
        js = out / ("events_%s.js" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        js.write_text(events.make_js(pl))
        print("Browser-Skript:", js)
    print(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
