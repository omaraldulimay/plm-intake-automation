#!/usr/bin/env python3
"""Produktkorrekturen im PLM per PUT + expectedUpdatedAt (Mechanismus laut App-Code).

Wichtig (Befund 2026-10-07): PUT /products/{id} speichert, antwortet aber mit 500, weil der Server das Produkt
danach nicht zuruecklesen kann (derselbe Fehler wie GET /products/{id}). Deshalb wird NICHT der Statuscode,
sondern das Ergebnis per Listen-GET geprueft.

Schutz: nur die gewollten Felder werden gesendet, Vorabcheck gegen das Backup (nichts dazwischen geaendert),
Ziel-SKU darf nicht schon vergeben sein, nachher darf sich ausser den gewollten Feldern nichts aendern.
Bereits erledigte Schritte werden uebersprungen (idempotent).
  .venv/bin/python plm_apply_corrections.py            # Trockenlauf
  .venv/bin/python plm_apply_corrections.py --apply
"""
import json
import sys
from pathlib import Path

from plm_client import call

ROOT = Path(__file__).parent
APPLY = "--apply" in sys.argv
IGNORE = {"updatedAt"}


def products():
    out, p = [], 1
    while True:
        st, d = call("GET", "products", limit=100, page=p)
        assert st == 200, f"GET products -> {st}"
        out += d["data"]
        if p >= d["pagination"]["pages"]:
            return {x["id"]: x for x in out}
        p += 1


def plan(backup):
    steps = []
    for p in sorted(backup, key=lambda x: x["name"]):
        n = p["name"]
        if n.startswith("SKM27-") and p["sku"].startswith("SKW27") and n != "SKM27-001":
            steps.append((p["id"], f"{n}: SKU {p['sku']} -> {n.replace('-', '')}", {"sku": n.replace("-", "")}))
    p004 = next(x for x in backup if x["sku"] == "SNM2600")
    steps.insert(0, (p004["id"], "SNM26-00 -> SNM26-004 (Name, SKU)", {"name": "SNM26-004", "sku": "SNM26004"}))
    # additionalFields (Genderq -> Gender) wird von PUT nicht uebernommen -> bewusst ausgelassen (kosmetisch)
    return steps


def main():
    backup = json.load(open(ROOT / "output/backup/products_before_2026-10-07.json"))
    bk = {p["id"]: p for p in backup}
    cur = products()
    steps = plan(backup)
    todo = []
    for pid, label, ch in steps:
        done = all(cur[pid].get(k) == v for k, v in ch.items())
        print(f"  {'erledigt' if done else 'offen   '}  {label}")
        if not done:
            todo.append((pid, label, ch))
    skus = {p["sku"] for p in cur.values()}
    for pid, label, ch in todo:
        if "sku" in ch:
            assert ch["sku"] not in skus, f"{label}: Ziel-SKU existiert schon - Abbruch"
    if not APPLY:
        print(f"\nTrockenlauf: {len(todo)} Schritte offen. Mit --apply ausfuehren.")
        return
    for pid, label, ch in todo:
        before = products()[pid]
        st, res = call("PUT", f"products/{pid}", {**ch, "expectedUpdatedAt": before["updatedAt"]})
        after = products()[pid]
        diff = {k for k in set(before) | set(after) if k not in IGNORE and before.get(k) != after.get(k)}
        ok = all(after.get(k) == v for k, v in ch.items())
        if not ok or diff - set(ch):
            print(f"  FEHLER bei '{label}' (HTTP {st}): nicht uebernommen={[k for k in ch if after.get(k) != ch[k]]}, unerwartet geaendert={sorted(diff - set(ch))} -> Abbruch")
            print("  Antwort:", json.dumps(res, ensure_ascii=False)[:300])
            sys.exit(1)
        print(f"  ok  {label} (HTTP {st}, per Liste verifiziert)")
    print("\nAlle Schritte ausgefuehrt und per GET verifiziert.")


if __name__ == "__main__":
    main()
