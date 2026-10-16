"""Einpflege-Lauf: Inbox (ausgelesene PO-JSONs) -> Pruefung -> ready/ (anlegen) oder blocked/ (Mensch schaut) + Bericht + Browser-Skript.

  python3 -m plm_intake.run                      # live Kontext aus dem PLM (nur lesen), schreibt ready/blocked/report
  python3 -m plm_intake.run --ctx snapshot.json  # offline mit gespeichertem Kontext
Danach: output/intake/run_<zeit>.js im Chrome-Tab (nach chrome_order_helpers.js) per javascript_tool ausfuehren,
dann: python3 -m plm_intake.verify
"""
import argparse
import copy
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

INTAKE = ROOT / "output" / "intake"


def process(inbox_files, ctx, today=None, force=()):
    """Reine Funktion: Liste (name, po) -> Liste Ergebnisse. Innerhalb des Laufs gelten schon angelegte POs als vorhanden."""
    ctx = copy.deepcopy(ctx)
    results = []
    for name, po in inbox_files:
        try:
            r = core.build(po, ctx, today, force_create=name in force)
        except Exception as e:  # kaputte Eingabe darf den Lauf nicht stoppen
            r = core.Result(decision="BLOCK", issues=[core.Issue("ERROR", "exception", "%s: %s" % (type(e).__name__, e))])
        if r.decision == "CREATE":
            ctx["orders"].append({"id": "pending:" + name, "orderNumber": "neu", "title": r.payload["title"], "poNumber": r.payload["poNumber"],
                                  "manufacturer": {"id": r.payload["manufacturer"]}, "totalCost": r.payload["totalCost"],
                                  "totalNumberOfPieces": r.payload["totalNumberOfPieces"]})
        results.append((name, r))
    return results


def render_report(results):
    lines = ["# Einpflege-Bericht %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "",
             "| Datei | Entscheidung | Titel | Stk | Summe | Hinweise |", "|---|---|---|---|---|---|"]
    for name, r in results:
        p = r.payload or {}
        hints = "; ".join("%s %s" % (i.level, i.msg) for i in r.issues if i.level in ("ERROR", "WARN"))
        lines.append("| %s | **%s** | %s | %s | %s | %s |" % (name, r.decision, p.get("title", "-"), p.get("totalNumberOfPieces", "-"), p.get("totalCost", "-"), hints.replace("|", "/")))
    n = {d: sum(1 for _, r in results if r.decision == d) for d in ("CREATE", "UPDATE", "SKIP", "BLOCK")}
    lines += ["", "Zusammenfassung: " + ", ".join("%s %d" % (k, v) for k, v in n.items())]
    return "\n".join(lines) + "\n"


def make_js(payloads, dry=False):
    tpl = (Path(__file__).parent / "runner_template.js").read_text()
    return tpl.replace("__PAYLOADS__", json.dumps(payloads, ensure_ascii=False, separators=(",", ":"))).replace("__DRY__", "true" if dry else "false")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=str(INTAKE / "inbox"))
    ap.add_argument("--ctx", help="Kontext-JSON statt Live-Abfrage")
    ap.add_argument("--dry", action="store_true", help="Browser-Skript nur als Trockenlauf erzeugen")
    a = ap.parse_args(argv)
    files = sorted(f for f in Path(a.inbox).glob("*.json") if not f.name.endswith("_events.json"))   # Ereignisse: plm_intake.events_run
    if not files:
        print("Inbox leer:", a.inbox)
        return 0
    if a.ctx:
        ctx = json.load(open(a.ctx))
    else:
        from plm_intake.context import load_context
        ctx = load_context()
    alias_file = INTAKE / "vendor_aliases.json"
    ctx["aliases"] = json.load(open(alias_file)) if alias_file.exists() else {}
    inbox = []
    for f in files:
        try:
            inbox.append((f.name, json.load(open(f))))
        except ValueError as e:
            inbox.append((f.name, {"_unreadable": str(e)}))
    results = process(inbox, ctx)
    for d in ("ready", "blocked"):
        (INTAKE / d).mkdir(parents=True, exist_ok=True)
    payloads = []
    for name, r in results:
        stem = Path(name).stem
        for d in ("ready", "blocked"):
            (INTAKE / d / (stem + ".json")).unlink(missing_ok=True)
        if r.decision == "CREATE":
            json.dump(r.payload, open(INTAKE / "ready" / (stem + ".json"), "w"), ensure_ascii=False, indent=1)
            payloads.append(r.payload)
        else:
            json.dump({"decision": r.decision, "existing_id": r.existing_id, "issues": [vars(i) for i in r.issues], "payload": r.payload},
                      open(INTAKE / "blocked" / (stem + ".json"), "w"), ensure_ascii=False, indent=1)
    rep = render_report(results)
    (INTAKE / "report.md").write_text(rep)
    if payloads:
        js = INTAKE / ("run_%s.js" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        js.write_text(make_js(payloads, a.dry))
        print("Browser-Skript:", js)
    print(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
