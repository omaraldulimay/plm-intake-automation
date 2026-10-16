"""Bruecke: Inbox-JSON (ausgelesene PI/PO) -> Plan fuer case_run (was neu angelegt werden muss, was schon da ist, was ein Mensch entscheiden muss).

  python3 -m plm_intake.case_from_po [--inbox <ordner>] [--ctx ctx_snapshot.json] [--out plans.json]
Nur lesen und planen, schreibt NICHTS ins PLM. Ein Plan ist 'ready' (voll automatisch), wenn die Pruefung (core.build) keinen ERROR hat.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

DEFAULT_INBOX = Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage/Inbox"
FATAL_OK = {"product_unlinked"}   # kein Produkt im PLM = anlegen, kein Blocker


def plan_for(name, po, ctx):
    r = core.build(po, ctx)
    errors = [i for i in r.issues if i.level == "ERROR"]
    by_sku = {core.norm(p.get("sku")): p for p in ctx.get("products") or [] if p.get("sku")}
    new_products, existing, colors = [], [], set()
    for it in po.get("items") or []:
        sku = it.get("sku")
        sizes = []
        cols = []
        for v in it.get("variants") or []:
            cols.append(v.get("color"))
            for s in (v.get("sizes") or {}):
                if s not in sizes: sizes.append(s)
        colors.update(c for c in cols if c)
        prod = by_sku.get(core.norm(sku)) if sku else None
        entry = {"sku": sku, "name": it.get("name") or sku, "colors": cols, "sizes": sizes or ["ONE SIZE"], "product_info": it.get("product_info") or {}}
        if prod:
            have = {v.get("name") for v in prod.get("variants") or []}
            entry.update({"id": prod["id"], "missing_colors": [c for c in cols if c and c not in have]}); existing.append(entry)
        else:
            new_products.append(entry)
    blockers = ["%s: %s" % (i.code, i.msg) for i in errors]
    if not errors and r.decision != "CREATE":
        blockers.append("decision_%s: %s" % (r.decision.lower(), "PO/Lieferant hat schon eine Order oder Beleg zu bestehender PO: Mensch entscheidet (Update/Teillieferung)"))
    return {"file": name, "decision": r.decision, "ready": (not errors) and r.decision == "CREATE", "blockers": blockers, "existing_id": r.existing_id,
            "vendor": po.get("vendor"), "po_number": po.get("po_number"), "doc_type": po.get("doc_type"),
            "new_products": new_products, "existing_products": existing, "colors_needed": sorted(colors), "po_payload": r.payload}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=str(DEFAULT_INBOX))
    ap.add_argument("--ctx", default=str(ROOT / "output/intake/ctx_snapshot.json"))
    ap.add_argument("--out", default=str(ROOT / "output/intake/plans.json"))
    a = ap.parse_args(argv)
    ctx = json.load(open(a.ctx))
    alias = ROOT / "output/intake/vendor_aliases.json"
    ctx["aliases"] = json.load(open(alias)) if alias.exists() else {}
    plans = []
    for f in sorted(Path(a.inbox).glob("*.json")):
        if f.name.endswith("_events.json"): continue
        try:
            plans.append(plan_for(f.name, json.load(open(f)), ctx))
        except Exception as e:  # kaputte Datei darf den Rest nicht stoppen
            plans.append({"file": f.name, "ready": False, "blockers": ["exception: %s: %s" % (type(e).__name__, e)]})
    Path(a.out).write_text(json.dumps(plans, ensure_ascii=False, indent=1))
    ready = [p for p in plans if p["ready"]]
    print("%d Dateien, %d voll automatisch moeglich, %d mit Blocker" % (len(plans), len(ready), len(plans) - len(ready)))
    for p in plans:
        tag = "OK   " if p["ready"] else "BLOCK"
        print("%s %s | %s | neu %d, vorhanden %d | %s" % (tag, p["file"], p.get("po_number"), len(p.get("new_products", [])), len(p.get("existing_products", [])),
                                                         "; ".join(b[:70] for b in p["blockers"][:2])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
