"""Belege (Rechnung, Packliste, Proforma, PO-PDF) als ANHANG an die zugeordnete Order im Lifecycle-PLM haengen.

Quellen: Beleg-JSONs der Inbox (Zuordnung Beleg -> Order wie docs_existing) und die Originaldateien in PLM-Mails/Anhaenge (lokal Drive Desktop, Cloud: Drive-API).
Datei -> Beleg: gleiche Mail-ID UND Dateiname enthaelt eine Kennung des Belegs (PO-/Belegnummer, Dokumentname) oder ist im Dokumentnamen des Belegs enthalten.
Upload wie upload_helpers.js: /upload/presigned-url -> S3 -> addOrderAttachment (browser/order_upload_helpers.js). Nur additiv, das Skript loescht NIE.

Regeln (nie lockern ohne Omar):
- nur Belege mit EINDEUTIG zugeordneter Order (docs_existing: DELIVERY_DOC bzw. Dublette einer vorhandenen Order); AMBIGUOUS/ORPHAN/BLOCKER/SERVICE/REORDER/PI_CHANGED nie;
  eine Datei, die zu Belegen verschiedener Orders passt, wird nicht angehaengt; Test-Orders (ZZ-/T1-/TEST-Titel) nie
- keine Zahlungsnachweise/Bank-Slips (Dateiname), keine BL/Zoll/Inspektions-/Etiketten-Dateien, nur PDF/Excel/Word, max. 20 MB
- keine Datei mit IBAN/SWIFT/Kontodaten im Text (Textcheck wie core.BANK_PATTERNS); nicht lesbarer Text (Scan, .doc) gilt als nicht pruefbar -> ausgeschlossen
- Dubletten: Merkbuch (intake/order_attachments_ledger.json, Order+SHA-1) und orderAttachments der Order (Dateiname ohne Endung); gleicher Name mit anderem Inhalt aus dem
  Merkbuch -> Name mit Mail-Datum; gleicher Name, nicht aus dem Merkbuch -> uebersprungen
- max. 30 Dateien pro Lauf, in Bloecken zu 10, nach jedem Block Zuruecklesen (Anhang mit Namen in orderAttachments), bei Abweichung Abbruch
Dry-Run ist Standard:  python3 -m plm_intake.order_attachments [--apply] [--max N]"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BROWSER = Path(__file__).resolve().parent / "browser"
HELPER = BROWSER / "order_upload_helpers.js"
LEDGER_NAME = "order_attachments_ledger.json"
MAX_FILES = 30
BLOCK = 10
MAXB = 20 * 1024 * 1024
EXTS = (".pdf", ".xlsx", ".xls", ".xlsm", ".docx", ".doc", ".csv")
ATT_RX = re.compile(r"^(\d{4}-\d{2}-\d{2})_([0-9a-f]{16})_(.+)$")
MIME = {".pdf": "application/pdf", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xls": "application/vnd.ms-excel",
        ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword", ".csv": "text/csv"}
# Zahlungsnachweise / Bank-Slips
PAY_RX = re.compile(r"(?i)swift|bank|remit|receipt|\bslip\b|dekont|havale|mt103|zahlungs(nachweis|beleg|bestaetig|bestätig)|[uü]berweisung|proof\s*of\s*payment|payment\s*(slip|proof|receipt|advice|confirm|voucher|copy)|\bt/?t\b\s*(copy|slip)|\biban\b")
# keine Beleg-Art: Transport/Zoll/Pruefung/Etiketten/Grafik
NOTDOC_RX = re.compile(r"(?i)preisvergleich|angebot|quotation|target|\bresult|\bpass\b|\breport|\bb/?l\b|\bbl[\s_-]|bill of lading|konşimento|konsimento|\bawb\b|beyanname|zoll|\btax\b|inspection|inspektion|barcode|sticker|shipping marks|carton marks|logo|tech ?pack|\blabel|aufkleber|\bqc\b")
BANK_TEXT = re.compile(r"(?i)\biban\b|\bswift\b|\bbic\b\s*[:\-=]?\s*[A-Z0-9]{8}|account\s*(no|number|name)|kontonummer|beneficiary|bank\s*(name|account|details|information|:)|\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").casefold().replace("ı", "i")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s)


def is_test(title):
    return bool(re.search(r"(?i)(^|[^a-z0-9])zz|(^|[^a-z0-9])T1([^a-z0-9]|$)|TEST", str(title or "")))


def display_name(datei):
    m = ATT_RX.match(datei)
    return m.group(3) if m else datei


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def attach_name(display, suffix=None):
    """PLM-Anhangsname = Dateiname ohne Endung (wie bei Produkt-Anhaengen), optional mit Zusatz."""
    base = os.path.splitext(display)[0].strip()
    return base + (" (%s)" % suffix if suffix else "")


def name_reason(display):
    """Grund, warum der Dateiname nicht angehaengt wird, sonst None."""
    ext = os.path.splitext(display)[1].lower()
    if ext not in EXTS:
        return "Dateityp %s kein Beleg-Format" % (ext or "?")
    if PAY_RX.search(display):
        return "Zahlungsnachweis/Bankbezug im Dateinamen"
    if NOTDOC_RX.search(display):
        return "kein Rechnung/Packliste/PI/PO (Transport/Zoll/Pruefung/Etikett)"
    return None


DOC_RX = re.compile(r"(?i)inv|rechnung|packing|pack(ing)?\s*list|packliste|\bp\.?\s?l\b|proforma|pro forma|\bpi\b|\bpo\b|commercial|\bci\b|purchase order|bestellung|fatura|orden")


def doc_like(display, keys, srcdoc_norm):
    """Dateiname sieht nach Beleg aus: Belegwort, oder der Name ist der Beleg (Name im Dokumentnamen / Name = Belegnummer)."""
    base = norm(os.path.splitext(display)[0])
    if DOC_RX.search(display):
        return True
    if len(base) >= 8 and base in srcdoc_norm:
        return True
    return any(base == k or (k in base and len(base) <= len(k) + 3) for k in keys)


def bank_hit(text):
    m = BANK_TEXT.search(text or "")
    return m.group(0)[:20] if m else None


def default_text_of(display, data):
    """Text einer Datei fuer den Bankdaten-Check; Fehler/nicht unterstuetzt -> ''."""
    from plm_intake import phase2_sources
    ext = os.path.splitext(display)[1].lower()
    if ext == ".doc":
        return ""
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as cwd:
        p = Path(td) / ("f" + ext)
        p.write_bytes(data)
        try:
            if ext == ".xls":   # xlrd liegt nur im User-Python (-I der Standardfunktion blendet es aus): Lauf in leerem Verzeichnis, Datei nur als Argument
                import subprocess
                code = ("import sys,xlrd\nb=xlrd.open_workbook(sys.argv[1])\nfor s in b.sheets():\n print('### Blatt',s.name)\n for r in range(s.nrows):\n"
                        "  v=[str(x) for x in s.row_values(r)]\n  print('\\t'.join(v).rstrip()) if any(x.strip() for x in v) else None")
                return subprocess.run(["/usr/bin/python3", "-c", code, str(p)], capture_output=True, text=True, timeout=120, check=True, cwd=cwd).stdout
            return phase2_sources.extract_text(p)
        except Exception:
            return ""


def doc_keys(po, fname):
    """Kennungen eines Beleg-JSONs (normalisiert) zum Abgleich mit Dateinamen."""
    src = po.get("source")
    srcdoc = (src.get("doc") if isinstance(src, dict) else src) or ""
    keys = set()
    for t in (po.get("po_number"), po.get("invoice_number"), srcdoc):
        n = norm(t)
        if len(n) >= 5:
            keys.add(n)
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9/\-_.#]{4,}", str(srcdoc)):
        n = norm(tok)
        if len(n) >= 5 and re.search(r"\d", n):
            keys.add(n)
    return keys, norm(srcdoc)


def file_matches(display, keys, srcdoc_norm):
    base = norm(os.path.splitext(display)[0])
    if len(base) >= 8 and base in srcdoc_norm:
        return True
    return any(k in base for k in keys)


def mail_of(po, fname):
    src = po.get("source")
    mid = src.get("mail_id") if isinstance(src, dict) else None
    return mid or fname.split("_")[0]


def index_files(files):
    """{mail_id: [file, ...]} aus der Anhangsliste (Name '<Datum>_<MailID>_<Name>')."""
    out = {}
    for f in files:
        m = ATT_RX.match(f["name"])
        if m:
            out.setdefault(m.group(2), []).append({**f, "date": m.group(1), "display": m.group(3)})
    return out


def plan(inbox, rows, files, overrides=None, text_of=None, load_data=True):
    """-> (items, ausgeschlossen). items: zuordenbare Dateien {file,json,mail,date,display,order_id,order,sha,size,data}; ausgeschlossen: [(Datei oder Beleg, Grund)].
    rows: docs_existing-Zeilen (kind/pid/parent/file)."""
    overrides = overrides or {}
    text_of = text_of or default_text_of
    by_mail = index_files(files)
    rowof = {r["file"]: r for r in rows}
    docs = {}
    for fn in sorted(rowof):
        try:
            docs[fn] = json.loads((Path(inbox) / fn).read_text())
        except (OSError, ValueError):
            pass
    # Beleg-Eignung je JSON
    ok_pid, excluded = {}, []
    for fn, r in rowof.items():
        kind, pid = r.get("kind"), r.get("pid")
        if overrides.get(fn) == "SKIP":
            excluded.append((fn, "Beleg per Override SKIP")); continue
        if kind in ("DELIVERY_DOC", "SKIP") and pid:   # SKIP mit pid = Beleg ist Dublette einer vorhandenen Order (z. B. PI), eindeutig zugeordnet
            ok_pid[fn] = pid
        else:
            excluded.append((fn, "%s%s" % (kind or "?", (": " + str(r.get("why"))[:80]) if r.get("why") else "")))
    # Datei -> Anspruchsteller (alle Belege der Mail, auch nicht zuordenbare, damit mehrdeutige Dateien auffallen)
    claims = {}
    for fn, po in docs.items():
        keys, sd = doc_keys(po, fn)
        for f in by_mail.get(mail_of(po, fn), []):
            if file_matches(f["display"], keys, sd):
                claims.setdefault(f["name"], []).append(fn)
    items, seen = [], set()
    for fname, fns in sorted(claims.items()):
        f = next(x for lst in by_mail.values() for x in lst if x["name"] == fname)
        disp = f["display"]
        pids = {ok_pid.get(x) for x in fns}
        if None in pids or len(pids) != 1:
            excluded.append((disp, "Beleg nicht eindeutig einer Order zugeordnet (%s: %s)" % (", ".join(sorted(fns))[:50], "; ".join(sorted({str(rowof[x].get("kind")) for x in fns}))))); continue
        pid = pids.pop()
        row = rowof[fns[0]]
        title = re.sub(r"^#\S+\s*", "", row.get("parent") or "")
        if is_test(title):
            excluded.append((disp, "Test-Order %s" % title)); continue
        why = name_reason(disp)
        if not why and not doc_like(disp, *doc_keys(docs[fns[0]], fns[0])):
            why = "Dateiname nicht als Rechnung/Packliste/PI/PO erkennbar"
        if why:
            excluded.append((disp, why)); continue
        if f.get("size", 0) > MAXB:
            excluded.append((disp, "groesser als 20 MB")); continue
        try:
            data = f["get"]()
        except Exception as e:
            excluded.append((disp, "Download fehlgeschlagen: %s" % str(e)[:60])); continue
        txt = text_of(disp, data)
        if len((txt or "").strip()) < 20:
            excluded.append((disp, "Text nicht lesbar, Bankdaten-Pruefung nicht moeglich")); continue
        hit = bank_hit(txt)
        if hit:
            excluded.append((disp, "Bank-/Kontodaten im Text (%s)" % hit)); continue
        h = sha1(data)
        if (pid, h) in seen:
            excluded.append((disp, "gleicher Inhalt schon in diesem Lauf fuer die Order")); continue
        seen.add((pid, h))
        items.append({"file": fns[0], "mail": ATT_RX.match(fname).group(2), "date": f["date"], "display": disp, "att_file": fname, "order_id": pid, "order": title,
                      "sha": h, "size": len(data), "data": data})
    items.sort(key=lambda i: (i["date"], i["order"], i["display"]))
    return items, excluded


# ---------------- Merkbuch ----------------
def load_ledger(path):
    try:
        d = json.loads(Path(path).read_text())
        return {"done": dict(d.get("done") or {})}
    except (OSError, ValueError):
        return {"done": {}}


def save_ledger(path, led):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(led, ensure_ascii=False, indent=1, sort_keys=True))


def lkey(order_id, sha):
    return "%s|%s" % (order_id, sha)


# ---------------- Browser ----------------
READ_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v }), V = n => ({ kind: 'Variable', name: N(n) });
  const F = (n, sel, args) => ({ kind: 'Field', name: N(n), arguments: args || [], selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const q = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: [{ kind: 'VariableDefinition', variable: V('o'), type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N('String') } } }],
    selectionSet: { kind: 'SelectionSet', selections: [F('orderAttachments', [F('id'), F('name'), F('fileUrl'), F('fileType')], [{ kind: 'Argument', name: N('orderId'), value: V('o') }])] } }] };
  const out = {};
  for (const o of __OIDS__) { const r = await window.__APOLLO_CLIENT__.query({ query: q, variables: { o }, fetchPolicy: 'no-cache', errorPolicy: 'all' }); out[o] = (r.data && r.data.orderAttachments) ? JSON.parse(JSON.stringify(r.data.orderAttachments, (k, v) => k === '__typename' ? undefined : v)) : null; }
  return out;
})()'''


def browser_js(js, tries=40, wait=15):
    """barcodes.run_js mit Wiederholung, wenn ein paralleler Lauf das Browserprofil belegt (Chrome: 'Aborting now to avoid profile corruption')."""
    import time
    from plm_intake import barcodes
    for i in range(tries):
        try:
            return barcodes.run_js(js)
        except RuntimeError as e:
            if not re.search(r"rruption|exitCode=21|ProcessSingleton", str(e)) or i == tries - 1:
                raise
            time.sleep(wait)


def read_existing(order_ids, run_js=None):
    return (run_js or browser_js)(READ_JS.replace("__OIDS__", json.dumps(sorted(order_ids))))


def upload_one(order_id, name_with_ext, data, run_js=None):
    """-> (ok, Anhangs-ID oder Fehlertext)."""
    ext = os.path.splitext(name_with_ext)[1].lower()
    js = "(async()=>{" + HELPER.read_text() + "\nreturn await window.__uploadOrderFile(%s,%s,%s,'%s');})()" % (
        json.dumps(order_id), json.dumps(name_with_ext), json.dumps(MIME.get(ext, "application/octet-stream")), base64.b64encode(data).decode())
    r = (run_js or browser_js)(js)
    if isinstance(r, dict) and r.get("ok"):
        return True, r.get("id")
    return False, str(r)[:200]


def has_name(atts, name):
    return any((a.get("name") or "").strip().lower() == name.strip().lower() for a in atts or [])


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(items, excluded, ledger_path, apply=False, max_files=MAX_FILES, reader=None, uploader=None):
    """-> (Berichtszeilen, Ergebnis {neu, uebersprungen, fehler, ausgeschlossen, offen, warnungen})."""
    reader = reader or read_existing
    uploader = uploader or upload_one
    max_files = min(max_files, MAX_FILES)
    led = load_ledger(ledger_path)
    res = {"neu": 0, "uebersprungen": 0, "fehler": 0, "ausgeschlossen": len(excluded), "offen": 0, "warnungen": []}
    lines = []
    todo = []
    for it in items:
        if lkey(it["order_id"], it["sha"]) in led["done"]:
            res["uebersprungen"] += 1; continue
        todo.append(it)
    if not todo:
        return lines, res
    ex = reader({i["order_id"] for i in todo})
    jobs, used = [], {}
    for it in todo:
        atts = ex.get(it["order_id"])
        if atts is None:
            res["fehler"] += 1; res["warnungen"].append("Anhaenge der Order %s nicht lesbar: %s" % (it["order"], it["display"])); continue
        name = attach_name(it["display"])
        taken = list(atts) + used.get(it["order_id"], [])
        if has_name(taken, name):
            ledger_names = {v.get("name", "").lower() for v in led["done"].values() if v.get("order_id") == it["order_id"]}
            if name.lower() in ledger_names or has_name(used.get(it["order_id"], []), name):   # unser eigener Anhang, anderer Inhalt -> Fassung mit Datum
                name = attach_name(it["display"], it["date"])
                if has_name(taken, name):
                    res["uebersprungen"] += 1; lines.append("- uebersprungen (Name vorhanden): %s -> %s" % (it["display"][:60], it["order"])); continue
            else:
                res["uebersprungen"] += 1; lines.append("- uebersprungen (Name im PLM vorhanden): %s -> %s" % (it["display"][:60], it["order"])); continue
        used.setdefault(it["order_id"], []).append({"name": name})
        jobs.append({**it, "name": name, "upload_name": name + os.path.splitext(it["display"])[1].lower()})
    res["offen"] = max(0, len(jobs) - max_files)
    jobs = jobs[:max_files]
    if not apply:
        lines += ["- wuerde anhaengen: %s -> %s (%d KB)" % (j["upload_name"][:70], j["order"], j["size"] // 1024) for j in jobs]
        res["neu"] = len(jobs)
        return lines, res
    for b in range(0, len(jobs), BLOCK):
        block, done = jobs[b:b + BLOCK], []
        for j in block:
            ok, info = uploader(j["order_id"], j["upload_name"], j["data"])
            if ok:
                done.append((j, info))
                led["done"][lkey(j["order_id"], j["sha"])] = {"order_id": j["order_id"], "order": j["order"], "name": j["name"], "size": j["size"], "mail": j["mail"],
                                                              "att_id": info, "ts": now_iso()}
                save_ledger(ledger_path, led)
                lines.append("- angehaengt: %s -> %s" % (j["upload_name"][:70], j["order"]))
            else:
                res["fehler"] += 1; res["warnungen"].append("Anhang %s -> %s: %s" % (j["upload_name"][:50], j["order"], info))
        after = reader({j["order_id"] for j, _ in done}) if done else {}
        bad = [j for j, i in done if not any(a.get("id") == i and (a.get("name") or "").lower() == j["name"].lower() for a in after.get(j["order_id"]) or [])]
        res["neu"] += len(done) - len(bad)
        if bad:
            res["fehler"] += len(bad)
            res["warnungen"].append("Zuruecklesen: %d Anhang/Anhaenge nicht in orderAttachments: %s" % (len(bad), ", ".join(j["name"][:40] for j in bad[:5])))
            lines.append("- ABBRUCH nach Block %d: Zuruecklesen meldet Abweichung" % (b // BLOCK + 1))
            break
        if res["fehler"]:   # Fehler im Block: nicht weitermachen, Mensch/naechster Lauf schaut nach
            lines.append("- Abbruch nach Block %d wegen Fehlern" % (b // BLOCK + 1))
            break
    return lines, res


def report_line(res):
    return "Anhaenge: neu %d, uebersprungen %d, Fehler %d" % (res["neu"], res["uebersprungen"], res["fehler"])


def source_files():
    from plm_intake import techpack_daily
    return techpack_daily.default_source(None)


def build(inbox, ctx, overrides, files=None, text_of=None, out_dir=None):
    """docs_existing-Zuordnung (frischer Kontext) + Dateien -> (items, ausgeschlossen, rows). Schreibt nichts ins PLM; Ereignisdateien nur in ein Temp-Verzeichnis."""
    from plm_intake import docs_existing
    with tempfile.TemporaryDirectory() as td:
        rows, _ = docs_existing.run(inbox, ctx, overrides, out_dir or td)
    items, excluded = plan(inbox, rows, files if files is not None else source_files(), overrides, text_of)
    return items, excluded, rows


def auto(inbox, ctx, intake, apply, overrides=None, files=None, max_files=MAX_FILES):
    """Aufruf aus auto_run: -> (Berichtszeilen, Ergebnis). Fehler brechen den Lauf nie ab (Aufrufer faengt ab)."""
    items, excluded, _ = build(inbox, ctx, overrides or {}, files)
    lines, res = run(items, excluded, Path(intake) / LEDGER_NAME, apply, max_files)
    return [("- " + report_line(res) + ", ausgeschlossen %d%s" % (res["ausgeschlossen"], "" if apply else " (Trockenlauf)"))] + lines, res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max", type=int, default=MAX_FILES)
    ap.add_argument("--inbox")
    ap.add_argument("--intake", default=str(ROOT / "output" / "intake"))
    ap.add_argument("--out", help="Bericht als Markdown schreiben")
    a = ap.parse_args(argv)
    intake = Path(a.intake)
    import plm_client  # noqa: F401
    from plm_intake import daily
    from plm_intake.context import add_po_numbers, load_context
    inbox = daily.resolve_inbox(a.inbox, intake)
    ctx = load_context()
    n_po = add_po_numbers(ctx, runner=browser_js)
    if not n_po:
        print('WARNUNG: PO-Nummern konnten nicht nachgeladen werden, Zuordnung nur ueber Titel', file=sys.stderr)
    for k, f in (("aliases", "vendor_aliases.json"), ("po_aliases", "po_aliases.json"), ("style_aliases", "style_aliases.json")):
        ctx[k] = json.load(open(intake / f)) if (intake / f).exists() else {}
    ov = json.load(open(intake / "overrides.json")) if (intake / "overrides.json").exists() else {}
    items, excluded, _ = build(inbox, ctx, ov)
    lines, res = run(items, excluded, intake / LEDGER_NAME, a.apply, a.max)
    rep = ["# Order-Anhaenge (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", report_line(res) + ", ausgeschlossen %d, noch offen %d" % (res["ausgeschlossen"], res["offen"]), "",
           "## Kandidaten (Datei -> Order)"] + ["- %s -> %s" % (i["display"][:80], i["order"]) for i in items] + ["", "## Ausgeschlossen"] + ["- %s: %s" % (n[:80], w) for n, w in excluded]
    rep += ["", "## Aktionen"] + lines + (["", "## Warnungen"] + res["warnungen"] if res["warnungen"] else [])
    txt = "\n".join(rep)
    if a.out:
        Path(a.out).write_text(txt)
    print(txt)
    return 1 if res["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
