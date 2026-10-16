"""Live-Kontext aus dem PLM lesen (nur GET).
Die Listen verhalten sich verschieden: /products liefert {data, pagination}, /orders eine nackte Liste, die per page/limit seitenweise kommt
(ohne Metadaten), /vendors ignoriert page/limit und liefert immer alles. fetch_all behandelt alle Faelle und dedupliziert nach id."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def fetch_all(call, path, limit=100, max_pages=60):
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        st, r = call("GET", path, page=page, limit=limit)
        if st != 200:
            raise RuntimeError("GET %s Seite %d -> HTTP %s" % (path, page, st))
        rows = r if isinstance(r, list) else (r.get("data") or [])
        new = [x for x in rows if x.get("id") not in seen]
        for x in new:
            seen.add(x.get("id"))
        out += new
        pages = None if isinstance(r, list) else (r.get("pagination") or {}).get("pages")
        if not new or (pages is not None and page >= pages) or (pages is None and len(rows) < limit):
            break
    else:
        raise RuntimeError("GET %s: mehr als %d Seiten, Abbruch" % (path, max_pages))
    return out


def load_context(call=None):
    if call is None:
        import plm_client
        call = plm_client.call
    return {"vendors": fetch_all(call, "vendors"), "products": fetch_all(call, "products"), "orders": fetch_all(call, "orders")}


def add_po_numbers(ctx, runner=None):
    """Die REST-Orderliste liefert KEINE PO-Nummer (poNumber = None). Ohne sie greift die Zuordnung nur ueber den Titel. Hier werden die Nummern ueber das
    eingeloggte Browser-Profil (GraphQL getOrderById) nachgeladen und in ctx["orders"][i]["poNumber"] eingetragen. Fehler -> Kontext bleibt unveraendert (nur Titel-Zuordnung)."""
    import json
    import subprocess
    import tempfile
    ids = [o["id"] for o in ctx.get("orders") or [] if not o.get("poNumber")]
    if not ids:
        return 0
    js = ("(async()=>{const out={};for(const id of %s){try{const r=await window.__fetchOrder(id);if(r&&r.d)out[id]={p:r.d.poNumber||null,n:r.d.notes||''};}catch(e){}}return out;})()" % json.dumps(ids))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    try:
        if runner is None:
            r = subprocess.run(["node", str(Path(__file__).resolve().parent / "browser" / "run_in_plm.js"), f.name], capture_output=True, text=True,
                               cwd=str(Path(__file__).resolve().parent / "browser"), timeout=300)
            if r.returncode:
                return 0
            data = json.loads(r.stdout)
        else:
            data = runner(js)
    except Exception:
        return 0
    n = 0
    for o in ctx["orders"]:
        d = data.get(o["id"])
        if d:
            if d.get("p"):
                o["poNumber"] = d["p"]; n += 1
            o["_notes"] = d.get("n", "")
    return n


def fetch_order_details(ids, runner=None):
    """Vollstaendige Orders (Positionen mit Produkt-/Varianten-IDs, Mengen) per Browser-GraphQL: {id: order}. Fehler -> {}."""
    import json
    import subprocess
    import tempfile
    ids = sorted(set(ids))
    if not ids:
        return {}
    js = "(async()=>{const out={};for(const id of %s){try{const r=await window.__fetchOrder(id);if(r&&r.d)out[id]=r.d;}catch(e){}}return out;})()" % json.dumps(ids)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    try:
        if runner is None:
            r = subprocess.run(["node", str(Path(__file__).resolve().parent / "browser" / "run_in_plm.js"), f.name], capture_output=True, text=True,
                               cwd=str(Path(__file__).resolve().parent / "browser"), timeout=300)
            return json.loads(r.stdout) if r.returncode == 0 else {}
        return runner(js)
    except Exception:
        return {}
