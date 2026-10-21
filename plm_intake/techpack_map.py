"""Zuordnung Techpack-/Spec-Datei -> PLM-Produkt(e). Kein Raten: nur belegte Wege, sonst offen.

Reihenfolge (staerkstes Signal zuerst):
  1. exakt     Stylecode im Dateinamen == SKU (normalisiert, wie techpack_links)
  2. regel     Kunde Y-Codes der Lieferanten: SKM26-005(-1) -> SDKM26-005-1 (ebenso SKW/SKU -> SDKW/SDKU); nur wenn die Ziel-SKU existiert
  3. alias     belegte Uebersetzungstabelle output/intake/techpack_code_aliases.json (z. B. Kunde X SLM26-001 -> IAN 561872)
  4. inhalt    Stylecodes, die im Text der Datei stehen und als SKU existieren (Kundenvarianten wie Holmes Place SHM26-008 -> SNM26-008)
Mehrere Produkte sind erlaubt, wenn Name oder Inhalt mehrere Styles nennt (Uebersicht/Set). Mehr als MAX_PRODUCTS -> offen."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALIASES = ROOT / "output" / "intake" / "techpack_code_aliases.json"
CODE_RX = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2}-[A-Za-z]{2}-?\d{4,6}|\d{2}[A-Za-z]\d{2}[-_ ]?\d{3}|[A-Za-z]{1,5}[-_ ]?\d{2}[-_ ]?\d{3}(?:[-_ ]\d)?|[A-Za-z]{1,6}[-_ ]?\d{2,6}[A-Za-z]?|SH-MM-\d{3}|YK-?\d{3}|\d{6})(?![0-9])")
KUNDE_Y_RX = re.compile(r"^SK([MWU])(\d{2})(\d{3})(\d?)$")
MAX_PRODUCTS = 12
NO_CONTENT = ("LIEFERANT_AG",)   # Lieferant AG-BOMs sind aus einer Smilodox-Vorlage (SNM26-008) kopiert: Inhaltscodes sind dort kein Beleg


def nk(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def load_aliases(path=ALIASES):
    try:
        return {nk(k): v for k, v in json.loads(Path(path).read_text()).items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def codes(text):
    out = []
    for m in CODE_RX.findall(re.sub(r"\.[A-Za-z]{2,4}$", "", str(text or ""))):
        k = nk(m)
        if len(k) >= 5 and k not in out:
            out.append(k)
    return out


def _index(products):
    by = {}
    for p in products:
        if p.get("sku") and not re.match(r"(?i)zz|t1-", str(p["sku"])):
            by.setdefault(nk(p["sku"]), []).append(p)
    return by


def _kunde_y(code):
    m = KUNDE_Y_RX.match(code.upper())
    if not m:
        return []
    g, yy, num, suf = m.groups()
    return [nk("SDK%s%s%s%s" % (g, yy, num, suf or "1"))]


def resolve(file_name, products, aliases=None, content=""):
    """-> (produkte, methode, begruendung). produkte = [] heisst offen."""
    by = _index(products)
    aliases = aliases if aliases is not None else load_aliases()
    hits, how = {}, []
    for c in codes(file_name):
        ids = [p for p in by.get(c, [])]
        meth = "exakt"
        if not ids:
            for k in _kunde_y(c):
                ids = by.get(k, [])
                meth = "regel"
                if ids:
                    break
        if not ids and c in aliases:
            ids, meth = by.get(nk(aliases[c]), []), "alias"
        if not ids:   # Varianten-Suffix (XW-042-CROC / 561871_A): nur Buchstaben, hoechstens 3 Produkte
            ext = [p for k, L in by.items() if k.startswith(c) and re.fullmatch(r"[a-z]{1,6}", k[len(c):]) for p in L]
            if 0 < len(ext) <= 3:
                ids, meth = ext, "exakt"
        for p in ids:
            hits[p["id"]] = p
        if ids:
            how.append("%s %s->%s" % (meth, c, ",".join(sorted({p["sku"] for p in ids}))))
    if not hits and content and not any(x.lower() in str(file_name).lower() for x in NO_CONTENT):
        found = [c for c in codes(content) if c in by]
        for c in found:
            for p in by[c]:
                hits[p["id"]] = p
        if found:
            how.append("inhalt " + ",".join(sorted({by[c][0]["sku"] for c in found})))
    if not hits:
        return [], "offen", "kein Stylecode im Namen oder Inhalt, der als SKU existiert"
    if len(hits) > MAX_PRODUCTS:
        return [], "offen", "zu viele Produkte (%d): %s" % (len(hits), "; ".join(how)[:200])
    meth = how[0].split(" ")[0]
    return list(hits.values()), meth, "; ".join(how)


def file_text(path, limit=60000):
    """Text aus PDF (PyMuPDF) oder Excel (openpyxl, .xls via xlrd wenn vorhanden). Fehler -> ''."""
    p = str(path)
    try:
        if p.lower().endswith(".pdf"):
            import fitz
            return " ".join(pg.get_text() for pg in fitz.open(p))[:limit]
        if p.lower().endswith((".xlsx", ".xlsm")):
            import openpyxl
            wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True, max_row=300):
                    out.append(" ".join(str(c) for c in row if c is not None))
            return " ".join(out)[:limit]
    except Exception:
        return ""
    return ""
