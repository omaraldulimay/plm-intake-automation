"""Collection umbenennen (nur der Name, Produkte und Kategorien bleiben).

  python3 -m plm_intake.rename_collection "Outerwear" "Jacken"            TROCKENLAUF: zeigt Collection, Anzahl Produkte, Zielname
  python3 -m plm_intake.rename_collection "Outerwear" "Jacken" --apply    benennt per updateCollection um und liest zurueck (Name neu, Produktanzahl gleich)
Nur wenn die Collection genau einmal existiert und der Zielname noch nicht vergeben ist. Nie loeschen."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v }); const V = n => ({ kind: 'Variable', name: N(n) });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: args || [], selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const A = (n, v) => ({ kind: 'Argument', name: N(n), value: v });
  const T = (n, nn) => nn ? { kind: 'NonNullType', type: { kind: 'NamedType', name: N(n) } } : { kind: 'NamedType', name: N(n) };
  const VD = l => l.map(x => ({ kind: 'VariableDefinition', variable: V(x[0]), type: x[1] }));
  const OBJ = fs => ({ kind: 'ObjectValue', fields: fs.map(f => ({ kind: 'ObjectField', name: N(f[0]), value: f[1] })) });
  const c = window.__APOLLO_CLIENT__; const MODE = '__MODE__', FROM = __FROM__, TO = __TO__; const out = {};
  const list = async () => (await c.query({ query: { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: VD([['limit', T('Int')]]),
    selectionSet: { kind: 'SelectionSet', selections: [F('collections', [A('limit', V('limit'))], [F('id'), F('name'), F('productsCount')])] } }] }, variables: { limit: 500 }, fetchPolicy: 'no-cache' })).data.collections;
  const cols = await list();
  const src = cols.filter(x => x.name === FROM), dst = cols.filter(x => x.name === TO);
  out.src = src; out.dst = dst;
  if (src.length !== 1 || dst.length) { out.skip = 'Quelle nicht genau einmal oder Zielname schon vergeben'; return out; }
  if (MODE === 'apply') {
    const r = await c.mutate({ mutation: { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: VD([['id', T('String', 1)], ['name', T('String', 1)]]),
      selectionSet: { kind: 'SelectionSet', selections: [F('updateCollection', [A('updateCollectionInput', OBJ([['id', V('id')], ['name', V('name')]]))], [F('id'), F('name'), F('productsCount')])] } }] },
      variables: { id: src[0].id, name: TO }, errorPolicy: 'all' });
    out.result = r.data && r.data.updateCollection; out.err = (r.errors || []).map(e => e.message.slice(0, 160));
    const after = await list(); out.after = after.filter(x => x.id === src[0].id);
  }
  return out;
})()'''


def run(frm, to, mode):
    from plm_intake import barcodes as bc
    js = JS.replace("__MODE__", mode).replace("__FROM__", json.dumps(frm, ensure_ascii=False)).replace("__TO__", json.dumps(to, ensure_ascii=False))
    return bc.run_js(js)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("von"); ap.add_argument("nach"); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    res = run(a.von, a.nach, "apply" if a.apply else "dry")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if res.get("skip"):
        return 1
    if a.apply:
        before = res["src"][0]; after = (res.get("after") or [{}])[0]
        ok = after.get("name") == a.nach and after.get("productsCount") == before.get("productsCount") and not res.get("err")
        print("Rueckpruefung:", "OK, Name '%s', %s Produkte unveraendert" % (after.get("name"), after.get("productsCount")) if ok else "ABWEICHUNG %s" % res)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
