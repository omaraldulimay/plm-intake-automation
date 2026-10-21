"""Taeglicher Lauf: liest die Inbox (lokaler Pfad, z. B. der mit Google Drive fuer Desktop gespiegelte Ordner PLM-Mails/Inbox),
bewertet NEUE Dateien (Merkbuch), erzeugt Bericht + Browser-Skripte. Schreibt NICHTS ins PLM.

  python3 -m plm_intake.daily                      # Pfad aus output/intake/config.json {"inbox": "..."} oder --inbox
  python3 -m plm_intake.daily --commit             # nach erfolgreichem Browser-Lauf + verify: Dateien als erledigt merken

Ablauf: daily -> Browser-Skripte (run_*.js, events_*.js) im PLM-Tab -> python3 -m plm_intake.verify -> daily --commit
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core, events, ledger, run  # noqa: E402

INTAKE = ROOT / "output" / "intake"


def resolve_inbox(arg, intake=INTAKE):
    if arg:
        return Path(arg).expanduser()
    from plm_intake import cloud
    if cloud.is_cloud_inbox():   # PLM_INBOX_MODE=drive_api: Dateien per Drive-API in ein Temp-Verzeichnis (einmal je Prozess); lokaler Modus bleibt Standard
        return cloud.inbox_dir()
    cfg = intake / "config.json"
    if cfg.exists():
        v = json.load(open(cfg)).get("inbox")
        if v:
            return Path(v).expanduser()
    return intake / "inbox"


def pending(inbox, led):
    files = sorted(Path(inbox).glob("*.json"))
    docs = [f for f in files if not f.name.endswith("_events.json") and not ledger.is_done(led, f)]
    evs = [f for f in files if f.name.endswith("_events.json") and not ledger.is_done(led, f)]
    return docs, evs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox")
    ap.add_argument("--ctx", help="Kontext-JSON statt Live-Abfrage (Tests)")
    ap.add_argument("--intake", default=str(INTAKE), help="Arbeitsordner (Tests)")
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args(argv)
    intake = Path(a.intake)
    led_path = intake / "ledger.json"
    led = ledger.load(led_path)
    inbox = resolve_inbox(a.inbox, intake)
    if not inbox.exists():
        print("Inbox nicht gefunden:", inbox)
        return 2
    docs, evs = pending(inbox, led)

    if a.commit:   # erledigt merken: Dateien, deren Order laut ready/ angelegt ist, und Ereignisdateien des letzten Laufs
        state = json.load(open(intake / "last_run.json")) if (intake / "last_run.json").exists() else {}
        for name, title in (state.get("ready") or {}).items():
            f = inbox / name
            if f.exists():
                ledger.mark(led, f, "applied", title)
        for name in state.get("skipped") or []:
            f = inbox / name
            if f.exists():
                ledger.mark(led, f, "skipped")
        for name in state.get("events") or []:
            f = inbox / name
            if f.exists():
                ledger.mark(led, f, "applied")
        ledger.save(led_path, led)
        print("Als erledigt gemerkt: %d Bestellungen, %d uebersprungen, %d Ereignisdateien" % (len(state.get("ready") or {}), len(state.get("skipped") or []), len(state.get("events") or [])))
        return 0

    if a.ctx:
        ctx = json.load(open(a.ctx))
    else:
        from plm_intake.context import load_context
        ctx = load_context()
    ctx["aliases"] = json.load(open(intake / "vendor_aliases.json")) if (intake / "vendor_aliases.json").exists() else {}
    po_aliases = json.load(open(intake / "po_aliases.json")) if (intake / "po_aliases.json").exists() else {}

    inbox_items = []
    for f in docs:
        try:
            inbox_items.append((f.name, json.load(open(f))))
        except ValueError as e:
            inbox_items.append((f.name, {"_unreadable": str(e)}))
    results = run.process(inbox_items, ctx)
    (intake / "ready").mkdir(parents=True, exist_ok=True)
    (intake / "blocked").mkdir(parents=True, exist_ok=True)
    payloads, ready, skipped = [], {}, []
    for name, r in results:
        stem = Path(name).stem
        for d in ("ready", "blocked"):
            (intake / d / (stem + ".json")).unlink(missing_ok=True)
        if r.decision == "CREATE":
            json.dump(r.payload, open(intake / "ready" / (stem + ".json"), "w"), ensure_ascii=False, indent=1)
            payloads.append(r.payload)
            ready[name] = r.payload["title"]
        else:
            if r.decision == "SKIP":
                skipped.append(name)
            json.dump({"decision": r.decision, "existing_id": r.existing_id, "issues": [vars(i) for i in r.issues], "payload": r.payload},
                      open(intake / "blocked" / (stem + ".json"), "w"), ensure_ascii=False, indent=1)
    out = ["# Taeglicher Lauf %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "", "Inbox: %s" % inbox,
           "Neu: %d Dokument-Dateien, %d Ereignis-Dateien (schon erledigt: %d)" % (len(docs), len(evs), len([f for f in Path(inbox).glob('*.json')]) - len(docs) - len(evs)), "", run.render_report(results)]
    js_files = []
    if payloads:
        f = intake / ("run_%s.js" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        f.write_text(run.make_js(payloads))
        js_files.append(f.name)
    ev_names = []
    if evs:
        evt = events.load_events(evs)
        pl = events.plan(evt, ctx["orders"], ctx["vendors"], po_aliases, event_overrides=events.load_event_overrides(intake))
        out += ["", events.report(pl)]
        if pl["orders"]:
            f = intake / ("events_%s.js" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
            f.write_text(events.make_js(pl))
            js_files.append(f.name)
        # Nur Dateien als erledigt vormerken, deren Ereignisse ALLE einer Order zugeordnet sind; nicht Zugeordnetes bleibt offen (spaeter evtl. zuordenbar)
        matched = {l["marker"] for o in pl["orders"] for l in o["lines"]}
        by_file = {}
        for e in evt:
            by_file.setdefault(e["_mail"]["id"], []).append(events.marker(e))
        ev_names = [f2.name for f2 in evs if f2.name.endswith("_events.json") and by_file.get(f2.name[:-len("_events.json")]) and all(m in matched for m in by_file[f2.name[:-len("_events.json")]])]
    json.dump({"ready": ready, "skipped": skipped, "events": ev_names, "js": js_files}, open(intake / "last_run.json", "w"), indent=1)
    (intake / "daily_report.md").write_text("\n".join(out))
    print("\n".join(out))
    print("Browser-Skripte:", ", ".join(js_files) or "keine (nichts zu tun)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
