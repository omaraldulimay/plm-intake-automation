#!/usr/bin/env python3
"""Korrigiert Zahlungsbetraege in POs, die um den Faktor 1000 zu klein gespeichert sind.

Erkennung (nicht raten): Summe der Payments * 1000 entspricht dem PO-Gesamtbetrag (totalCost) auf 0,5 % genau,
waehrend die Summe der Payments selbst weit darunter liegt. Nur dann wird x1000 korrigiert.
Schreiben: PUT /orders/{id} mit nur "payments" (+ expectedUpdatedAt), danach GET-Pruefung.

  .venv/bin/python plm_fix_payments.py             # Trockenlauf
  .venv/bin/python plm_fix_payments.py --apply [TITEL]   # optional nur eine PO
"""
import json
import sys

from plm_client import call

APPLY = "--apply" in sys.argv
ONLY = next((a for a in sys.argv[1:] if not a.startswith("--")), None)


def suspect(o):
    amounts = [p.get("amount") or 0 for p in o["payments"]]
    s, total = sum(amounts), o.get("totalCost") or 0
    return bool(total) and s > 0 and abs(s * 1000 - total) / total < 0.005 and s < total / 100


def main():
    orders = call("GET", "orders")[1]
    todo = [o for o in orders if suspect(o) and (not ONLY or o["title"] == ONLY)]
    print("Pruefung der Zahlungsbetraege:")
    for o in orders:
        s = sum(p.get("amount") or 0 for p in o["payments"])
        print(f"  {o['title']:28s} Summe Payments {s:>12,.4f} | totalCost {o['totalCost']:>12,.2f} | {'-> x1000 noetig' if suspect(o) else 'ok'}")
    if not APPLY:
        print(f"\nTrockenlauf: {len(todo)} POs betroffen. Mit --apply ausfuehren (optional mit Titel).")
        return
    for o in todo:
        payments = [{**p, "amount": round(p["amount"] * 1000, 2)} for p in o["payments"]]
        st, res = call("PUT", f"orders/{o['id']}", {"payments": payments, "expectedUpdatedAt": o["updatedAt"]})
        after = call("GET", f"orders/{o['id']}")[1]
        got = [p["amount"] for p in after["payments"]]
        want = [p["amount"] for p in payments]
        ok = got == want
        print(f"  {o['title']}: PUT -> {st} | Betraege jetzt {got} | {'verifiziert' if ok else 'ABWEICHUNG, Antwort: ' + json.dumps(res, ensure_ascii=False)[:300]}")
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
