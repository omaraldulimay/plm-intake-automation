"""Nachpruefung per REST (nur lesen): jede Order in output/intake/ready/ muss GENAU EINMAL im PLM stehen und zur Quelle passen;
ausserdem Gesamtcheck auf Dubletten (gleicher Vendor + gleiche PO-Nr oder gleicher Titel).
  python3 -m plm_intake.verify            # Exit 1 bei Abweichung"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402


def check(expected_payloads, live_orders):
    """Reine Funktion -> Liste Befunde (leer = alles gut)."""
    bad = []
    by_title = {}
    for o in live_orders:
        by_title.setdefault(core.norm(o.get("title")), []).append(o)
    for p in expected_payloads:
        hits = by_title.get(core.norm(p["title"]), [])
        if len(hits) == 0:
            bad.append("FEHLT: %s nicht im PLM" % p["title"])
            continue
        if len(hits) > 1:
            bad.append("DOPPELT: %s %d-mal (#%s)" % (p["title"], len(hits), ", #".join(str(h.get("orderNumber")) for h in hits)))
        o = hits[0]
        if abs((o.get("totalCost") or 0) - p["totalCost"]) > core.TOL:
            bad.append("SUMME: %s PLM %s != %s" % (p["title"], o.get("totalCost"), p["totalCost"]))
        if o.get("totalNumberOfPieces") != p["totalNumberOfPieces"]:
            bad.append("STUECK: %s PLM %s != %s" % (p["title"], o.get("totalNumberOfPieces"), p["totalNumberOfPieces"]))
        if len(o.get("items") or []) != len(p["items"]):
            bad.append("POSITIONEN: %s PLM %d != %d" % (p["title"], len(o.get("items") or []), len(p["items"])))
        pq = sum(a["quantity"] for it in o.get("items") or [] for v in it.get("variants") or [] for a in v.get("amounts") or [])
        if pq != p["totalNumberOfPieces"]:
            bad.append("MENGE_IN_POSITIONEN: %s %d != %d" % (p["title"], pq, p["totalNumberOfPieces"]))
        ps = round(sum(x.get("amount") or 0 for x in o.get("payments") or []), 2)
        if abs(ps - p["totalCost"]) > core.TOL:
            bad.append("ZAHLUNGEN: %s %.2f != %.2f" % (p["title"], ps, p["totalCost"]))
        for it_exp, it_live in zip(p["items"], o.get("items") or []):
            if bool(it_exp.get("product")) != bool(it_live.get("product")):
                bad.append("PRODUKTLINK: %s Position '%s' erwartet %s" % (p["title"], it_exp["name"], "Link" if it_exp.get("product") else "kein Link"))
    # Gesamt-Dublettencheck
    keys = Counter()
    for o in live_orders:
        mid = o.get("manufacturer", {}).get("id") if isinstance(o.get("manufacturer"), dict) else o.get("manufacturer")
        if o.get("poNumber"):
            keys[(mid, core.norm(o["poNumber"]))] += 1
    for k, n in keys.items():
        if n > 1:
            bad.append("DUBLETTE im PLM: Vendor %s PO-Nr %s %d-mal" % (k[0], k[1], n))
    return bad


def main(argv=None):
    from plm_intake.context import fetch_all
    import plm_client
    live = fetch_all(plm_client.call, "orders")
    exp = [json.load(open(f)) for f in sorted((ROOT / "output" / "intake" / "ready").glob("*.json"))]
    bad = check(exp, live)
    print("geprueft: %d erwartete Orders, %d live" % (len(exp), len(live)))
    print("\n".join(bad) if bad else "ALLES OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
