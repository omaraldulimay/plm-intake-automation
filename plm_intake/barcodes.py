"""EAN + SKU je Farbe x Groesse ins PLM (Identifiers) aus Plenty (logistics.skus).

  python3 -m plm_intake.barcodes [--n 25] [--skus A,B]            TROCKENLAUF (Standard): Plan + Bericht output/barcodes/plan_<Zeit>.md, schreibt NICHTS
  python3 -m plm_intake.barcodes --apply [--n 25] [--skus A,B]    schreibt per importIdentifierValues (nur LEERE Zellen, nie ueberschreiben) und liest alles zurueck

Regeln: EAN muss 13 Stellen mit gueltiger Pruefziffer haben; eine EAN darf im PLM nirgends sonst vorkommen; Farbe und Groesse muessen eindeutig passen; vorhandene
abweichende Werte (EAN/SKU) werden nie ueberschrieben (Konflikt -> Bericht); die SKU je Groesse ist die Plenty-Variantennummer (z. B. AL29008-A1).
Fehlt im PLM die Farb-/Groessenzelle, die Plenty kennt, steht sie als 'Zelle fehlt' im Bericht (Variante muss erst angelegt werden).
Plenty wird nur gelesen (psql, read-only)."""
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
from plm_intake import batch_plan, core, daily, new_products  # noqa: E402

BROWSER = ROOT / "plm_intake" / "browser"
OUT = ROOT / "output" / "barcodes"
PSQL = "/opt/homebrew/bin/psql"
CONN = "host=smilo-bi.cxar5ovsxcrg.eu-west-1.rds.amazonaws.com dbname=postgres user=smilo_postgr sslmode=verify-full sslrootcert=db/global-bundle.pem"
MAX_WRITE_PER_RUN = int(__import__("os").environ.get("PLM_MAX_ROWS", 600))   # Sicherheitsgrenze (Standard 600): mehr EAN-Schreibungen in einem Lauf braucht eine bewusste Entscheidung; der Nachtlauf setzt PLM_MAX_ROWS


FAMILY = {"schwarz": "black", "black": "black", "weiss": "white", "weiß": "white", "white": "white", "grau": "grey", "grey": "grey", "gray": "grey", "blau": "blue", "blue": "blue",
          "navy": "blue", "marine": "blue", "marineblau": "blue", "braun": "brown", "brown": "brown", "rot": "red", "red": "red", "bordeaux": "red", "wine": "red", "burgundy": "red",
          "gruen": "green", "grün": "green", "green": "green", "olive": "green", "gelb": "yellow", "yellow": "yellow", "beige": "beige", "sand": "beige", "creme": "beige", "cream": "beige", "ecru": "beige",
          "flieder": "lilac", "lilac": "lilac", "lavender": "lilac", "lila": "lilac", "violett": "lilac", "purple": "lilac", "rosa": "pink", "pink": "pink", "orange": "orange",
          "tuerkis": "turquoise", "türkis": "turquoise", "turquoise": "turquoise", "teal": "turquoise", "anthrazit": "anthracite", "anthrazite": "anthracite", "anthracite": "anthracite",
          "charcoal": "anthracite", "taupe": "taupe", "terrakotta": "terracotta", "terracotta": "terracotta", "creamy": "beige", "royal": "royalblue", "hellgrau": "grey", "dunkelblau": "blue", "dunkelgrün": "green", "dunkelgruen": "green"}
SHADE = {"dunkel": "dark", "dark": "dark", "hell": "light", "light": "light", "navy": "dark", "marine": "dark", "marineblau": "dark", "hellgrau": "light", "dunkelblau": "dark", "dunkelgrün": "dark", "dunkelgruen": "dark"}
EXTRA = {"melange", "leo", "neon", "pastel", "metallic"}


def colour_key(name):
    """Vergleichsschluessel fuer Farbnamen DE/EN/Schreibweisen: (Farbfamilie, Helligkeit, Zusatz). 'Dunkel Blau' == 'Dark Blue' == 'Dunkelblau', 'Major Brown' == 'Braun',
    'Flieder / Nirvana 17-3808 TCX' == 'Flieder', 'AN-43 Flared Leggings - Bordeaux' == 'Bordeaux'. Unbekannte Farbworte -> Fallback auf core.norm_color."""
    t = str(name or "")
    if " / " in t:
        t = t.split(" / ")[0]
    if re.search(r"\s[\-–]\s", t):
        t = re.split(r"\s[\-–]\s", t)[-1]
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\d{2}-\d{4}\s?[A-Za-z]{0,3}", " ", t)
    words = re.findall(r"[a-zäöüß]+", t.lower())
    extras = set()
    cut = next((i for i, w in enumerate(words) if w in ("piping", "paspel", "kontrast", "contrast")), None)
    if cut is not None:   # 'Hellblau piping white': Farbe = Teil VOR 'piping'; die Farbe dahinter ist nur der Zusatz (sonst wird 'white' faelschlich zur Hauptfarbe)
        if cut + 1 < len(words):
            extras.add("piping_" + (FAMILY.get(words[cut + 1]) or words[cut + 1]))
        words = words[:cut]
    fam = shade = None
    for w in words:
        w2 = w.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue") if w not in FAMILY else w
        f = FAMILY.get(w) or FAMILY.get(w2)
        sh = SHADE.get(w) or SHADE.get(w2)
        if not f:   # Zusammensetzungen: hellblau, dunkelgruen, hellbraun ...
            for pre, shd in (("dunkel", "dark"), ("hell", "light")):
                if w.startswith(pre) and (FAMILY.get(w[len(pre):]) or FAMILY.get(w2[len(pre):])):
                    f = FAMILY.get(w[len(pre):]) or FAMILY.get(w2[len(pre):]); sh = sh or shd
        if f and not fam:
            fam = f
        if sh and not shade:
            shade = sh
        if w in EXTRA:
            extras.add(w)
    if not fam:   # zusammengeschriebene Mischformen wie 'dunkelblau', 'hellgrau'
        j = "".join(words)
        for k, f in FAMILY.items():
            if k in j and len(k) >= 4:
                fam = f; shade = shade or ("dark" if "dunkel" in j else "light" if "hell" in j else None); break
    if not fam:
        return ("?", core.norm_color(name), ())
    return (fam, shade, tuple(sorted(extras)))


def ean_ok(e):
    return bool(re.fullmatch(r"\d{13}", str(e or ""))) and core.valid_ean(e)


def norm_size(s):
    s = re.sub(r"\s+", "", str(s or "").upper())
    s = re.sub(r"(EU|EUR)$", "", s) if re.match(r"^\d", s) else s   # Schuhgroessen '38 EU' == '38'
    return {"XXS": "XXS", "2XL": "XXL", "XXXL": "3XL", "3XL": "3XL", "OS": "ONESIZE", "ONE": "ONESIZE", "ONESIZE": "ONESIZE", "UNI": "ONESIZE", "TU": "ONESIZE"}.get(s, s)


def parse_attrs(a):
    d = {}
    for part in str(a or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            k = k.strip().lower()
            if re.search(r"colou?r|farbe", k):   # 'Couch color', 'Farbe' ...
                k = "color"
            elif re.search(r"size|gr(ö|oe|o)(ß|ss)e", k):   # 'Größe', 'Groesse' ...
                k = "size"
            d[k] = v.strip()
    return d


def plenty_rows(skus):
    """Plenty-Zeilen je Produkt-SKU: {sku_norm: [{variation_no, color, size, ean}]} (read-only, psql). Zuordnung: Teil von variation_no vor dem Farbbuchstaben+Nummer == Produkt-SKU."""
    out = {}
    if not skus:
        return out
    sql = ("select variation_no, attributes, coalesce(ean,'') from logistics.skus where variation_no ~ '-[A-Z]+[0-9]+$' and regexp_replace(upper(regexp_replace(variation_no,'-[A-Z]+[0-9]+$','')),'[^A-Z0-9]','','g') in (%s)"
           % ",".join("'%s'" % re.sub(r"[^A-Z0-9]", "", str(s).upper()) for s in skus))   # Bindestriche egal: PLM 'AN43' == Plenty 'AN-43'
    r = subprocess.run([PSQL, CONN, "-At", "-F", "\t", "-c", sql], capture_output=True, text=True, cwd=str(ROOT), timeout=300,
                       env=dict(__import__("os").environ, PGOPTIONS="-c default_transaction_read_only=on"))
    if r.returncode:
        raise RuntimeError("Plenty-Abfrage gescheitert: " + r.stderr[-200:])
    for line in r.stdout.splitlines():
        vn, attrs, ean = line.split("\t")
        a = parse_attrs(attrs)
        style = re.sub(r"-[A-Z]+[0-9]+$", "", vn)
        out.setdefault(core.norm(style), []).append({"variation_no": vn, "color": a.get("color", ""), "size": a.get("size", ""), "ean": ean})
    return out


def plan_product(prows, cells, other_eans):
    """prows: Plenty-Zeilen des Produkts. cells: PLM-Zellen [{variant, color, size, barcode, sku}] (variant = Variantenname, color = Bibliotheksfarbname).
    other_eans: EANs, die an ANDEREN Produkten im PLM stehen. -> dict(rows, conflicts, missing_cells, bad_ean, dup, unmatched)."""
    by_cell = {}
    for c in cells:
        for cn in {colour_key(c.get("variant")), colour_key(c.get("color"))} - {("?", "", ())}:
            by_cell.setdefault((cn, norm_size(c["size"])), []).append(c)
    rows, conflicts, missing, bad, dup = [], [], [], [], []
    seen_ean = {}
    for p in prows:
        key = (colour_key(p["color"]), norm_size(p["size"]))
        hit = by_cell.get(key) or []
        hit = list({id(h): h for h in hit}.values())
        if not ean_ok(p["ean"]):
            bad.append((p["variation_no"], p["ean"])); continue
        if len(hit) != 1:
            missing.append((p["variation_no"], p["color"], p["size"], "keine Zelle" if not hit else "%d Zellen passen" % len(hit))); continue
        c = hit[0]
        if p["ean"] in other_eans:
            dup.append((p["variation_no"], p["ean"], other_eans[p["ean"]])); continue
        if p["ean"] in seen_ean:
            dup.append((p["variation_no"], p["ean"], "doppelt in Plenty: " + seen_ean[p["ean"]])); continue
        seen_ean[p["ean"]] = p["variation_no"]
        row = {"variantName": c["variant"], "sizeTitle": c["size"], "identifierId": c.get("iid"), "sizeId": c.get("sid"), "barcode": None, "sku": None}
        if c.get("barcode"):
            if c["barcode"] != p["ean"]:
                conflicts.append((p["variation_no"], "EAN im PLM %s != Plenty %s" % (c["barcode"], p["ean"])))
        else:
            row["barcode"] = p["ean"]
        if c.get("sku"):
            if c["sku"] != p["variation_no"]:
                conflicts.append((p["variation_no"], "SKU im PLM %s != Plenty %s" % (c["sku"], p["variation_no"])))
        else:
            row["sku"] = p["variation_no"]
        if row["barcode"] or row["sku"]:
            rows.append(row)
    targets = {}
    for r in rows:
        targets.setdefault((r["identifierId"], r["sizeId"]), []).append(r)
    clash = {k for k, v in targets.items() if len(v) > 1}
    if clash:   # zwei Plenty-Zeilen wollen dieselbe Zelle: keine schreiben, Mensch klaert
        for k in clash:
            for r in targets[k]:
                missing.append(("%s/%s" % (r["variantName"], r["sizeTitle"]), "", "", "Plenty-Kollision: mehrere Zeilen fuer dieselbe Zelle"))
        rows = [r for r in rows if (r["identifierId"], r["sizeId"]) not in clash]
    plm_cells_hit = {(r["variantName"], r["sizeTitle"]) for r in rows}
    unmatched = [c for c in cells if not c.get("barcode") and (c["variant"], c["size"]) not in plm_cells_hit]
    return {"rows": rows, "conflicts": conflicts, "missing": missing, "bad_ean": bad, "dup": dup, "unmatched_plm_cells": unmatched}


READ_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: (args || []).map(a => ({ kind: 'Argument', name: N(a[0]), value: a[1] })), selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const V = n => ({ kind: 'Variable', name: N(n) });
  const T = (n, nn) => nn ? { kind: 'NonNullType', type: { kind: 'NamedType', name: N(n) } } : { kind: 'NamedType', name: N(n) };
  const c = window.__APOLLO_CLIENT__; const out = {};
  const q = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: [{ kind: 'VariableDefinition', variable: V('productId'), type: T('ID', 1) }],
    selectionSet: { kind: 'SelectionSet', selections: [F('listIdentifiers', [['productId', V('productId')]], [F('id'), F('productVariant', [], [F('id'), F('name'), F('colorData', [], [F('name')])]), F('sizes', [], [F('id'), F('title'), F('barcode'), F('sku')])])] } }] };
  for (const id of __IDS__) {
    try { const r = await c.query({ query: q, variables: { productId: id }, fetchPolicy: 'no-cache', errorPolicy: 'all' }); out[id] = r.data ? r.data.listIdentifiers : null; if (r.errors && r.errors.length) out[id + '_err'] = r.errors[0].message.slice(0, 120); }
    catch (e) { out[id + '_err'] = String(e.message).slice(0, 120); }
  }
  return out;
})()'''

WRITE_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: (args || []).map(a => ({ kind: 'Argument', name: N(a[0]), value: a[1] })), selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const V = n => ({ kind: 'Variable', name: N(n) });
  const T = (n, nn) => nn ? { kind: 'NonNullType', type: { kind: 'NamedType', name: N(n) } } : { kind: 'NamedType', name: N(n) };
  const LT = { kind: 'NonNullType', type: { kind: 'ListType', type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N('ImportIdentifierValuesRowInput') } } } };
  const doc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation',
    variableDefinitions: [{ kind: 'VariableDefinition', variable: V('productId'), type: T('ID', 1) }, { kind: 'VariableDefinition', variable: V('rows'), type: LT }, { kind: 'VariableDefinition', variable: V('overwriteExisting'), type: T('Boolean') }],
    selectionSet: { kind: 'SelectionSet', selections: [F('importIdentifierValues', [['productId', V('productId')], ['rows', V('rows')], ['overwriteExisting', V('overwriteExisting')]],
      [F('updated'), F('skipped'), F('failed'), F('errors', [], [F('variantName'), F('sizeTitle'), F('barcode'), F('sku'), F('error')])])] } }] };
  const c = window.__APOLLO_CLIENT__; const out = [];
  for (const job of __JOBS__) {
    try { const r = await c.mutate({ mutation: doc, variables: { productId: job.id, rows: job.rows, overwriteExisting: __OVERWRITE__ }, errorPolicy: 'all' });
          out.push({ id: job.id, sku: job.sku, res: r.data && r.data.importIdentifierValues, err: (r.errors || []).map(e => e.message.slice(0, 160)) }); }
    catch (e) { out.push({ id: job.id, sku: job.sku, fatal: String(e.message).slice(0, 200) }); break; }   // bei Fehler sofort stoppen
  }
  return out;
})()'''


def run_js(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=1800)
    if r.returncode:
        raise RuntimeError("Browser-Lauf gescheitert: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout)


def cells_of(ident):
    out = []
    for v in ident or []:
        pv = v.get("productVariant") or {}
        for z in v.get("sizes") or []:
            out.append({"variant": pv.get("name"), "color": (pv.get("colorData") or {}).get("name"), "size": z.get("title"), "barcode": z.get("barcode") or "", "sku": z.get("sku") or "",
                        "iid": v.get("id"), "sid": z.get("id")})
    return out


def real_products(products):
    """Echte Produkte (ohne vom Skript angelegte Testobjekte), neu -> alt nach Anlagedatum (stabile Reihenfolge fuer Batches)."""
    ok = [p for p in products if "aus-mail" not in str(p.get("tags") or "").lower() and p.get("sku")
          and not re.match(r"(?i)zz", str(p.get("sku"))) and not re.match(r"(?i)zz", str(p.get("name")))]   # ZZ-... = Testobjekte (Omar loescht sie)
    return sorted(ok, key=lambda p: (str(p.get("createdAt") or ""), str(p.get("id"))), reverse=True)


def select_products(n, skus, vendors, products, all_products=False, offset=0, tag=None):
    """Batch-Produkte: --skus, oder --all (alle echten PLM-Produkte nach Aktualitaet, ab --offset), sonst die n neuesten Styles aus den Mails (vorhandene PLM-Produkte, ohne Testobjekte)."""
    if tag:   # alle Produkte mit diesem Tag (z. B. plenty-import), neu -> alt
        return [p for p in real_products(products) if tag.lower() in str(p.get("tags") or "").lower()][offset:offset + n]
    if all_products:
        return real_products(products)[offset:offset + n]
    if skus:
        wanted = {core.norm(x) for x in str(skus).split(",")}
        return [p for p in products if core.norm(p.get("sku")) in wanted]
    aliases = json.load(open(daily.INTAKE / "vendor_aliases.json")) if (daily.INTAKE / "vendor_aliases.json").exists() else {}
    style_aliases = json.load(open(daily.INTAKE / "style_aliases.json")) if (daily.INTAKE / "style_aliases.json").exists() else {}
    cands = batch_plan.collect(batch_plan.load_docs(daily.resolve_inbox(None, daily.INTAKE)), vendors, aliases, n + 30)
    prods, seen = [], set()
    for e in cands:
        h = new_products.existing_style_hit(e["sku"], products, style_aliases)
        if h and h[0] in ("exakt", "alias") and "aus-mail" not in str(h[1].get("tags") or "").lower() and h[1]["id"] not in seen:
            prods.append(h[1]); seen.add(h[1]["id"])
        if len(prods) >= n:
            break
    return prods


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25); ap.add_argument("--skus"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true", help="alle echten PLM-Produkte nach Aktualitaet statt der Mail-Styles"); ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--tag", help="nur Produkte mit diesem Tag (z. B. plenty-import)")
    ap.add_argument("--fast", action="store_true", help="EAN-Eindeutigkeit nicht gegen alle PLM-Produkte lesen (das PLM lehnt doppelte EANs selbst ab); fuer grosse Laeufe")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    vendors = fetch_all(plm_client.call, "vendors"); products = fetch_all(plm_client.call, "products")
    prods = select_products(a.n, a.skus, vendors, products, a.all, a.offset, a.tag)
    ids = [p["id"] for p in prods]
    ident = run_js(READ_JS.replace("__IDS__", json.dumps(ids)))
    all_ids = [p["id"] for p in products]
    # EANs ANDERER Produkte (Eindeutigkeit): alle Produkte lesen (nur lesen)
    rest = [] if a.fast else [i for i in all_ids if i not in ident]
    everything = dict(ident); everything.update(run_js(READ_JS.replace("__IDS__", json.dumps(rest))) if rest else {})
    prows = plenty_rows([p.get("sku") for p in prods])
    plans, report = {}, ["# EAN/SKU-Plan (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Stand %s, %d Produkte" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), len(prods)), ""]
    total_rows = 0
    for p in prods:
        cells = cells_of(ident.get(p["id"]))
        others = {}
        for pid, idn in everything.items():
            if pid != p["id"] and not str(pid).endswith("_err"):
                for z in cells_of(idn):
                    if z["barcode"]:
                        others[z["barcode"]] = pid
        pr = prows.get(core.norm(p.get("sku")), [])
        pl = plan_product(pr, cells, others)
        plans[p["id"]] = pl
        total_rows += len(pl["rows"])
        report.append("## %s %s: Plenty %d Zeilen, PLM-Zellen %d -> schreiben %d | Konflikte %d | Zelle fehlt %d | ungueltige EAN %d | Dublette %d" % (
            p.get("sku"), p.get("name", "")[:30], len(pr), len(cells), len(pl["rows"]), len(pl["conflicts"]), len(pl["missing"]), len(pl["bad_ean"]), len(pl["dup"])))
        for x in pl["conflicts"][:5]:
            report.append("- KONFLIKT %s: %s" % x)
        for x in pl["missing"][:8]:
            report.append("- Zelle fehlt im PLM: %s (%s / %s) %s" % x)
        for x in pl["bad_ean"][:3]:
            report.append("- ungueltige EAN: %s %s" % x)
        for x in pl["dup"][:3]:
            report.append("- EAN-Dublette: %s %s (%s)" % x)
        if not pr:
            report.append("- keine Plenty-Zeilen (EANs kommen von Smilodox/Lieferantenliste)")
    report += ["", "Gesamt zu schreiben: %d Zeilen (Limit %d pro Lauf)" % (total_rows, MAX_WRITE_PER_RUN)]
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if a.apply:
        if total_rows > MAX_WRITE_PER_RUN:
            report.append("ABBRUCH: mehr als %d Zeilen in einem Lauf." % MAX_WRITE_PER_RUN); (OUT / ("plan_%s.md" % stamp)).write_text("\n".join(report)); print("\n".join(report)); return 1
        jobs = [{"id": p["id"], "sku": p.get("sku"), "rows": [{k: r[k] for k in ("identifierId", "sizeId", "barcode", "sku") if r.get(k) is not None} for r in plans[p["id"]]["rows"]]} for p in prods if plans[p["id"]]["rows"]]
        res = run_js(WRITE_JS.replace("__JOBS__", json.dumps(jobs)).replace("__OVERWRITE__", "false"))
        report += ["", "## Schreibergebnis"] + ["- %s: %s%s" % (r.get("sku"), json.dumps(r.get("res") or r.get("fatal") or {}, ensure_ascii=False), (" " + str(r["err"])) if r.get("err") else "") for r in res]
        after = run_js(READ_JS.replace("__IDS__", json.dumps([j["id"] for j in jobs])))
        bad = []
        rejected = {}   # vom PLM abgelehnte Zeilen (z. B. SKU/EAN schon anderswo vergeben): nichts geschrieben, kein Fehler der Rueckpruefung, aber im Bericht
        for r_ in res:
            for e in ((r_.get("res") or {}).get("errors") or []):
                rejected.setdefault(r_.get("sku"), set()).add((e.get("variantName"), e.get("sizeTitle")))
        names = {p["id"]: {} for p in prods}
        for j in jobs:
            now = {(z["iid"], z["sid"]): z for z in cells_of(after.get(j["id"]))}
            nm = {(z["iid"], z["sid"]): (z["variant"], z["size"]) for z in cells_of(after.get(j["id"]))}
            for r in j["rows"]:
                if nm.get((r["identifierId"], r["sizeId"])) in rejected.get(j["sku"], set()):
                    continue
                z = now.get((r["identifierId"], r["sizeId"]))
                if not z or (r.get("barcode") and z["barcode"] != r["barcode"]) or (r.get("sku") and z["sku"] != r["sku"]):
                    bad.append((j["sku"], r))
        nrej = sum(len(v) for v in rejected.values())
        report += ["", "## Rueckpruefung", "- %s" % ("ALLES zurueckgelesen und gleich" if not bad else "ABWEICHUNGEN: %s" % bad[:10])]
        if nrej:
            report.append("- vom PLM abgelehnt (nichts geschrieben, Mensch klaert): %d Zeilen bei %s" % (nrej, ", ".join(sorted(rejected))))
        if bad or any(r.get("fatal") or r.get("err") for r in res):
            report.append("ACHTUNG: Abweichung/Fehler, nichts wiederholen, Stand im PLM pruefen.")
    (OUT / ("plan_%s.md" % stamp)).write_text("\n".join(report))
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
