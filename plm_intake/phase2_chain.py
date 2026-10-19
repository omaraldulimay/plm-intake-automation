"""Phase 2 Ablauf: Lieferanten batchweise komplett abarbeiten (je Lieferant ein Durchgang, kein Teil-Batch).

  python3 -m plm_intake.phase2_chain --batch 1 [--dry]      Batch aus output/phase2/lieferanten.json
  python3 -m plm_intake.phase2_chain --lieferant lieferant_d [--dry]

Je Lieferant:
 1. Quellen kopieren (phase2_sources, ohne LLM)
 2. Belege wählen: PO/PI/CI/PL/TP/Spec/QC, je Dokument nur die neueste Fassung (xlsx vor pdf)
 3. Leser (claude -p, Sonnet) -> extract/, Prüfer (claude -p, Sonnet, ohne Einsicht in extract/) -> check/
 4. phase2_check --cross; Dateien mit Abweichung -> STOPP.md, werden NICHT geschrieben
 5. Inbox-Dokumente bauen (Bestellungen, Rechnungs-/Packlisten-Belege) -> auto_run Trockenlauf -> --apply (wiederholt, bis nichts Neues)
 6. Maße: measurements_p2 --apply (nur übereinstimmende Messpunkte, nur leere Produkte)
 7. ERGEBNIS.md + Zeile in MIGRATION_STATE.md
Harte Regeln bleiben in den Skripten: nur leere Felder, nie löschen, keine Bankdaten, Dublettenwache, Rücklesung."""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P2 = ROOT / "output" / "phase2"
CFG = P2 / "lieferanten.json"
TYPES = {"PO", "PI", "CI", "PL", "TP", "Spec", "QC"}
MAX_CHARS = 60000
GROUP = 15

SCHEMA = """{"fileId": "<id>", "doc_kind": "order|invoice|techpack|qc|plan|other",
 "product": {"style": null, "name": null},
 "order": {"po_number": null, "po_date": "YYYY-MM-DD", "currency": "USD", "incoterm": null, "total": 0, "pieces": 0,
           "items": [{"style": null, "name": null, "color": null, "sizes": {"S": 0}, "qty": 0, "price": 0, "sum": 0}], "payment_terms": []},
 "invoice": {"nr": null, "datum": null, "po_ref": null, "container": null, "bl": null, "mawb": null, "vessel": null,
             "cartons": null, "gross_kg": null, "net_kg": null, "cbm": null, "total": null, "pieces": null},
 "measurements": {"sizes": ["S"], "rows": [{"name": "Messpunkt", "values": {"S": 0}}]},
 "packaging": null, "abweichung": [],
 "facts": [{"key": "order.total", "value": 0, "src": {"zeile": 1, "zitat": "woertlich aus der Quelle"}}]}"""

RULES = """Regeln: Lies nur die genannten Dateien src/<id>.txt. Jede Zahl, jedes Datum, jeder Style braucht ein facts-Element mit src.zitat (WOERTLICH aus der Datei kopiert) und src.zeile. Zahlen als Zahl. Nichts schaetzen, nichts aus anderen Dateien oder dem Gedaechtnis; fehlt etwas -> null + "fehlt_grund". Summen der Quelle nicht glaetten, Widersprueche in "abweichung". doc_kind: order = PO/PI/Auftragsbestaetigung mit Positionen und Preisen; invoice = Rechnung/Packliste (dann invoice + order.total/pieces/items der Rechnung); techpack = Techpack/Spec/Massblatt (product + measurements, Toleranzen als eigene Zeile "Toleranz <Name>"); plan = Planungs-/Uebersichtsliste ohne verbindliche Bestellung; qc = Inspektionsbericht. Keine Bankdaten (IBAN, Konto, SWIFT) uebernehmen. Kein PLM-Zugriff, keine Mails, nichts senden, nichts teilen."""


def log(msg):
    print("[%s] %s" % (dt.datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def state(line):
    with open(ROOT / "output" / "MIGRATION_STATE.md", "a") as f:
        f.write("- %s %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), line))


def base_key(name):
    n = name.lower()
    n = re.sub(r"\.(pdf|xlsx|xlsm|xls|docx|csv|txt)$", "", n)
    n = re.sub(r"\s*\(\d+\)|\s*-?\s*copy|kopie", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


def select(sources):
    best, skipped = {}, []
    for s in sources:
        if s["typ"] not in TYPES or not s.get("lesbar"):
            continue
        if s.get("zeichen", 0) > MAX_CHARS:
            skipped.append((s, "zu gross (%d Zeichen), Mensch/Einzelauswertung" % s["zeichen"]))
            continue
        k = base_key(s["name"])
        rank = (s["datum"], s["name"].lower().endswith((".xlsx", ".xls", ".xlsm")), s.get("zeichen", 0))
        if k not in best or rank > best[k][0]:
            if k in best:
                skipped.append((best[k][1], "aeltere Fassung"))
            best[k] = (rank, s)
        else:
            skipped.append((s, "aeltere Fassung"))
    return [v[1] for v in best.values()], skipped


def claude(prompt, d):
    cmd = ["claude", "-p", prompt, "--model", "sonnet", "--permission-mode", "acceptEdits",
           "--allowedTools", "Read", "Write", "Edit", "Glob", "Grep", "Bash(python3:*)", "--add-dir", str(d)]
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}  # Claude-Login statt (ungueltigem) API-Key aus .env
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=3600, env=env, stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "")[-1500:] + (r.stderr or "")[-500:]


def read_round(d, ids, role):
    folder = "extract" if role == "leser" else "check"
    todo = [i for i in ids if not (d / folder / (i + ".json")).exists()]
    for k in range(0, len(todo), GROUP):
        part = todo[k:k + GROUP]
        if role == "leser":
            p = ("Leser-Agent Phase 2. Ordner %s. Dateien: %s. Schreibe je Datei %s/<id>.json (Dateiname = exakt die id inkl. Praefix att_, z.B. att_0dbc49a17da8.json) nach diesem Schema (nicht passende Bloecke weglassen):\n%s\n%s\n"
                 "Danach: python3 -m plm_intake.phase2_check %s ; Zitatfehler in DEINEN Dateien beheben (genauer zitieren). Antwort: nur Dateiliste.") % (d, ", ".join("src/%s.txt" % i for i in part), folder, SCHEMA, RULES, d)
        else:
            p = ("Pruef-Agent (unabhaengige zweite Lesung) Phase 2. Ordner %s. Lies NICHT den Ordner extract/. Dateien: %s. Schreibe je Datei %s/<id>.json (Dateiname = exakt die id inkl. Praefix att_, z.B. att_0dbc49a17da8.json) nach diesem Schema (nicht passende Bloecke weglassen):\n%s\n%s\n"
                 "Antwort: nur Dateiliste.") % (d, ", ".join("src/%s.txt" % i for i in part), folder, SCHEMA, RULES)
        log("%s %s: %d Dateien" % (d.name, role, len(part)))
        rc, out = claude(p, d)
        if rc:
            log("  claude Fehler rc=%s: %s" % (rc, out[-300:]))
            if any(k in out.lower() for k in ("api key", "login", "rate limit", "usage limit", "session limit", "hit your", "limit reached", "credit")):
                raise RuntimeError("claude -p nicht nutzbar: " + out[-200:])


def cross_ok(d):
    subprocess.run([sys.executable, "-m", "plm_intake.phase2_check", str(d), "--cross"], cwd=str(ROOT), capture_output=True, text=True)
    rep = (d / "check_report.md").read_text() if (d / "check_report.md").exists() else ""
    ok = set(re.findall(r"^- ok (\S+)\.json", rep, re.M))
    bad = {m.group(1): m.group(2) for m in re.finditer(r"^- FEHLER (\S+)\.json[^\n]*\n((?:    - [^\n]*\n?)*)", rep, re.M)}
    return ok, bad


def r2(x):
    return None if x in (None, "") else round(float(x), 2)


def used_elsewhere(slug, m):
    """Gleiche Anhang-Datei (Originalname + Groesse) schon bei einem ANDEREN Lieferanten verwendet? -> nicht automatisch schreiben."""
    key = (str(m.get("name", "")).lower(), m.get("groesse_bytes"))
    hits = []
    for f in P2.glob("*/sources.json"):
        other = f.parent.name
        if other == slug:
            continue
        for s in json.loads(f.read_text()):
            if (str(s.get("name", "")).lower(), s.get("groesse_bytes")) == key and s.get("typ") != "Mail":
                hits.append(other)
                break
    return hits


def order_keys(x):
    """Echte Kennungen einer bestehenden Order (PO-/PI-Nummer aus poNumber und Titel, ohne Lieferantenkuerzel und ohne von Claude vergebene Datum-Hash-Nummern)."""
    keys = set()
    if x.get("poNumber"):
        keys.add(str(x["poNumber"]))
    t = re.sub(r"^PO-", "", str(x.get("title") or ""), flags=re.I)
    rest = t.split("-", 1)[1] if "-" in t else t
    if not re.fullmatch(r"20\d\d-\d\d-\d\d-[0-9A-Fa-f]{4}", rest):
        for tok in re.split(r"[-_ ]", rest) + [rest]:
            if len(tok) >= 6 and re.search(r"\d{3}", tok) and re.search(r"[A-Za-z]", tok):
                keys.add(tok)
    return {re.sub(r"[^A-Z0-9]", "", k.upper()) for k in keys if k}


def dup_order(o, orders, vendor=None, src_text=""):
    """Bestehende Order DESSELBEN Lieferanten mit gleicher Stueckzahl (+-1 %%) oder gleicher Summe -> Dubletten-Verdacht."""
    pcs, tot = float(o.get("pieces") or 0), float(o.get("total") or 0)
    for x in orders:
        if vendor and ((x.get("manufacturer") or {}).get("name") or "").lower() != vendor.lower():
            continue
        xp, xt = float(x.get("totalNumberOfPieces") or 0), float(x.get("totalCost") or 0)
        if (pcs and xp and abs(xp - pcs) <= 0.01 * pcs) or (tot and xt and abs(xt - tot) < 0.01):
            return x
        flat = re.sub(r"[^A-Z0-9]", "", src_text.upper())
        if flat and any(k and k in flat for k in order_keys(x)):
            return x  # Beleg nennt die PO-/PI-Nummer einer bestehenden Order dieses Lieferanten
    return None


def build_inbox(d, slug, vendor, ok, meta, products, orders=(), mensch=None, names=()):
    mensch = mensch if mensch is not None else []
    inbox = d / "p2inbox"
    inbox.mkdir(exist_ok=True)
    known = {re.sub(r"[^A-Z0-9]", "", str(p.get("sku") or "").upper()) for p in products}
    made = {"order": 0, "invoice": 0}
    for i in sorted(ok):
        x = json.loads((d / "extract" / (i + ".json")).read_text())
        o, inv, kind = x.get("order") or {}, x.get("invoice") or {}, x.get("doc_kind")
        m = meta.get(i, {})
        other = used_elsewhere(slug, m)
        if other:
            mensch.append("%s (%s): Datei auch bei %s -> Lieferant unklar, nicht geschrieben" % (i, m.get("name"), ",".join(other)))
            continue
        if kind == "order":
            txt = (d / "src" / (i + ".txt")).read_text(errors="replace").lower() if (d / "src" / (i + ".txt")).exists() else ""
            own = [t.lower() for t in names] + [vendor.lower().split()[0]]
            if txt and not any(t in txt for t in own):
                mensch.append("%s (%s): Lieferantenname (%s) steht nicht im Beleg -> Lieferant unklar, nicht angelegt" % (i, m.get("name"), "/".join(own)))
                continue
            dup = dup_order(o, orders, vendor, txt)
            if dup:
                mensch.append("%s (%s): %s Stk / %s wie bestehende #%s %s -> Dubletten-Verdacht, nicht angelegt" % (i, m.get("name"), o.get("pieces"), o.get("total"), dup.get("orderNumber"), dup.get("title")))
                continue
        src = {"doc": m.get("name"), "mail_id": m.get("mail_id"), "mail_date": m.get("datum")}
        if kind == "order" and o.get("items") and o.get("total"):
            items = []
            for it in o["items"]:
                s = {k: int(v) for k, v in (it.get("sizes") or {}).items() if v}
                if not it.get("qty"):
                    continue
                if sum(s.values()) != it["qty"]:
                    s = {"ONE SIZE": int(it["qty"])}
                st = re.sub(r"\s+", "", str(it.get("style") or "")) or None
                sku = st if st and re.sub(r"[^A-Z0-9]", "", st.upper()) in known else None
                items.append({"sku": sku, "name": " ".join(v for v in (st, it.get("name")) if v), "variants": [{"color": it.get("color") or "Default Style", "price": it.get("price") or 0, "sizes": s}]})
            if not items:
                continue
            pn = o.get("po_number") or "%s-%s-%s" % (slug.upper(), o.get("po_date") or m.get("datum"), i[-4:])
            notes = "Phase 2 (Quelle %s, Mail %s). PO-Datum %s, Incoterm %s. Zahlungsbedingungen: %s. %s%s" % (
                m.get("name"), m.get("datum"), o.get("po_date"), o.get("incoterm"), o.get("payment_terms") or "-",
                "; ".join(map(str, x.get("abweichung") or []))[:500], "" if o.get("po_number") else " PO-Nr. nicht in der Quelle, von Claude vergeben.")
            doc = {"doc_type": "PO", "source": src, "vendor": vendor, "po_number": pn, "doc_date": o.get("po_date"), "currency": o.get("currency") or "USD",
                   "incoterm": o.get("incoterm"), "ex_factory": None, "etd": None, "items": items, "payments": [], "total_cost": o["total"],
                   "total_pieces": o.get("pieces"), "contract_total": None, "notes": notes}
            made["order"] += 1
        elif kind == "invoice" and (inv.get("nr") or o.get("total")):
            parts = ["Rechnung/Packliste %s vom %s: %s Stk, Warenwert %s %s" % (inv.get("nr"), inv.get("datum"), o.get("pieces") or inv.get("pieces"), r2(o.get("total") or inv.get("total")), o.get("currency") or "USD")]
            for k, lab in (("cartons", "Kartons"), ("gross_kg", "Brutto kg"), ("net_kg", "Netto kg"), ("cbm", "CBM"), ("container", "Container"), ("bl", "B/L"), ("mawb", "MAWB"), ("vessel", "Schiff")):
                if inv.get(k):
                    parts.append("%s %s" % (lab, r2(inv[k]) if isinstance(inv[k], (int, float)) else inv[k]))
            if x.get("abweichung"):
                parts.append("Hinweis Quelle: " + "; ".join(map(str, x["abweichung"]))[:300])
            doc = {"doc_type": "INVOICE", "source": src, "vendor": vendor, "po_number": inv.get("po_ref") or inv.get("nr"), "currency": o.get("currency") or "USD",
                   "items": [], "payments": [], "total_cost": o.get("total") or inv.get("total"), "total_pieces": o.get("pieces") or inv.get("pieces"), "notes": ", ".join(parts)}
            made["invoice"] += 1
        else:
            continue
        (inbox / (i + ".json")).write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return inbox, made


def auto_run(d, inbox, apply):
    intake = d / "p2intake"
    intake.mkdir(exist_ok=True)
    for f in ("config.json", "vendor_aliases.json"):
        if (ROOT / "output/intake" / f).exists() and not (intake / f).exists():
            (intake / f).write_text((ROOT / "output/intake" / f).read_text())
    cmd = [sys.executable, "-m", "plm_intake.auto_run", "--inbox", str(inbox), "--intake", str(intake)] + (["--apply"] if apply else [])
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}  # Claude-Login statt (ungueltigem) API-Key aus .env
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=3600, env=env, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def one(slug, cfg, dry):
    d = P2 / slug
    d.mkdir(parents=True, exist_ok=True)
    rep = ["# Phase 2 %s (%s)" % (slug, dt.datetime.now().strftime("%Y-%m-%d %H:%M")), ""]
    log("%s: Quellen" % slug)
    args = [sys.executable, "-m", "plm_intake.phase2_sources", slug] + sum((["--domain", x] for x in cfg["domain"]), []) + sum((["--name", x] for x in cfg["name"]), [])
    if not (d / "sources.json").exists():
        subprocess.run(args, cwd=str(ROOT), check=True, timeout=7200)
    sources = json.loads((d / "sources.json").read_text())
    meta = {s["id"]: s for s in sources}
    sel, skipped = select(sources)
    rep += ["Quellen: %d, ausgewaehlt %d, uebersprungen %d" % (len(sources), len(sel), len(skipped)), ""]
    ids = [s["id"] for s in sel]
    (d / "auswahl.json").write_text(json.dumps({"ids": ids, "uebersprungen": [[s["id"], s["name"], why] for s, why in skipped]}, ensure_ascii=False, indent=1))
    read_round(d, ids, "leser")
    read_round(d, ids, "pruefer")
    if ids and not list((d / "extract").glob("*.json")):
        raise RuntimeError("Leser hat keine Extrakte geliefert (Limit/Fehler) - Lieferant NICHT fertig")
    ok, bad = cross_ok(d)
    ok &= set(ids) | {f.stem for f in (d / "extract").glob("*.json")}
    rep += ["Gegenprobe: %d gleich, %d Abweichung (STOPP.md)" % (len(ok), len(bad)), ""]
    if bad:
        (d / "STOPP.md").write_text("# STOPP %s: Leser und Pruefer weichen ab, NICHT geschrieben\n\n" % slug + "\n".join("- %s (%s)\n%s" % (k, meta.get(k, {}).get("name"), v) for k, v in sorted(bad.items())))
    import plm_client
    from plm_intake.context import fetch_all
    for t in range(5):
        try:
            products = fetch_all(plm_client.call, "products")
            break
        except Exception as e:  # noqa: BLE001 - PLM-Timeout: kurz warten, erneut
            log("PLM-Lesefehler (%s), Versuch %d" % (str(e)[:80], t + 1))
            import time
            time.sleep(60)
    else:
        raise RuntimeError("PLM nicht erreichbar")
    orders = fetch_all(plm_client.call, "orders")
    mensch = []
    inbox, made = build_inbox(d, slug, cfg["vendor"], ok, meta, products, orders, mensch, cfg["name"] + cfg["domain"])
    if mensch:
        (d / "MENSCH.md").write_text("# %s: nicht automatisch geschrieben\n\n" % slug + "\n".join("- " + x for x in mensch))
        rep.append("Mensch (MENSCH.md): %d" % len(mensch))
    rep.append("Inbox: %d Bestellungen, %d Belege" % (made["order"], made["invoice"]))
    rc, out = auto_run(d, inbox, False)
    (d / "p2_dry.txt").write_text(out)
    mensch = re.search(r"## Mensch entscheidet \((\d+)\)", out)
    rep.append("Trockenlauf rc=%s, Mensch entscheidet: %s" % (rc, mensch.group(1) if mensch else "?"))
    if not dry and rc == 0:
        for n in range(6):
            rc, out = auto_run(d, inbox, True)
            (d / ("p2_apply_%d.txt" % n)).write_text(out)
            done = re.search(r"Erledigt: (\{.*\})", out)
            res = json.loads(done.group(1)) if done else {}
            rep.append("Lauf %d rc=%s: %s" % (n + 1, rc, res or out[-200:]))
            if rc or not (res.get("orders") or res.get("event_orders") or res.get("shipments")):
                break
        r = subprocess.run([sys.executable, "-m", "plm_intake.measurements_p2", str(d), "--apply"], cwd=str(ROOT), capture_output=True, text=True, timeout=3600)
        rep += ["", "## Masse", r.stdout[-2500:]]
    (d / "ERGEBNIS.md").write_text("\n".join(rep))
    state("PHASE2 %s %s: %s" % ("TROCKENLAUF" if dry else "FERTIG", slug, " | ".join(x for x in rep[2:8] if x)))
    log("%s fertig" % slug)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int)
    ap.add_argument("--lieferant", action="append", default=[])
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    cfg = json.loads(CFG.read_text())
    slugs = a.lieferant or (cfg["batches"][a.batch - 1] if a.batch else [])
    for s in slugs:
        try:
            one(s, cfg["lieferanten"][s], a.dry)
        except Exception as e:  # noqa: BLE001 - naechster Lieferant
            log("%s ABBRUCH: %s" % (s, e))
            (P2 / s).mkdir(parents=True, exist_ok=True)
            (P2 / s / "STOPP.md").write_text("# ABBRUCH %s\n\n%s\n" % (s, e))
            state("PHASE2 ABBRUCH %s: %s" % (s, str(e)[:200]))
            if "nicht nutzbar" in str(e) or "keine Extrakte" in str(e):
                log("Claude nicht verfuegbar -> gesamter Lauf gestoppt")
                break


if __name__ == "__main__":
    main()
