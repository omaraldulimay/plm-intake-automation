"""Techpacks/Specs aus den Mail-Anhaengen als ECHTE Dateien (Lifecycle-Speicher) an die Produkte haengen.

  python3 -m plm_intake.techpack_upload            TROCKENLAUF: output/phase2/B15/upload_plan.md
  python3 -m plm_intake.techpack_upload --apply    laedt hoch, liest je Produkt zurueck
Zuordnung: plm_intake.techpack_map (exakt / Kunde Y-Regel / belegte Alias-Tabelle / Inhalt). Je Produkt jeder Dateiname nur einmal (neueste Fassung),
schon vorhandene echte Datei gleichen Namens wird uebersprungen (Drive-Links zaehlen nicht als vorhanden). Nie loeschen. Max. 20 MB je Datei."""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import techpack_map as tm  # noqa: E402
from plm_intake.techpack_links import ANH, MIME, display_name, load_sources  # noqa: E402

OUT = ROOT / "output" / "phase2" / "B15"
MAXB = 20 * 1024 * 1024
HELP = (ROOT / "plm_intake" / "browser" / "upload_helpers.js")

READ_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v }), V = n => ({ kind: 'Variable', name: N(n) });
  const F = (n, sel, args) => ({ kind: 'Field', name: N(n), arguments: args || [], selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const q = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: [{ kind: 'VariableDefinition', variable: V('p'), type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N('String') } } }],
    selectionSet: { kind: 'SelectionSet', selections: [F('productAttachments', [F('id'), F('name'), F('fileUrl')], [{ kind: 'Argument', name: N('productId'), value: V('p') }])] } }] };
  const out = {};
  for (const p of __PIDS__) { const r = await window.__APOLLO_CLIENT__.query({ query: q, variables: { p }, fetchPolicy: 'no-cache', errorPolicy: 'all' }); out[p] = (r.data && r.data.productAttachments) || null; }
  return out;
})()'''


def real(a):
    return not str(a.get("fileUrl") or "").startswith("http")   # Drive-Link = http..., Lifecycle-Datei = Speicher-Schluessel


def plan(products):
    al = tm.load_aliases()
    best = {}
    for s in load_sources():
        name, path = display_name(s["datei"]), ANH / s["datei"]
        if not path.exists() or path.stat().st_size > MAXB:
            continue
        r = tm.resolve(name, products, al)
        if not r[0]:
            r = tm.resolve(name, products, al, content=tm.file_text(path))
        for p in r[0]:
            k = (p["id"], name.lower())
            it = {"productId": p["id"], "sku": p["sku"], "name": name, "datei": s["datei"], "datum": s.get("datum") or "", "methode": r[1]}
            if k not in best or (it["datum"], it["datei"]) > (best[k]["datum"], best[k]["datei"]):
                best[k] = it
    return list(best.values())


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); a = ap.parse_args(argv)
    import plm_client
    from plm_intake import barcodes as bc
    from plm_intake.context import fetch_all
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = plan(fetch_all(plm_client.call, "products"))
    ex = bc.run_js(READ_JS.replace("__PIDS__", json.dumps(sorted({j["productId"] for j in jobs}))))
    todo = [j for j in jobs if ex.get(j["productId"]) is not None and not any(real(x) and (x.get("name") or "").lower() == os.path.splitext(j["name"])[0].lower() for x in ex[j["productId"]])]
    rep = ["# Techpacks/Specs als Datei hochladen (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Zuordnungen: %d | schon als Datei vorhanden: %d | NEU: %d" % (len(jobs), len(jobs) - len(todo), len(todo)), "",
           "| SKU | Methode | Datei |", "|---|---|---|"] + ["| %s | %s | %s |" % (j["sku"], j["methode"], j["name"][:80]) for j in todo]
    if a.apply:
        helper = HELP.read_text()
        ok, bad = 0, []
        for j in todo:   # einzeln: Base64 je Datei bleibt klein
            ext = os.path.splitext(j["name"])[1].lower()
            b64 = base64.b64encode((ANH / j["datei"]).read_bytes()).decode()
            js = "(async()=>{" + helper + "\nreturn await window.__uploadProductFile(%s,%s,%s,'%s');})()" % (json.dumps(j["productId"]), json.dumps(j["name"]), json.dumps(MIME.get(ext, "application/octet-stream")), b64)
            r = bc.run_js(js)
            if isinstance(r, dict) and r.get("ok"):
                ok += 1
            else:
                bad.append("%s %s: %s" % (j["sku"], j["name"], str(r)[:150]))
        after = bc.run_js(READ_JS.replace("__PIDS__", json.dumps(sorted({j["productId"] for j in todo}))))
        miss = [j for j in todo if not any(real(x) and (x.get("name") or "").lower() == os.path.splitext(j["name"])[0].lower() for x in after.get(j["productId"]) or [])]
        rep += ["", "## Ergebnis", "- hochgeladen: %d, Fehler: %d" % (ok, len(bad))] + ["  - " + b for b in bad[:30]]
        rep += ["- Rueckpruefung: %s" % ("alle %d als Datei am Produkt" % len(todo) if not miss else "FEHLEN %d: %s" % (len(miss), [m["sku"] + " " + m["name"] for m in miss[:15]]))]
    (OUT / "upload_plan.md").write_text("\n".join(rep))
    print("\n".join(rep[:6] + rep[-4:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
