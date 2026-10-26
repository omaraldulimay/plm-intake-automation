"""Phase 2 Schritt 1+2: Quellen eines Lieferanten aus dem lokal gespiegelten Drive-Export (NUR LESEN, kein LLM).

  python3 -m plm_intake.phase2_sources alpha --domain lieferant-a.example --name "lieferant_a" [--von 2025-10-01]

Mails: mails_*.txt in einzelne Mails teilen; Treffer = Domain/Name in Von/An/Cc/Betreff.
Anhänge: Anhaenge/<Datum>_<MailID>_<Name>, gehören zu Treffer-Mails (MailID) oder Name/Inhalt nennt den Lieferanten.
Dubletten: gleicher Originalname + Größe -> nur die neueste Datei. Text wörtlich nach src/<id>.txt.
Ausgabe output/phase2/<lieferant>/sources.json (typ, datum, styles, bankdaten, lesbar)."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVE = Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage/PLM-Mails"
BANK_RX = re.compile(r"(?i)\biban\b|\bswift\b|\bbic\b\s*[:=]|account\s*(no|number)|kontonummer|\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b")
ATT_RX = re.compile(r"^(\d{4}-\d{2}-\d{2})_([0-9a-f]{16})_(.+)$")
TYP_RULES = [("QC", r"inspection|durability|test report|\bqc\b"), ("TP", r"tech[ _-]?(pack|sheet)|\btp\b|_tp|bom"),
             ("Spec", r"spec|size ?chart|measure|mass|maß"), ("PL", r"packing|packliste|\bpl\b"),
             ("CI", r"invoice|\binv\b|inv#|rechnung|\bci\b"), ("PI", r"\bpi\b|proforma|pro forma|sales contract"),
             ("PO", r"\bpo\b|order"), ("Versand", r"\bbl\b|b/l|hbl|ohbl|cro|mawb|awb|shipment|shipping")]
STYLE_RX = re.compile(r"\b(?:AL29\d{3}|S[EKDLN][MWKU]?\d{2}-?\d{3}(?:-\d)?|SM26-?\d{3}(?:-\d)?|ALP-?\d{2,3}-?\d{0,2}|\d{5}|5618\d{2})\b")
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".heic", ".webp", ".bmp", ".tif", ".tiff", ".mp4", ".mov", ".zip", ".rar", ".ics"}


def split_mails(text):
    for block in text.split("===== MAIL =====")[1:]:
        head, _, body = block.partition("----- TEXT -----")
        h = {}
        for line in head.strip().splitlines():
            k, _, v = line.partition(":")
            h[k.strip()] = v.strip()
        yield h, block


def typ_of(name):
    n = name.lower()
    for t, rx in TYP_RULES:
        if re.search(rx, n):
            return t
    return "Sonstiges"


def extract_text(p):
    ext = p.suffix.lower()
    if ext == ".pdf":
        import fitz
        with fitz.open(p) as d:
            return "\n".join(pg.get_text() for pg in d)
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        out = []
        for ws in wb:
            out.append(f"### Blatt {ws.title}")
            for row in ws.iter_rows(values_only=True):
                if any(c is not None and str(c).strip() for c in row):
                    out.append("\t".join("" if c is None else str(c) for c in row).rstrip())
        return "\n".join(out)
    if ext == ".xls":
        code = ("import sys,xlrd\nb=xlrd.open_workbook(sys.argv[1])\nfor s in b.sheets():\n print('### Blatt',s.name)\n"
                " for r in range(s.nrows):\n  v=[str(x) for x in s.row_values(r)]\n  print('\\t'.join(v).rstrip()) if any(x.strip() for x in v) else None")
        return subprocess.run(["/usr/bin/python3", "-I", "-c", code, str(p)], capture_output=True, text=True, timeout=120, check=True).stdout
    if ext == ".docx":
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf8", "replace")
        return re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", xml))
    if ext in (".csv", ".txt"):
        return p.read_text("utf8", "replace")
    raise ValueError(f"Format {ext} nicht unterstützt")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("lieferant")
    ap.add_argument("--domain", action="append", default=[])
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--von", default="2025-10-01")
    ap.add_argument("--drive", default=str(DRIVE))
    a = ap.parse_args(argv)
    drive = Path(a.drive)
    out = ROOT / "output" / "phase2" / a.lieferant
    (out / "src").mkdir(parents=True, exist_ok=True)
    pats = [re.escape(x.lower()) for x in a.domain + a.name]
    hit_rx = re.compile("|".join(pats))

    mails, mail_ids = {}, set()
    for f in sorted(drive.glob("mails_*.txt")):
        for h, block in split_mails(f.read_text("utf8", "replace")):
            if h.get("Datum", "")[:10] < a.von:
                continue
            kopf = " ".join(h.get(k, "") for k in ("Von", "An", "Cc", "Betreff")).lower()
            if hit_rx.search(kopf):
                mid = h.get("Message-ID", "")
                if mid and mid not in mails:
                    mails[mid] = (h, block)
                    mail_ids.add(mid)

    sources = []
    for mid, (h, block) in sorted(mails.items(), key=lambda kv: kv[1][0].get("Datum", "")):
        sid = "mail_" + mid
        (out / "src" / f"{sid}.txt").write_text(block, "utf8")
        sources.append({"id": sid, "name": h.get("Betreff", ""), "typ": "Mail", "datum": h.get("Datum", ""),
                        "von": h.get("Von", ""), "anhaenge": h.get("Anhaenge", ""), "styles": sorted(set(STYLE_RX.findall(block))),
                        "bankdaten": bool(BANK_RX.search(block)), "lesbar": True})

    newest = {}
    for p in (drive / "Anhaenge").iterdir():
        m = ATT_RX.match(p.name)
        if not m or m.group(1) < a.von:
            continue
        datum, mid, orig = m.groups()
        if mid not in mail_ids and not hit_rx.search(orig.lower()):
            continue
        if p.suffix.lower() in SKIP_EXT:
            continue
        key = (orig.lower(), p.stat().st_size)
        if key not in newest or datum > newest[key][0]:
            newest[key] = (datum, mid, orig, p)

    for datum, mid, orig, p in sorted(newest.values()):
        sid = "att_" + hashlib.sha1(p.name.encode()).hexdigest()[:12]
        rec = {"id": sid, "name": orig, "datei": p.name, "typ": typ_of(orig), "datum": datum, "mail_id": mid,
               "groesse_bytes": p.stat().st_size}
        try:
            txt = extract_text(p)
            (out / "src" / f"{sid}.txt").write_text(txt, "utf8")
            rec.update(lesbar=bool(txt.strip()), styles=sorted(set(STYLE_RX.findall(txt + " " + orig))),
                       bankdaten=bool(BANK_RX.search(txt)), zeichen=len(txt))
            if not txt.strip():
                rec["grund"] = "kein Text (Scan?)"
        except Exception as e:  # noqa: BLE001 - jede Datei einzeln, Lauf geht weiter
            rec.update(lesbar=False, grund=str(e)[:200], styles=[], bankdaten=False)
        sources.append(rec)

    (out / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=1), "utf8")
    from collections import Counter
    c = Counter(s["typ"] for s in sources)
    print(f"{a.lieferant}: {len(sources)} Quellen", dict(c), "nicht lesbar:", sum(not s["lesbar"] for s in sources))


if __name__ == "__main__":
    main()
