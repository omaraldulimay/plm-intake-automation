"""Phase 2: PO-Status aus Belegen nachziehen (nur vorwaerts, nur mit woertlichem Beleg). Trockenlauf Standard.

  python3 -m plm_intake.phase2_status [--nr 55 --nr 58 ...] [--apply]      ohne --nr: alle echten Orders mit Status Draft

Belege:
 1. Rechnungs-/Packlisten-Extrakte (phase2, doc_kind invoice, gegengeprueft) mit B/L, AWB oder Container -> In Transit
 2. Mails des Lieferanten (output/phase2/<lieferant>/src/mail_*.txt), die PO-Nr./PI-Nr./Stylenummer nennen:
    Sonnet (claude -p) ordnet Meilensteine zu, JEDER mit woertlichem Zitat; das Skript prueft das Zitat im Mailtext.
Meilenstein -> Status: PI_CONFIRMED/DEPOSIT_PAID -> Approved, PRODUCTION_STARTED -> In Production, INSPECTION -> QC,
SHIPPED -> In Transit, DELIVERED -> Complete. Nie rueckwaerts. --apply setzt Status + haengt eine Notizzeile an (Rest unveraendert, Rueckpruefung).
Bericht output/phase2/status_plan.md"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
P2 = ROOT / "output" / "phase2"
BROWSER = ROOT / "plm_intake" / "browser"
ORDER = ["Draft", "Approved", "In Production", "QC", "In Transit", "Complete"]
MS = {"PI_CONFIRMED": "Approved", "DEPOSIT_PAID": "Approved", "PRODUCTION_STARTED": "In Production", "INSPECTION": "QC", "SHIPPED": "In Transit", "DELIVERED": "Complete"}
TEST = re.compile(r"ZZ|-T1|KH-T1", re.I)


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def st(o):
    s = o.get("status")
    return s.get("status") if isinstance(s, dict) else s


def idents(o):
    ids = set()
    if o.get("poNumber"):
        ids.add(str(o["poNumber"]).upper())
    t = re.sub(r"^PO-", "", str(o.get("title") or ""), flags=re.I)
    rest = t.split("-", 1)[1] if "-" in t else t  # Lieferantenkuerzel vorn weg
    if not re.fullmatch(r"20\d\d-\d\d-\d\d-[0-9A-Fa-f]{4}", rest) and re.search(r"\d{3}", rest):
        ids.add(rest.upper())
    for it in o.get("items") or []:
        m = re.match(r"\s*([A-Za-z]{0,6}[-_ ]?\d[\w\-]{2,})", str(it.get("name") or ""))
        if m and len(norm(m.group(1))) >= 5:
            ids.add(m.group(1).upper())
    return {i for i in ids if not re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", i)}


def slug_for(vendor, cfg):
    for s, c in cfg["lieferanten"].items():
        if c["vendor"].lower() == str(vendor or "").lower():
            return s
    return None


def mails_for(slug):
    d = P2 / slug / "src"
    out = []
    for f in sorted(d.glob("mail_*.txt")) if d.exists() else []:
        t = f.read_text(errors="replace")
        dm = re.search(r"^Datum: (.+)$", t, re.M)
        sm = re.search(r"^Betreff: (.+)$", t, re.M)
        th = re.search(r"^Thread-ID: (\S+)", t, re.M)
        out.append({"thread": th.group(1) if th else None, "id": f.stem, "datum": dm.group(1) if dm else "", "betreff": sm.group(1) if sm else "", "text": t})
    return out


def invoice_evidence(slug, ids, min_pieces=0):
    ev = []
    for f in (P2 / slug / "extract").glob("*.json") if slug else []:
        x = json.loads(f.read_text())
        if x.get("doc_kind") != "invoice":
            continue
        chk = P2 / slug / "check" / f.name
        if not chk.exists():
            continue
        inv = x.get("invoice") or {}
        blob = norm(json.dumps(x.get("order") or {}) + str(inv.get("po_ref")))
        pcs = float((x.get("order") or {}).get("pieces") or inv.get("pieces") or 0)
        luft_ok = inv.get("mawb") and pcs >= 0.5 * min_pieces  # AWB allein ist oft nur Musterversand
        if any(norm(i) in blob for i in ids) and (inv.get("bl") or inv.get("container") or luft_ok):
            ev.append({"milestone": "SHIPPED", "datum": inv.get("datum"), "beleg": "Rechnung %s (%s %s)" % (inv.get("nr"), "B/L" if inv.get("bl") else "AWB" if inv.get("mawb") else "Container", inv.get("bl") or inv.get("mawb") or inv.get("container"))})
    return ev


def thread_of(o, slug, mails):
    """Threads der Quellmail(s), aus der die Order angelegt wurde (p2inbox/source.mail_id)."""
    th = set()
    for f in (P2 / slug / "p2inbox").glob("*.json") if slug else []:
        d = json.loads(f.read_text())
        if d.get("po_number") and norm(d["po_number"]) in norm(o["title"]):
            mid = (d.get("source") or {}).get("mail_id")
            th |= {m["thread"] for m in mails if m["id"] == "mail_" + str(mid) and m["thread"]}
    return th


def ask_claude(order, cands):
    snip = []
    for m in cands[:25]:
        body = m["text"].split("----- TEXT -----", 1)[-1]
        snip.append("### MAIL %s | %s | %s\n%s" % (m["id"], m["datum"], m["betreff"], body[:2500]))
    prompt = ("Bestellung %s (Lieferant %s, Kennungen %s). Unten Mails, die diese Kennungen nennen. Bestimme Meilensteine DIESER Bestellung. "
              "Erlaubt: PI_CONFIRMED, DEPOSIT_PAID, PRODUCTION_STARTED, INSPECTION, SHIPPED, DELIVERED. Nur wenn die Mail es klar sagt (keine Plaene/Anfragen/Zukunft). "
              "Antworte NUR mit JSON-Liste [{\"milestone\":..., \"mail\":\"mail_...\", \"datum\":\"YYYY-MM-DD\", \"zitat\":\"woertlich max 200 Zeichen aus der Mail\"}], leer [] wenn nichts sicher.\n\n%s") % (
        order["title"], (order.get("manufacturer") or {}).get("name"), ", ".join(sorted(order["_ids"])), "\n\n".join(snip))
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    r = subprocess.run(["claude", "-p", prompt, "--model", "sonnet"], capture_output=True, text=True, timeout=900, env=env, stdin=subprocess.DEVNULL)
    if r.returncode:
        raise RuntimeError("claude -p: " + (r.stdout + r.stderr)[-200:])
    m = re.search(r"\[.*\]", r.stdout, re.S)
    return json.loads(m.group(0)) if m else []


def run_js(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=900)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])
    return json.loads(r.stdout)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--nr", type=int, action="append", default=[])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    cfg = json.loads((P2 / "lieferanten.json").read_text())
    orders = fetch_all(plm_client.call, "orders")
    status_obj = {}
    for o in orders:
        if isinstance(o.get("status"), dict) and o["status"].get("status"):
            status_obj.setdefault(o["status"]["status"], o["status"])
    targets = [o for o in orders if o["orderNumber"] in a.nr] if a.nr else [o for o in orders if st(o) in (None, "Draft") and not TEST.search(o["title"])]
    plan, L = [], ["# PO-Status aus Belegen (%s)" % ("APPLY" if a.apply else "TROCKENLAUF"), ""]
    for o in sorted(targets, key=lambda o: o["orderNumber"]):
        o["_ids"] = idents(o)
        slug = slug_for((o.get("manufacturer") or {}).get("name"), cfg)
        ev = invoice_evidence(slug, o["_ids"], float(o.get("totalNumberOfPieces") or 0))
        mails = mails_for(slug) if slug else []
        thread = thread_of(o, slug, mails)
        cands = [m for m in mails if m["thread"] in thread or any(norm(i) in norm(m["text"]) for i in o["_ids"])]
        cands.sort(key=lambda m: m["datum"], reverse=True)
        if cands:
            for e in ask_claude(o, cands):
                m = next((x for x in cands if x["id"] == e.get("mail")), None)
                if m and e.get("milestone") in MS and e.get("zitat") and re.sub(r"\s+", " ", e["zitat"]).strip()[:120] in re.sub(r"\s+", " ", m["text"]):
                    ev.append({"milestone": e["milestone"], "datum": e.get("datum"), "beleg": "Mail %s: \"%s\"" % (m["datum"], e["zitat"][:160])})
        cur = st(o) or "Draft"
        best = max(ev, key=lambda e: ORDER.index(MS[e["milestone"]]), default=None)
        tgt = MS[best["milestone"]] if best else None
        if tgt and ORDER.index(tgt) > ORDER.index(cur) and tgt in status_obj:
            plan.append({"id": o["id"], "nr": o["orderNumber"], "title": o["title"], "von": cur, "nach": tgt, "beleg": best["beleg"], "datum": best.get("datum")})
            L.append("- #%s %s: %s -> **%s** (%s, %s)" % (o["orderNumber"], o["title"], cur, tgt, best.get("datum"), best["beleg"]))
        else:
            L.append("- #%s %s: bleibt %s (%s; %d Mails mit Kennung %s)" % (o["orderNumber"], o["title"], cur, "kein Beleg" if not best else "Beleg nicht weiter: " + best["milestone"], len(cands), ", ".join(sorted(o["_ids"]))[:80]))
    if a.apply and plan:
        js = "(async()=>{const S=%s;const P=%s;const out={};for(const p of P){const b=await window.__fetchOrder(p.id);const before=JSON.stringify([b.d.totalCost,b.d.totalNumberOfPieces,b.d.items.length,(b.d.payments||[]).length]);" \
             "const line='['+new Date().toISOString().slice(0,10)+' ev:status-'+p.nach.replace(/ /g,'')+'] STATUS '+p.von+' -> '+p.nach+' laut '+p.beleg;" \
             "const notes=(b.d.notes||'');if(notes.includes('ev:status-'+p.nach.replace(/ /g,''))){out[p.nr]='schon';continue;}" \
             "await window.__updOrder(p.id,{status:S[p.nach],notes:notes+(notes?'\\n':'')+line});const x=await window.__fetchOrder(p.id);" \
             "out[p.nr]=[(x.d.status||{}).status,before===JSON.stringify([x.d.totalCost,x.d.totalNumberOfPieces,x.d.items.length,(x.d.payments||[]).length])];}return out;})()"
        S = {k: {kk: v[kk] for kk in ("id", "status", "color", "order")} for k, v in status_obj.items()}
        res = run_js(js % (json.dumps(S), json.dumps(plan, ensure_ascii=False)))
        L += ["", "## Rueckpruefung (Status, Summen/Positionen/Zahlungen unveraendert)", ""] + ["- #%s: %s" % (k, v) for k, v in res.items()]
    (P2 / "status_plan.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
