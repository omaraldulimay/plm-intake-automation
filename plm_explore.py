#!/usr/bin/env python3
"""Systematischer Explorer: probiert pro Teilziel viele Body-Varianten durch, stoppt je Teilziel beim ersten Treffer
und schreibt ALLES in output/explore_report.json (Claude liest die Datei, kein Copy-Paste noetig).

Teilziele (nur echte, gewollte Datensaetze: Produkt SNW26-102 und PO-Huelle "EasyFitness ALPHA MEN"):
  1. PO: payments befuellen   2. PO: items befuellen   3. Produkt: sizes setzen   4. Produkt: variants setzen
Pro Versuch: frische Version laden (expectedUpdatedAt), PUT/POST, danach per Listen-GET verifizieren
(der Server antwortet oft 500, obwohl gespeichert) -> Erfolg zaehlt nur, wenn das Ergebnis wirklich stimmt.

  .venv/bin/python plm_explore.py            # Trockenlauf: zeigt nur die Anzahl der Versuche
  .venv/bin/python plm_explore.py --apply    # ausfuehren (ca. 3-5 Minuten)
"""
import copy
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import plm_create_orders as m
from plm_client import call

ROOT = Path(__file__).parent
APPLY = "--apply" in sys.argv
REPORT = {"started": datetime.now(timezone.utc).isoformat(), "goals": {}}
oid = lambda: secrets.token_hex(12)
norm = m.norm


def save():
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "explore_report.json").write_text(json.dumps(REPORT, indent=1, ensure_ascii=False, default=str))


def all_products():
    out, p = [], 1
    while True:
        st, d = call("GET", "products", limit=100, page=p)
        out += d["data"]
        if p >= d["pagination"]["pages"]:
            return out
        p += 1


def product():
    return next((x for x in all_products() if x["sku"] == "SNW26102"), None)


def order(title):
    return next((o for o in call("GET", "orders")[1] if o["title"] == title), None)


def run_goal(goal, attempts, put_path, version_getter, check):
    """attempts: Liste (name, body-ohne-Version). Stoppt beim ersten Treffer."""
    log = REPORT["goals"].setdefault(goal, {"attempts": [], "success": None})
    print(f"\n== {goal}: {len(attempts)} Versuche")
    if not APPLY:
        return None
    for name, body, method in attempts:
        rec = version_getter()
        if check(rec):
            log["success"] = "bereits erledigt"
            print("  schon erledigt")
            return log["success"]
        full = {**body, "expectedUpdatedAt": rec["updatedAt"]} if method == "PUT" else body
        path = put_path(rec)
        st, res = call(method, path, full)
        after = version_getter()
        ok = bool(check(after))
        msg = res if isinstance(res, str) else res.get("message") if isinstance(res, dict) else str(res)
        log["attempts"].append({"name": name, "method": method, "path": path.split("/")[-1], "status": st, "message": str(msg)[:200], "ok": ok,
                                "body": json.dumps(body, ensure_ascii=False, default=str)[:400]})
        print(f"  {'OK ' if ok else '-- '} {name} -> {st}")
        save()
        if ok:
            log["success"] = name
            log["working_body"] = json.dumps(body, ensure_ascii=False, default=str)[:1500]
            return name
        time.sleep(0.2)
    return None


def main():
    vendor = next(v for v in call("GET", "vendors")[1] if v["name"] == "Lieferant A")
    prods = all_products()
    by = {}
    for x in prods:
        by.setdefault(norm(x["name"]), []).append(x)
    body = m.build(m.load_pos()["ALPHA_MEN"], vendor["id"], by)
    title = body["title"]
    by_id = {x["id"]: x for x in prods}
    o = order(title)
    if not o:
        print("PO-Huelle fehlt - erst plm_try_create.py --apply laufen lassen.")
        return
    oput = lambda rec: f"orders/{rec['id']}"
    ov = lambda: order(title)

    # ---------- 1) payments ----------
    def pay(extra, ids):
        out = []
        for p_ in body["payments"]:
            d = {"name": p_["name"], "terms": p_["terms"], "status": "Unpaid", **extra}
            if ids == "id": d["id"] = oid()
            if ids == "_id": d["_id"] = oid()
            if ids == "both":
                i = oid(); d["id"] = i; d["_id"] = i
            out.append(d)
        return out
    po_ms = int(datetime(2026, 9, 9, tzinfo=timezone.utc).timestamp() * 1000)
    pa = []
    for due in ("absent", None):
        for amt in ("absent", 0, None):
            for ids in ("none", "id", "_id", "both"):
                extra = {}
                if due != "absent": extra["dueDate"] = due
                if amt != "absent": extra["amount"] = amt
                pa.append((f"payments amount={amt} dueDate={due} ids={ids}", {"payments": pay(extra, ids)}, "PUT"))
    for ids in ("none", "id", "both"):  # Platzhalter-Datum NUR als letzte Option (wird im Bericht markiert)
        pa.append((f"payments amount=0 dueDate=PO-Datum(Platzhalter) ids={ids}", {"payments": pay({"amount": 0, "dueDate": po_ms}, ids)}, "PUT"))
    run_goal("1_PO_payments", pa, oput, ov, lambda r: r and len(r["payments"]) == len(body["payments"]))

    # ---------- 2) items ----------
    def items(prod_form, ids, shape):
        out = []
        for i in body["items"]:
            pid = i["product"]
            prod = by_id[pid]
            vs = []
            for v in i["variants"]:
                if shape == "full":
                    amts = [{"key": a["key"], "quantity": a["quantity"], "price": 0, "cost": 0, "shippedQuantity": 0, "remainingQuantity": a["quantity"],
                             "fulfillmentPercentage": 0, "totalValue": 0, "totalCost": 0} for a in v["amounts"]]
                else:
                    amts = [{"key": a["key"], "quantity": a["quantity"]} for a in v["amounts"]]
                vd = {"variantId": v["variantId"], "name": v["name"], "amounts": amts}
                if ids in ("id", "both"): vd["id"] = oid()
                if ids in ("_id", "both"): vd["_id"] = oid()
                vs.append(vd)
            d = {"name": prod["name"], "variants": vs, "totalQuantity": i["totalQuantity"], "cost": 0}
            if prod_form == "str": d["product"] = pid
            elif prod_form == "obj": d["product"] = {"id": pid}
            else: d["productId"] = pid
            if ids in ("id", "both"): d["id"] = oid()
            if ids in ("_id", "both"): d["_id"] = oid()
            out.append(d)
        return out
    ia = []
    for shape in ("full", "min"):
        for pf in ("str", "obj", "productId"):
            for ids in ("none", "id", "_id", "both"):
                ia.append((f"items product={pf} ids={ids} shape={shape}", {"items": items(pf, ids, shape), "totalNumberOfPieces": body["totalNumberOfPieces"]}, "PUT"))
    want = {i["product"]: i["totalQuantity"] for i in body["items"]}
    def items_ok(r):
        if not r or len(r["items"]) != len(body["items"]): return False
        got = {it["product"]["id"]: it["totalQuantity"] for it in r["items"]}
        return got == want
    run_goal("2_PO_items", ia, oput, ov, items_ok)

    # ---------- 3) product sizes ----------
    pr = product()
    S = ["XS", "S", "M", "L", "XL"]
    pput = lambda rec: f"products/{rec['id']}"
    sa = [("sizes strings", {"sizes": S}, "PUT"),
          ("sizes [{title}]", {"sizes": [{"title": x} for x in S]}, "PUT"),
          ("sizes [{title,id}]", {"sizes": [{"title": x, "id": oid()} for x in S]}, "PUT"),
          ("sizes [{title,_id}]", {"sizes": [{"title": x, "_id": oid()} for x in S]}, "PUT"),
          ("sizes [{name}]", {"sizes": [{"name": x} for x in S]}, "PUT"),
          ("sizes [{size}]", {"sizes": [{"size": x} for x in S]}, "PUT"),
          ("sizes [{label}]", {"sizes": [{"label": x} for x in S]}, "PUT"),
          ("sizes [{title,order}]", {"sizes": [{"title": x, "order": i} for i, x in enumerate(S)]}, "PUT"),
          ("sizes [{title}] + confirmImpact", {"sizes": [{"title": x} for x in S], "confirmImpact": True}, "PUT"),
          ("sizes strings + masterSize M", {"sizes": S, "masterSize": "M"}, "PUT"),
          ("Unterroute PUT /sizes strings", {"sizes": S}, "PUT:sizes"),
          ("Unterroute PUT /sizes objekte", {"sizes": [{"title": x} for x in S]}, "PUT:sizes"),
          ("Unterroute POST /sizes", {"sizes": [{"title": x} for x in S]}, "POST:sizes")]
    def sub(att):
        out = []
        for n, b, mth in att:
            if ":" in mth:
                mm, route = mth.split(":")
                out.append((n, b, mm, route))
            else:
                out.append((n, b, mth, None))
        return out
    def run_sub(goal, att, check):
        att2 = sub(att)
        log = REPORT["goals"].setdefault(goal, {"attempts": [], "success": None})
        print(f"\n== {goal}: {len(att2)} Versuche")
        if not APPLY: return
        for n, b, mm, route in att2:
            rec = product()
            if check(rec):
                log["success"] = "bereits erledigt"; print("  schon erledigt"); return
            path = f"products/{rec['id']}" + (f"/{route}" if route else "")
            full = {**b, "expectedUpdatedAt": rec["updatedAt"]} if mm == "PUT" else b
            st, res = call(mm, path, full)
            ok = bool(check(product()))
            msg = res.get("message") if isinstance(res, dict) else str(res)
            log["attempts"].append({"name": n, "method": mm, "path": path.split("products/")[-1][24:] or "(Produkt)", "status": st, "message": str(msg)[:200], "ok": ok, "body": json.dumps(b, ensure_ascii=False)[:300]})
            print(f"  {'OK ' if ok else '-- '} {n} -> {st}"); save()
            if ok:
                log["success"] = n; log["working_body"] = json.dumps(b, ensure_ascii=False)[:800]; return
    run_sub("3_Produkt_sizes", sa, lambda r: r and len(r["sizes"]) == len(S))

    # ---------- 4) product variants ----------
    va = [("variants [{name}]", {"variants": [{"name": "Default Style"}]}, "PUT"),
          ("variants [{name,id}]", {"variants": [{"name": "Default Style", "id": oid()}]}, "PUT"),
          ("variants [{name,color:{}}]", {"variants": [{"name": "Default Style", "color": {}}]}, "PUT"),
          ("variants [{name,color:null}]", {"variants": [{"name": "Default Style", "color": None}]}, "PUT"),
          ("variants [{title}]", {"variants": [{"title": "Default Style"}]}, "PUT"),
          ("isDefaultVariant true", {"isDefaultVariant": True}, "PUT"),
          ("Unterroute POST /variants {name}", {"name": "Default Style"}, "POST:variants"),
          ("Unterroute POST /variants {name,color}", {"name": "Default Style", "color": {}}, "POST:variants")]
    run_sub("4_Produkt_variants", va, lambda r: r and len(r["variants"]) > 0)

    # ---------- Endstand ----------
    o = order(title); pr = product()
    REPORT["final"] = {"PO": {"items": len(o["items"]), "pieces": o["totalNumberOfPieces"], "payments": len(o["payments"])} if o else None,
                       "Produkt SNW26-102": {"sizes": pr["sizes"], "variants": [v["name"] for v in pr["variants"]]} if pr else None}
    save()
    print("\nEndstand:", json.dumps(REPORT["final"], ensure_ascii=False))
    print("Bericht: output/explore_report.json  -> bitte nur 'fertig' sagen, ich lese ihn selbst.")


if __name__ == "__main__":
    if not APPLY:
        print("Trockenlauf: zeigt nur die Zahl der Versuche je Teilziel.")
    main()
