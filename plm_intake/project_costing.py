"""Projektkosten der Lieferanten-Projekte aus belegten Order-Positionen (Dry-Run, schreibt NICHTS).

Je Projekt-Produkt, das in Orders des Lieferanten vorkommt: Menge je Variante = Summe ueber alle Orders, Einkaufspreis = price der Order-Position.
Verschiedene Preise je Variante (mehrere Orders oder Groessen): nicht schreiben, melden. Variante nicht in selectedVariants des Projekt-Produkts: melden.
Ziel-Mutationen (App-GraphQL, Namen aus output/plm_datenmodell/graphql_operationen.json; Projekt-Costing-Zeile = variants[] von getProjectCosting):
  updateVariantQuantity(projectId, variantId, quantity)  |  updateVariantBuyingPriceSimple(projectId, variantId, buyingPrice, projectProductId)
  updateVariantVendor(projectId, variantId, vendorId)   |  bulkUpdateVariantBuyingPrices(projectId, updates)
Ein --apply gibt es bewusst noch nicht (Schreibweg erst nach Freigabe des Dry-Runs).
Aufruf:  .venv/bin/python -m plm_intake.project_costing [--out output/phase2/B27/projektkosten_dryrun.md]"""
import argparse
import sys
from pathlib import Path

from plm_intake import vendor_projects as vp

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = ["updateVariantQuantity", "updateVariantBuyingPriceSimple", "updateVariantVendor", "bulkUpdateVariantBuyingPrices"]


def plan(vendors, orders, projects):
    """-> {projekte: [ {project_id, vendor, vendor_id, zeilen[], konflikte[], fremd[], summe, order_summe, order_summe_pos, orders} ]}"""
    vname = {v["id"]: v.get("name") or "" for v in vendors}
    by_name = {}
    for p in projects:
        by_name.setdefault(vp.norm(p.get("name")), []).append(p)
    out = []
    for vid in sorted(vname, key=lambda v: vname[v].casefold()):
        hit = by_name.get(vp.norm(vname[vid]), [])
        if len(hit) != 1 or not vp.norm(vname[vid]):
            continue
        proj = hit[0]
        sel = {str(x["productId"]): set(x.get("selectedVariants") or []) for x in proj.get("products") or []}
        agg, fremd = {}, []
        nord, order_sum, pos_sum = 0, 0.0, 0.0
        for o in orders:
            if vp.is_test(o.get("title")) or vp.order_vendor_id(o) != vid:
                continue
            nord += 1
            order_sum += float(o.get("totalCost") or 0)
            for it in o.get("items") or []:
                pid = str((it.get("product") or {}).get("id") or "")
                for v in it.get("variants") or []:
                    for a in v.get("amounts") or []:
                        pos_sum += float(a.get("quantity") or 0) * float(a.get("price") or 0)
                    if pid not in sel:
                        fremd.append("%s | %s (Produkt nicht im Projekt)" % (o.get("title"), it.get("name")))
                        break
                    vv = v.get("variantId")
                    if vv not in sel[pid]:
                        fremd.append("%s | %s / %s (Variante nicht im Projekt)" % (o.get("title"), it.get("name"), v.get("name")))
                        continue
                    g = agg.setdefault((pid, vv), {"produkt": it.get("name"), "variante": v.get("name"), "qty": 0, "preise": {}, "orders": set()})
                    for a in v.get("amounts") or []:
                        q = float(a.get("quantity") or 0)
                        if q <= 0:
                            continue
                        g["qty"] += q
                        g["preise"][round(float(a.get("price") or 0), 4)] = o.get("title")
                        g["orders"].add(o.get("title"))
        zeilen, konf, summe = [], [], 0.0
        for (pid, vv), g in sorted(agg.items(), key=lambda kv: (kv[1]["produkt"] or "", kv[1]["variante"] or "")):
            row = {"productId": pid, "variantId": vv, "produkt": g["produkt"], "variante": g["variante"], "menge": int(g["qty"]),
                   "preise": sorted(g["preise"]), "orders": sorted(g["orders"])}
            if len(row["preise"]) > 1 or not row["preise"] or row["preise"][0] <= 0:
                konf.append(row)
            else:
                row["preis"] = row["preise"][0]
                summe += row["menge"] * row["preis"]
                zeilen.append(row)
        if nord or zeilen:
            out.append({"project_id": proj["id"], "vendor": vname[vid], "vendor_id": vid, "zeilen": zeilen, "konflikte": konf, "fremd": sorted(set(fremd)),
                        "summe": round(summe, 2), "order_summe": round(order_sum, 2), "order_summe_pos": round(pos_sum, 2), "orders": nord})
    return {"projekte": out}


def report(pl):
    P = pl["projekte"]
    L = ["# Projektkosten Dry-Run (nichts geschrieben)", "",
         "Quelle: Order-Positionen je Lieferant (Menge = Summe ueber Orders, Preis = price je Variante). Schreibweg: %s." % ", ".join(MUTATIONS), "",
         "| Projekt | Orders | Zeilen | Konflikte | nicht im Projekt | Summe Projekt (belegt) | Summe Order-Positionen | totalCost Orders | Differenz Projekt-totalCost |",
         "|---|---|---|---|---|---|---|---|---|"]
    for p in sorted(P, key=lambda p: -p["summe"]):
        L.append("| %s | %d | %d | %d | %d | %.2f | %.2f | %.2f | %.2f |" % (p["vendor"], p["orders"], len(p["zeilen"]), len(p["konflikte"]), len(p["fremd"]),
                                                                           p["summe"], p["order_summe_pos"], p["order_summe"], p["summe"] - p["order_summe"]))
    L += ["", "Summe: Projekt %.2f | Order-Positionen %.2f | totalCost %.2f" % (sum(p["summe"] for p in P), sum(p["order_summe_pos"] for p in P), sum(p["order_summe"] for p in P)), ""]
    L.append("## Konflikte (verschiedene Preise oder Preis 0 je Variante: nicht schreiben)")
    for p in P:
        for r in p["konflikte"]:
            L.append("- %s | %s / %s | Menge %d | Preise %s | Orders %s" % (p["vendor"], r["produkt"], r["variante"], r["menge"], r["preise"], "; ".join(r["orders"])))
    L += ["", "## Order-Positionen ausserhalb der Projekt-Produkte/-Varianten"]
    for p in P:
        for f in p["fremd"]:
            L.append("- %s | %s" % (p["vendor"], f))
    L += ["", "## Schreibzeilen je Projekt (Variante: Menge x Preis)"]
    for p in P:
        if p["zeilen"]:
            L += ["", "### %s (%d Zeilen, %.2f)" % (p["vendor"], len(p["zeilen"]), p["summe"])]
            L += ["- %s / %s: %d x %.4f" % (r["produkt"], r["variante"], r["menge"], r["preis"]) for r in p["zeilen"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output" / "phase2" / "B27" / "projektkosten_dryrun.md"))
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    import plm_client
    from plm_intake.context import fetch_all
    pl = plan(fetch_all(plm_client.call, "vendors"), fetch_all(plm_client.call, "orders"), fetch_all(plm_client.call, "projects"))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(report(pl), encoding="utf-8")
    print("geschrieben:", a.out)
    for p in sorted(pl["projekte"], key=lambda p: -p["summe"])[:10]:
        print("%-34s zeilen %3d konfl %2d summe %.2f order_pos %.2f totalCost %.2f" % (p["vendor"][:34], len(p["zeilen"]), len(p["konflikte"]), p["summe"], p["order_summe_pos"], p["order_summe"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
