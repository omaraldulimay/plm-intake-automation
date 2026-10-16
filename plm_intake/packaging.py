"""HS-Code (Zolltarifnummer) am Produkt (Feld packaging.hsCode) aus Plenty (logistics.skus.hs_code), mit Plausibilitaetspruefung.

  python3 -m plm_intake.packaging [--n 25] [--skus A,B]            TROCKENLAUF (Standard): Bericht output/packaging/plan_<Zeit>.md
  python3 -m plm_intake.packaging --apply [--n 25] [--skus A,B]    schreibt nur plausible HS-Codes in LEERE Felder (andere Verpackungsfelder bleiben unveraendert) und liest zurueck

Plausibel = Kapitel passt zur Produktart: Taschen/Rucksaecke 42, Schuhe 64, Bekleidung 61 oder 62. Unplausible oder widerspruechliche Codes (z. B. Schuh-Code an einer Jacke)
werden NICHT geschrieben, sondern gemeldet. Ein schon gesetzter abweichender Code wird nie ueberschrieben. Kartonmasse/Gewicht/Ursprungsland: nicht in Plenty, kommen aus Packlisten."""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import barcodes as bc, batch_plan, core  # noqa: E402

OUT = ROOT / "output" / "packaging"
PKG_KEYS = ("cartonLengthCm", "cartonWidthCm", "cartonHeightCm", "cartonGrossWeightKg", "piecesPerCarton", "productNetWeightKg", "polybagWeightKg", "hsCode", "dutyRatePercent", "countryOfOrigin")


def kind_of(name):
    n = str(name or "").lower()
    if re.search(r"\b(bag|tasche|rucksack|backpack|sporttasche|beutel)\b", n):
        return "bag"
    if re.search(r"sneaker|schuh|shoe|boot", n):
        return "shoe"
    return "apparel"


def chapter_ok(hs, kind):
    ch = str(hs or "")[:2]
    return {"bag": ch == "42", "shoe": ch == "64", "apparel": ch in ("61", "62")}[kind]


HEADINGS = [   # (Stichworte im Produktnamen, erlaubte 4-stellige Positionen)
    (r"t[- ]?shirt|tee\b|tank|singlet|longsleeve|long sleeve", {"6109"}),
    (r"hoodie|sweatshirt|sweat shirt|sweater|pullover|fleece|crewneck|crew neck", {"6110", "6101", "6102"}),
    (r"jacket|jacke|windbreaker|anorak|parka|coat|mantel|vest|weste", {"6101", "6102", "6110", "6201", "6202", "6113", "6114"}),
    (r"pant|hose|jogger|legging|tight|short|trouser", {"6103", "6104", "6112", "6115", "6203", "6204", "6211"}),
]


def heading_ok(hs, name):
    """Passt die Warengruppe (erste 4 Stellen) zum Produktnamen? Ohne erkennbares Stichwort: keine Aussage (True)."""
    n = str(name or "").lower()
    for rx, ok in HEADINGS:
        if re.search(rx, n):
            return str(hs)[:4] in ok
    return True


def plan(prod, plenty_hs, current_hs):
    """-> (aktion, hs, grund). plenty_hs: Menge der HS-Codes in Plenty zu diesem Produkt."""
    hs = sorted(h for h in plenty_hs if h)
    if not hs:
        return "KEIN_PLENTY", None, "Plenty hat keinen HS-Code"
    if len(hs) > 1:
        return "FLAGGE", None, "mehrere HS-Codes in Plenty: %s" % ", ".join(hs)
    code = re.sub(r"\D", "", hs[0])
    if not re.fullmatch(r"\d{8,10}", code):
        return "FLAGGE", None, "HS-Code unueblich: %s" % hs[0]
    k = kind_of(prod.get("name"))
    if not chapter_ok(code, k):
        return "FLAGGE", code, "Kapitel %s passt nicht zu '%s' (%s)" % (code[:2], prod.get("name"), k)
    if not heading_ok(code, prod.get("name")):
        return "FLAGGE", code, "Position %s passt nicht zu '%s'" % (code[:4], prod.get("name"))
    if current_hs:
        return ("OK" if re.sub(r"\D", "", str(current_hs)) == code else "KONFLIKT"), code, "im PLM schon %s" % current_hs
    return "SCHREIBEN", code, "Kapitel %s passt zu %s" % (code[:2], k)


def plenty_hs(skus):
    out = {}
    if not skus:
        return out
    sql = ("select regexp_replace(upper(regexp_replace(variation_no,'-[A-Z]+[0-9]+$','')),'[^A-Z0-9]','','g'), coalesce(hs_code,'') from logistics.skus "
           "where variation_no ~ '-[A-Z]+[0-9]+$' and regexp_replace(upper(regexp_replace(variation_no,'-[A-Z]+[0-9]+$','')),'[^A-Z0-9]','','g') in (%s) group by 1,2"
           % ",".join("'%s'" % re.sub(r"[^A-Z0-9]", "", str(s).upper()) for s in skus))
    r = subprocess.run([bc.PSQL, bc.CONN, "-At", "-F", "\t", "-c", sql], capture_output=True, text=True, cwd=str(ROOT), timeout=300,
                       env=dict(__import__("os").environ, PGOPTIONS="-c default_transaction_read_only=on"))
    if r.returncode:
        raise RuntimeError("Plenty-Abfrage gescheitert: " + r.stderr[-200:])
    for line in r.stdout.splitlines():
        k, h = line.split("\t")
        out.setdefault(core.norm(k), set()).add(h)
    return out


WRITE_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v });
  const V = n => ({ kind: 'Variable', name: N(n) });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: (args || []), selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const doc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation',
    variableDefinitions: [{ kind: 'VariableDefinition', variable: V('id'), type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N('String') } } }, { kind: 'VariableDefinition', variable: V('packaging'), type: { kind: 'NamedType', name: N('ProductPackagingInput') } }],
    selectionSet: { kind: 'SelectionSet', selections: [F('updateProduct', [{ kind: 'Argument', name: N('updateProductInput'), value: { kind: 'ObjectValue', fields: [{ kind: 'ObjectField', name: N('id'), value: V('id') }, { kind: 'ObjectField', name: N('packaging'), value: V('packaging') }] } }],
      [F('id'), F('packaging', [], ['cartonLengthCm', 'cartonWidthCm', 'cartonHeightCm', 'cartonGrossWeightKg', 'piecesPerCarton', 'productNetWeightKg', 'polybagWeightKg', 'hsCode', 'dutyRatePercent', 'countryOfOrigin'].map(n => F(n)))])] } }] };
  const c = window.__APOLLO_CLIENT__; const out = [];
  for (const j of __JOBS__) {
    try { const r = await c.mutate({ mutation: doc, variables: { id: j.id, packaging: j.packaging }, errorPolicy: 'all' });
          out.push({ id: j.id, sku: j.sku, packaging: r.data && r.data.updateProduct && r.data.updateProduct.packaging, err: (r.errors || []).map(e => e.message.slice(0, 160)) }); }
    catch (e) { out.push({ id: j.id, sku: j.sku, fatal: String(e.message).slice(0, 200) }); break; }
  }
  return out;
})()'''


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25); ap.add_argument("--skus"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true"); ap.add_argument("--offset", type=int, default=0)
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    vendors = fetch_all(plm_client.call, "vendors"); products = fetch_all(plm_client.call, "products")
    prods = bc.select_products(a.n, a.skus, vendors, products, a.all, a.offset)
    det = batch_plan.fetch_details([p["id"] for p in prods])
    hs = plenty_hs([p.get("sku") for p in prods])
    report = ["# Verpackung/HS-Code (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Stand %s, %d Produkte" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), len(prods)), "",
              "| Produkt | Aktion | HS-Code | Grund |", "|---|---|---|---|"]
    jobs = []
    for p in prods:
        pk = ((det.get(p["id"]) or {}).get("info") or {}).get("packaging") or {}
        act, code, why = plan(p, hs.get(core.norm(p.get("sku")), set()), pk.get("hsCode"))
        report.append("| %s %s | %s | %s | %s |" % (p.get("sku"), str(p.get("name"))[:28], act, code or "–", why))
        if act == "SCHREIBEN":
            merged = {k: pk.get(k) for k in PKG_KEYS if pk.get(k) not in (None, "")}
            merged["hsCode"] = code
            jobs.append({"id": p["id"], "sku": p.get("sku"), "packaging": merged})
    report += ["", "Zu schreiben: %d HS-Codes" % len(jobs)]
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if a.apply and jobs:
        res = bc.run_js(WRITE_JS.replace("__JOBS__", json.dumps(jobs)))
        after = batch_plan.fetch_details([j["id"] for j in jobs])
        bad = []
        for j in jobs:
            now = ((after.get(j["id"]) or {}).get("info") or {}).get("packaging") or {}
            if str(now.get("hsCode")) != j["packaging"]["hsCode"] or any(now.get(k) != v for k, v in j["packaging"].items() if k != "hsCode"):
                bad.append(j["sku"])
        report += ["", "## Schreibergebnis"] + ["- %s: %s" % (r.get("sku"), r.get("fatal") or r.get("err") or "ok") for r in res]
        report += ["", "## Rueckpruefung", "- %s" % ("ALLES zurueckgelesen und gleich" if not bad else "ABWEICHUNG bei: %s" % bad)]
    (OUT / ("plan_%s.md" % stamp)).write_text("\n".join(report))
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
