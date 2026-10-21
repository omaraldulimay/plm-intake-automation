"""Abgleich der ausgelesenen Packlisten-/Rechnungs-Belege mit den Avisen aus dem Logistik-Portal (smilo-logistics, DB-Schema logistics).

  python3 -m plm_intake.portal_abgleich [--inbox <Ordner>] [--seit 2026-10-01]      -> output/phase2/B14/portal_abgleich.md (nur LESEN, schreibt nichts in PLM/Portal/Inbox)

Das Portal liest Packlisten mit eigenen Vorlagen (Lieferant I, XW, Lieferant AH, Proforma, generisch), ordnet jede Zeile EAN-genau zu und vergleicht mit den Summen der Packliste.
Hier: je Beleg die Portal-Bestellung finden (Lieferant + Gesamtstueckzahl gleich) und je Artikel/Farbe/Groesse vergleichen. Abweichung = Hinweis, das Portal gilt (eindeutige Zahl aus der Packliste)."""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "phase2" / "B14"
INBOX = Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage/PLM-Mails/Inbox"
COLOR = {"black": "schwarz", "white": "weiss", "weib": "weiss", "weiß": "weiss", "grey": "grau", "gray": "grau", "cream": "creme", "crème": "creme", "creme": "creme",
         "hellgrau": "hellgrau", "hellblau": "hellblau", "dark green": "dunkelgruen", "dunkelgrün": "dunkelgruen"}
SIZE = {"2XL": "XXL", "XXL": "XXL"}
GENERIC = {"tekstil", "textile", "sanayi", "ticaret", "limited", "sirketi", "ltd", "sti", "co", "pvt", "private", "the", "and", "ve", "tic", "san", "company", "garment", "knitting", "trading", "industry"}


def nk(s):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(s or "").replace("ı", "i").replace("İ", "I")).lower()
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)))


def core(name):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(name or "").replace("ı", "i").replace("İ", "I")).lower()
    toks = [x for x in re.findall(r"[a-z0-9]+", "".join(c for c in t if not unicodedata.combining(c))) if x not in GENERIC]
    return toks[0] if toks else ""


def _ascii(x):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(x or "").replace("\u0131", "i").replace("\u0130", "I")).lower()
    return "".join(c for c in t if not unicodedata.combining(c))


def vendor_ok(vk, supplier):
    """Firmenkern des Belegs passt zu einem Wort des Portal-Lieferanten (auch bei Tippfehler: lieferant_i/lieferant_i)."""
    import difflib
    if not vk:
        return False
    for tok in re.findall(r"[a-z0-9]+", _ascii(supplier)):
        if tok == vk or (len(tok) >= 5 and len(vk) >= 5 and difflib.SequenceMatcher(None, tok, vk).ratio() >= 0.85):
            return True
    return False


def ckey(c):
    n = str(c or "").strip().lower()
    return COLOR.get(n, nk(n))


def skey(s):
    n = str(s or "").strip().upper()
    return SIZE.get(n, n)


def base(variation_no):
    return re.sub(r"-[A-Za-z]+\d+$", "", str(variation_no or ""))


def parse_attr(a):
    m = {}
    for part in str(a or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1); m[k.strip().lower()] = v.strip()
    return m.get("color", ""), m.get("size", "")


def portal_avise(since):
    import plenty_products as pp
    head = pp.psql("select id, supplier_name, reference, created_at::date, status from logistics.purchase_orders where created_at >= '%s' and supplier_name not ilike 'lagerdienst%%' and supplier_name not ilike 'WE-gez%%' order by id" % since)
    out = {}
    for pid, sup, ref, dt, st in head:
        rows = pp.psql("select k.variation_no, k.attributes, i.quantity from logistics.purchase_order_items i join logistics.skus k on k.ean=i.ean and k.instance_key=1 where i.purchase_order_id=%s" % pid)
        lines = {}
        for vno, attr, q in rows:
            col, size = parse_attr(attr)
            k = (nk(base(vno)), ckey(col), skey(size))
            lines[k] = lines.get(k, 0) + int(q)
        out[int(pid)] = {"supplier": sup, "ref": ref, "date": dt, "status": st, "lines": lines, "total": sum(lines.values())}
    return out


def doc_lines(po):
    lines = {}
    for it in po.get("items") or []:
        for v in it.get("variants") or []:
            for sz, q in (v.get("sizes") or {}).items():
                if q:
                    k = (nk(it.get("sku")), ckey(v.get("color")), skey(sz)); lines[k] = lines.get(k, 0) + int(q)
    return lines


def collapse(lines):
    """Ohne Farbe vergleichen (Farbnamen unterscheiden sich zwischen Beleg und Portal)."""
    out = {}
    for (a, _c, s), q in lines.items():
        out[(a, s)] = out.get((a, s), 0) + q
    return out


def run(inbox, since):
    avis = portal_avise(since)
    rep, n_ok, n_diff, n_none = [], 0, 0, 0
    for f in sorted(glob.glob(str(Path(inbox) / "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        po = d.get("po") if isinstance(d, dict) and "po" in d else d
        if not isinstance(po, dict) or not po.get("items") or po.get("doc_type") not in ("PACKING_LIST", "INVOICE", "PI", "PO"):
            continue
        dl = doc_lines(po)
        if not dl:
            continue
        dtotal = sum(dl.values()); declared = po.get("total_pieces")
        vk = core(po.get("vendor"))
        tots = (dtotal, declared and int(declared))
        cands = [(pid, a) for pid, a in avis.items() if vendor_ok(vk, a["supplier"]) and a["total"] and a["total"] in tots]
        nur_menge = False
        if not cands:   # anderer Absendername (z. B. Rechnung von Lieferant Z fuer LIEFERANT_AA): nur wenn genau EINE Portal-Bestellung dieselbe Stueckzahl hat
            same = [(pid, a) for pid, a in avis.items() if a["total"] >= 200 and a["total"] in tots]
            if len(same) == 1:
                cands, nur_menge = same, True
        name = Path(f).name
        if not cands:
            n_none += 1; continue
        pid, a = cands[-1]
        dc, pc = collapse(dl), collapse(a["lines"])
        da, pa_ = {k[0] for k in dc}, {k[0] for k in pc}
        if len(da) == 1 and len(pa_) == 1 and da != pa_:   # je eine Artikelnummer, aber andere Schreibweise (Lieferantencode gegen Smilodox-Variationsnummer): nur Groessen vergleichen
            dc, pc = {("", k[1]): v for k, v in dc.items()}, {("", k[1]): v for k, v in pc.items()}
        diffs = [(k, dc.get(k, 0), pc.get(k, 0)) for k in sorted(set(dc) | set(pc)) if dc.get(k, 0) != pc.get(k, 0)]
        head = "- %s | %s %s | Beleg %s Stk (Summe Groessen %s) | Portal-Bestellung #%s '%s' %s Stk" % (name, po.get("vendor", "")[:28], po.get("po_number"), declared, dtotal, pid, str(a["ref"])[:50], a["total"])
        if not diffs:
            n_ok += 1; rep.append(head + (" [nur ueber Stueckzahl zugeordnet]" if nur_menge else "") + " -> STIMMT"); continue
        n_diff += 1
        rep.append(head + (" [nur ueber Stueckzahl zugeordnet]" if nur_menge else "") + " -> %d ABWEICHUNGEN (Beleg/KI gegen Portal):" % len(diffs))
        rep += ["    - %s %s: KI %s, Portal %s" % (k[0], k[1], x, y) for k, x, y in diffs[:25]]
    return rep, n_ok, n_diff, n_none


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--inbox", default=str(INBOX)); ap.add_argument("--seit", default="2026-10-01")
    a = ap.parse_args(argv)
    rep, ok, diff, none = run(a.inbox, a.seit)
    OUT.mkdir(parents=True, exist_ok=True)
    text = ["# Abgleich Belege gegen Portal-Avise (nur lesen)", "", "Belege mit Portal-Treffer: %d (stimmen %d, mit Abweichung %d) | ohne Portal-Treffer: %d" % (ok + diff, ok, diff, none), ""] + rep
    (OUT / "portal_abgleich.md").write_text("\n".join(text))
    print("\n".join(text[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
