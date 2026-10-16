"""Batch-Plan (TROCKENLAUF, nur lesen): die N neuesten Produkte aus den Mails, was fuer jedes Datenfeld des PLM aus den Mails kommt und was im PLM schon steht.

  python3 -m plm_intake.batch_plan [--n 25] [--sheet <Protokoll.xlsx>]    -> output/batch_plan.md
Schreibt NICHTS ins PLM. Liest Inbox-Dateien, REST (Produkte/Lieferanten) und per Browser-GraphQL die Produktdetails (Verpackung, Maße, Techpack, Hauptmaterial).
Zweck: vor der Migration sehen, wie vollstaendig die Mails die Felder des PLM abdecken (siehe output/PLM_Datenmodell.md)."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core, daily, new_products  # noqa: E402

BROWSER = ROOT / "plm_intake" / "browser"
DOC_WORDS = re.compile(r"tech[ _-]?pack|spec|size[ _-]?(chart|table|spec)|measure|mass|bom|material|fabric|trim|grading|sketch|label|carton", re.I)

DETAIL_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v });
  const tok = s => s.match(/\$?[A-Za-z_]\w*|[{}():]|"[^"]*"|-?\d+/g);
  const parse = (src, vt) => {
    const t = tok(src); let i = 0;
    const sel = () => { i++; const out = []; while (t[i] !== '}') out.push(field()); i++; return { kind: 'SelectionSet', selections: out }; };
    const val = v => v[0] === '$' ? { kind: 'Variable', name: N(v.slice(1)) } : v[0] === '"' ? { kind: 'StringValue', value: v.slice(1, -1) } : /^-?\d+$/.test(v) ? { kind: 'IntValue', value: v } : { kind: 'EnumValue', value: v };
    const field = () => { const f = { kind: 'Field', name: N(t[i++]), arguments: [] };
      if (t[i] === '(') { i++; while (t[i] !== ')') { const n = t[i++]; i++; f.arguments.push({ kind: 'Argument', name: N(n), value: val(t[i++]) }); } i++; }
      if (t[i] === '{') f.selectionSet = sel(); return f; };
    const s = sel(); return { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: [{ kind: 'VariableDefinition', variable: { kind: 'Variable', name: N('productId') }, type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N(vt || 'String') } } }], selectionSet: s }] };
  };
  const Q = {
    info: '{ getProductGeneralInfo(productId:$productId){ id sku name barcode rrp estimatedCost masterSize measurementUnit season year tags packaging{ cartonLengthCm cartonWidthCm cartonHeightCm cartonGrossWeightKg piecesPerCarton productNetWeightKg polybagWeightKg hsCode dutyRatePercent countryOfOrigin } dimensions{ lengthCm widthCm heightCm } mainMaterial{ id name } sizes{ id title } } }',
    base: '{ getProductBaseMeasurements(productId:$productId){ id baseSize measurements{ id name requiredValue } } }',
    tp: '{ getProductTechpacksByProduct(productId:$productId){ id code name status vendorId variantIds } }',
    ident: '{ listIdentifiers(productId:$productId){ id productVariant{ id name } sizes{ id title barcode sku } } }'
  };
  const c = window.__APOLLO_CLIENT__; const out = {};
  for (const id of __IDS__) {
    out[id] = {};
    for (const [k, q] of Object.entries(Q)) {
      try { const r = await c.query({ query: parse(q, k === 'ident' ? 'ID' : 'String'), variables: { productId: id }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
            out[id][k] = r.data ? Object.values(r.data)[0] : null; if (r.errors && r.errors.length) out[id][k + '_err'] = r.errors[0].message.slice(0, 120); }
      catch (e) { out[id][k + '_err'] = String(e.message).slice(0, 120); }
    }
  }
  return out;
})()'''


def load_docs(inbox):
    docs = []
    for f in sorted(Path(inbox).glob("*.json")):
        if f.name.endswith("_events.json"):
            continue
        try:
            d = json.load(open(f))
        except ValueError:
            continue
        d["_file"] = f.name
        docs.append(d)
    docs.sort(key=lambda d: str((d.get("source") or {}).get("mail_date") or ""), reverse=True)
    return docs


def collect(docs, vendors, aliases, n):
    """Die n neuesten verschiedenen Styles ueber alle Belege (neueste Angabe gewinnt je Feld)."""
    out, order = {}, []
    for d in docs:
        v, _ = core.match_vendor(d.get("vendor") or "", vendors, aliases)
        for it in d.get("items") or []:
            sku = str(it.get("sku") or "").strip()
            if not sku:
                continue
            k = core.norm(sku)
            if k not in out:
                if len(order) >= n:
                    continue
                order.append(k)
                out[k] = {"sku": sku, "name": re.sub(r"\s+", " ", str(it.get("name") or "")).strip(), "vendor": (v or {}).get("name") or d.get("vendor"), "vendor_known": bool(v),
                          "docs": [], "colors": [], "sizes": [], "prices": set(), "pi": {}, "currency": d.get("currency"), "newest": str((d.get("source") or {}).get("mail_date") or "")}
            e = out[k]
            e["docs"].append("%s %s (%s)" % (d.get("doc_type"), d.get("po_number") or "-", str((d.get("source") or {}).get("mail_date") or "")[:10]))
            for var in it.get("variants") or []:
                if var.get("color") and var["color"] not in e["colors"]:
                    e["colors"].append(var["color"])
                for s in (var.get("sizes") or {}):
                    if s not in e["sizes"]:
                        e["sizes"].append(s)
                if var.get("price") is not None:
                    e["prices"].add(var["price"])
            for key, val in (it.get("product_info") or {}).items():
                if val not in (None, "", []) and key not in e["pi"]:
                    e["pi"][key] = val
    return [out[k] for k in order]


def fetch_details(ids):
    if not ids:
        return {}
    js = DETAIL_JS.replace("__IDS__", json.dumps(ids))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=900)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def source_docs(sheet, items, since):
    """Anhaenge der Mails seit `since`, deren Name oder Betreff nach Techpack/Spec/Maßblatt/Material aussieht und zum Style passt."""
    if not sheet or not Path(sheet).exists():
        return {}
    import datetime
    import openpyxl
    wb = openpyxl.load_workbook(sheet, read_only=True)
    rows = list(wb["Exportiert"].iter_rows(values_only=True))[1:]
    res = {}
    for e in items:
        rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(e["sku"]) + r"(?![A-Za-z0-9])", re.I)
        hits = []
        for r in rows:
            d = r[1]
            if isinstance(d, (int, float)):
                d = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=d)
            if not isinstance(d, datetime.datetime) or d < since:
                continue
            for a in str(r[5] or "").split(" | "):
                if a.strip() and (rx.search(a) or rx.search(str(r[3] or ""))) and DOC_WORDS.search(a):
                    hits.append(a.strip()[:70])
        res[e["sku"]] = sorted(set(hits))[:4]
    return res


def yes(v):
    return "ja" if v else "–"


def render(items, plm_hit, det, src):
    L = ["# Batch-Plan (Trockenlauf, nichts geschrieben)", "", "Die %d neuesten Styles aus den Mails (Inbox-Belege). Spalten: was die Mails liefern / was im PLM schon steht.\n" % len(items)]
    cov = {"Größen": 0, "Farben": 0, "Preis": 0, "Barcode": 0, "UVP": 0, "EK": 0, "Material": 0, "HS-Code": 0}
    plm = {"existiert": 0, "Verpackung leer": 0, "Maße leer": 0, "ohne Techpack": 0, "ohne Hauptmaterial": 0, "ohne Barcode": 0}
    rows = []
    for e in items:
        pi = e["pi"]
        mail = {"Größen": e["sizes"], "Farben": e["colors"], "Preis": e["prices"], "Barcode": core.valid_ean(pi.get("barcode")) and pi.get("barcode"), "UVP": pi.get("uvp"),
                "EK": pi.get("purchase_price"), "Material": pi.get("material"), "HS-Code": pi.get("hs_code")}
        for k, v in mail.items():
            cov[k] += 1 if v else 0
        hit = plm_hit.get(e["sku"])
        d = det.get(hit[1]["id"], {}) if hit else {}
        inf = d.get("info") or {}
        pk = inf.get("packaging") or {}
        pk_set = any(v not in (None, "", 0) for v in pk.values() if not isinstance(v, dict))
        base = d.get("base") or {}
        tps = d.get("tp") or []
        idn = d.get("ident") or []
        cells = [z for v in idn for z in (v.get("sizes") or [])]
        ean_n = sum(1 for z in cells if z.get("barcode")); sku_n = sum(1 for z in cells if z.get("sku"))
        ean_txt = "EAN %d/%d, SKU %d/%d" % (ean_n, len(cells), sku_n, len(cells)) if cells else "keine Identifiers"
        if hit:
            plm["existiert"] += 1
            plm["Verpackung leer"] += 0 if pk_set else 1
            plm["Maße leer"] += 0 if (base.get("measurements") or []) else 1
            plm["ohne Techpack"] += 0 if tps else 1
            plm["ohne Hauptmaterial"] += 0 if inf.get("mainMaterial") else 1
            plm["ohne Barcode"] += 0 if inf.get("barcode") else 1
            plm["EAN je Größe komplett"] = plm.get("EAN je Größe komplett", 0) + (1 if cells and ean_n == len(cells) else 0)
            plm["EAN je Größe teilweise/leer"] = plm.get("EAN je Größe teilweise/leer", 0) + (0 if cells and ean_n == len(cells) else 1)
        status = "NEU" if not hit else ("vorhanden (%s) %s" % (hit[0], hit[1].get("sku")))
        rows.append("| %s | %s | %s | %s | %s | %s | %s |" % (e["sku"], (e["name"] or "")[:34], e["vendor"] + ("" if e["vendor_known"] else " (NEU)"), status,
                                                         ", ".join("%s %s" % (k, yes(v)) for k, v in mail.items() if v), "Verp. %s / Maße %s / Techpack %s / Mat. %s / %s" % (yes(pk_set), yes(base.get("measurements")), yes(tps), yes(inf.get("mainMaterial")), ean_txt) if hit else "–",
                                                         "; ".join(src.get(e["sku"], [])) or "–"))
    n = len(items) or 1
    L += ["## Abdeckung durch die Mails (je Feld: bei wie vielen der %d Styles liefern die Belege den Wert)" % len(items), ""]
    L += ["- %s: %d von %d" % (k, v, len(items)) for k, v in cov.items()]
    L += ["", "## Stand im PLM bei den schon vorhandenen Produkten", ""] + ["- %s: %d" % (k, v) for k, v in plm.items()]
    L += ["", "## Pro Style", "", "| Style | Name | Lieferant | PLM | Aus den Mails | PLM-Stand | Techpack-/Spec-Dateien in Mails |", "|---|---|---|---|---|---|---|"] + rows
    L += ["", "## Was die Auslese heute NICHT liefert (Prompt/Filter)", "",
          "- **Verpackung** (Kartonmaße, Gewicht, Stück/Karton): nicht im Auslese-Schema, kommt aus Packlisten.",
          "- **HS-Code / Ursprungsland**: Feld `hs_code` existiert, Ursprungsland nicht.",
          "- **Maßtabelle (Werte je Größe)** und **Stückliste/Materialdetails**: nicht im Schema; Techpack-Dateien werden bewusst übersprungen (`SKIP_ATTACHMENT_NAMES` enthält tech pack).",
          "- **Ist-Termine, Lieferadresse als Feld, Kartonzahl je Sendung**: nur als Text in Notizen."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25); ap.add_argument("--sheet"); ap.add_argument("--inbox")
    ap.add_argument("--out", default=str(ROOT / "output" / "batch_plan.md"))
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    inbox = daily.resolve_inbox(a.inbox, daily.INTAKE)
    vendors = fetch_all(plm_client.call, "vendors"); products = fetch_all(plm_client.call, "products")
    aliases = json.load(open(daily.INTAKE / "vendor_aliases.json")) if (daily.INTAKE / "vendor_aliases.json").exists() else {}
    style_aliases = json.load(open(daily.INTAKE / "style_aliases.json")) if (daily.INTAKE / "style_aliases.json").exists() else {}
    cands = collect(load_docs(inbox), vendors, aliases, a.n + 30)
    hits_all = {e["sku"]: new_products.existing_style_hit(e["sku"], products, style_aliases) for e in cands}
    def is_test(h):   # vom Skript (Realtest 15.10.) angelegte Produkte tragen den Tag aus-mail; Omar loescht sie
        return bool(h) and "aus-mail" in str(h[1].get("tags") or "").lower()
    skipped_test = [e["sku"] for e in cands if is_test(hits_all[e["sku"]])]
    items = [e for e in cands if not is_test(hits_all[e["sku"]])][:a.n]
    plm_hit = {e["sku"]: hits_all[e["sku"]] for e in items if hits_all[e["sku"]]}
    print("Testobjekte uebersprungen:", ", ".join(skipped_test) or "keine")
    det = fetch_details([h[1]["id"] for h in plm_hit.values()])
    import datetime
    src = source_docs(a.sheet, items, datetime.datetime(2026, 10, 1))
    out = render(items, plm_hit, det, src)
    Path(a.out).write_text(out); print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
