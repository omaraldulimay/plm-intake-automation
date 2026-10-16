"""Neue Collections + Kategorien anlegen (Omar 16.10.: eigene Kategorien fuer Sets, Kleider/Roecke, Bademode, Unterwaesche, Badelatschen).

  python3 -m plm_intake.new_categories            TROCKENLAUF: zeigt, was angelegt wuerde
  python3 -m plm_intake.new_categories --apply    legt je eine Collection mit EINER Kategorie "<CODE> – <Name>" an (wie die vorhandene Struktur: Collection = Produkttyp), ergaenzt den Code in der
                                                  Auswahlliste des Feldes Kategorie-Code (falls es eine Auswahlliste ist) und liest alles zurueck
Idempotent: gibt es die Collection/Kategorie schon, wird nichts doppelt angelegt. Nie loeschen/umbenennen."""
import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NEW = [("Sets / Anzüge", "SET – Set / Trainingsanzug"), ("Kleider / Röcke", "DRS – Kleid / Rock"), ("Bademode", "SWM – Bademode (Bikini, Badeanzug)"),
       ("Unterwäsche", "UWE – Unterwäsche (Slip, String, Body)"), ("Badelatschen", "SLD – Badelatschen / Slides")]
KATCODE_KEY = "mv6jnln121cc81_kategorie_code"

JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v }); const V = n => ({ kind: 'Variable', name: N(n) });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: args || [], selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const A = (n, v) => ({ kind: 'Argument', name: N(n), value: v });
  const T = (n, nn) => nn ? { kind: 'NonNullType', type: { kind: 'NamedType', name: N(n) } } : { kind: 'NamedType', name: N(n) };
  const VD = l => l.map(x => ({ kind: 'VariableDefinition', variable: V(x[0]), type: x[1] }));
  const OBJ = fs => ({ kind: 'ObjectValue', fields: fs.map(f => ({ kind: 'ObjectField', name: N(f[0]), value: f[1] })) });
  const q = (vars, sel) => ({ kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: VD(vars), selectionSet: { kind: 'SelectionSet', selections: [sel] } }] });
  const m = (vars, sel) => ({ kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: VD(vars), selectionSet: { kind: 'SelectionSet', selections: [sel] } }] });
  const c = window.__APOLLO_CLIENT__; const out = { steps: [] };
  const MODE = '__MODE__', SPEC = __SPEC__, CODES = __CODES__;
  const cols = (await c.query({ query: q([['limit', T('Int')]], F('collections', [A('limit', V('limit'))], [F('id'), F('name')])), variables: { limit: 500 }, fetchPolicy: 'no-cache' })).data.collections;
  const cats = (await c.query({ query: q([['after', T('Int')], ['limit', T('Int')]], F('categories', [A('after', V('after')), A('limit', V('limit'))], [F('id'), F('name'), F('collectionId')])), variables: { after: 0, limit: 1000 }, fetchPolicy: 'no-cache' })).data.categories;
  for (const [cn, catn, guid1, guid2] of SPEC) {
    let col = cols.find(x => x.name === cn); let step = { collection: cn, category: catn };
    if (!col && MODE === 'apply') {
      const r = await c.mutate({ mutation: m([['name', T('String', 1)], ['guid', T('String', 1)]], F('createCollection', [A('createCollectionInput', OBJ([['name', V('name')], ['guid', V('guid')]]))], [F('id'), F('name')])), variables: { name: cn, guid: guid1 }, errorPolicy: 'all' });
      col = r.data && r.data.createCollection; step.collection_created = !!col; if (!col) { step.err = (r.errors || []).map(e => e.message.slice(0, 160)); out.steps.push(step); break; }
    }
    step.collection_id = col && col.id;
    if (col && !cats.find(x => x.collectionId === col.id && x.name === catn) && MODE === 'apply') {
      const r = await c.mutate({ mutation: m([['guid', T('String', 1)], ['name', T('String', 1)], ['parent_collection', T('String', 1)]], F('createCategory', [A('createCategoryInput', OBJ([['name', V('name')], ['parent_collection', V('parent_collection')], ['guid', V('guid')]]))], [F('id'), F('name')])), variables: { name: catn, parent_collection: col.id, guid: guid2 }, errorPolicy: 'all' });
      step.category_created = !!(r.data && r.data.createCategory); if (!step.category_created) step.err = (r.errors || []).map(e => e.message.slice(0, 160));
    } else if (col) step.category_exists = !!cats.find(x => x.collectionId === col.id && x.name === catn);
    out.steps.push(step);
  }
  // Auswahlliste Kategorie-Code
  const fo = (await c.query({ query: { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', selectionSet: { kind: 'SelectionSet', selections: [F('getFilterOptions', [], [F('customFields', [], [F('id'), F('dbKey'), F('fieldType'), F('enumValues')])])] } }] }, fetchPolicy: 'no-cache' })).data.getFilterOptions.customFields;
  const f = fo.find(x => x.dbKey === '__KEY__'); out.field = f ? { id: f.id, type: f.fieldType, n: (f.enumValues || []).length, missing: CODES.filter(x => !(f.enumValues || []).includes(x)) } : null;
  if (f && MODE === 'apply' && (f.fieldType || '').toLowerCase().includes('enum') || f && (f.enumValues || []).length) {
    out.added = [];
    for (const code of out.field.missing) { if (MODE !== 'apply') break;
      const r = await c.mutate({ mutation: m([['id', T('String', 1)], ['value', T('String', 1)]], F('addCustomFieldOption', [A('id', V('id')), A('value', V('value'))], [F('id'), F('enumValues')])), variables: { id: f.id, value: code }, errorPolicy: 'all' });
      out.added.push({ code, ok: !!(r.data && r.data.addCustomFieldOption), err: (r.errors || []).map(e => e.message.slice(0, 120)) }); }
  }
  return out;
})()'''


def run(mode):
    from plm_intake import barcodes as bc
    spec = [[c, k, str(uuid.uuid4()), str(uuid.uuid4())] for c, k in NEW]
    codes = [k.split(" ")[0] for _, k in NEW]
    js = JS.replace("__MODE__", mode).replace("__SPEC__", json.dumps(spec, ensure_ascii=False)).replace("__CODES__", json.dumps(codes)).replace("__KEY__", KATCODE_KEY)
    return bc.run_js(js)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    res = run("apply" if a.apply else "dry")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.apply:
        again = run("dry")
        bad = [s for s in again["steps"] if not (s.get("collection_id") and s.get("category_exists"))]
        print("Rueckpruefung:", "ALLES vorhanden (%d Collections mit Kategorie)" % len(again["steps"]) if not bad else "ABWEICHUNG %s" % bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
