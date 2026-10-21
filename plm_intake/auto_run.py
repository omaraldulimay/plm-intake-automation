"""Alltagslauf: Drive-Inbox -> neue Lieferanten -> Pruefung -> neue POs / Belege / Ereignisse als Notizen -> PLM (Browser-Skript) -> Bericht.

  python3 -m plm_intake.auto_run                 # TROCKENLAUF: plant alles, schreibt NICHTS ins PLM, Bericht in output/intake/auto_report.md
  python3 -m plm_intake.auto_run --apply         # fuehrt aus (Lieferanten anlegen, POs anlegen, Notizen schreiben) und merkt erledigte Dateien im Merkbuch
Reihenfolge: (1) Lieferanten (vendors_new.auto) (2) PLM-Stand frisch lesen (3) neue Bestellungen (core.build -> CREATE) (4) Belege zu bestehenden Orders (docs_existing)
(5) Ereignisse (events) (6) Browser-Skripte per plm_intake/browser/run_in_plm.js (7) Rueckpruefung + Merkbuch + Bericht.
Nie: loeschen, Mengen/Preise/Zahlungen bestehender Orders aendern, blind wiederholen (bei unsicherem Ergebnis stoppt der Lauf).
Menschen-Liste im Bericht: Blocker, mehrdeutige Belege, Belege ohne PO, Reorder-Fragen, nicht zuordenbare Ereignisse.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core, daily, docs_existing, events, ledger, new_products, run, shipments as shp, vendors_new  # noqa: E402

INTAKE = ROOT / "output" / "intake"
MAX_NEW_POS_PER_RUN = 3
BROWSER = ROOT / "plm_intake" / "browser"


def browser(js_path):
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), str(js_path)], capture_output=True, text=True, cwd=BROWSER, timeout=600)
    if r.returncode:
        raise SystemExit("Browser-Lauf gescheitert (%s): %s" % (js_path.name, (r.stderr or r.stdout)[-400:]))
    return json.loads(r.stdout)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--inbox")
    ap.add_argument("--intake", default=str(INTAKE))
    ap.add_argument("--overrides", default=str(INTAKE / "overrides.json"))
    a = ap.parse_args(argv)
    intake = Path(a.intake); intake.mkdir(parents=True, exist_ok=True)
    inbox = daily.resolve_inbox(a.inbox, intake)
    if not inbox.exists():
        print("Inbox nicht gefunden:", inbox); return 2
    led_path = intake / "ledger.json"; led = ledger.load(led_path)
    docs, evs = daily.pending(inbox, led)
    rep = ["# Alltagslauf %s (%s)" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "",
           "Neu: %d Dokument-Dateien, %d Ereignis-Dateien" % (len(docs), len(evs)), ""]
    import plm_client
    from plm_intake.context import load_context

    # (1) Lieferanten
    st, vl = plm_client.call("GET", "vendors"); vl = vl if isinstance(vl, list) else vl.get("data", vl)
    valias = json.load(open(intake / "vendor_aliases.json")) if (intake / "vendor_aliases.json").exists() else {}
    vres = vendors_new.auto(inbox, vl, a.apply, valias)
    rep += ["## Lieferanten"] + (["- %s: %s %s" % (v["name"], v["status"], v.get("why") or v.get("hint") or "") for v in vres] or ["- keine neuen"]) + [""]

    # (2) PLM-Stand
    ctx = load_context()
    from plm_intake.context import add_po_numbers
    rep += ["PO-Nummern per Browser nachgeladen: %d" % add_po_numbers(ctx), ""]
    ctx["aliases"] = json.load(open(intake / "vendor_aliases.json")) if (intake / "vendor_aliases.json").exists() else {}
    po_aliases = json.load(open(intake / "po_aliases.json")) if (intake / "po_aliases.json").exists() else {}
    overrides = json.load(open(a.overrides)) if Path(a.overrides).exists() else {}

    # (3) neue Bestellungen
    items = []
    for f in docs:
        try: items.append((f.name, json.load(open(f))))
        except ValueError as e: items.append((f.name, {"_unreadable": str(e)}))
    force = {n for n, v in overrides.items() if v == "CREATE"}
    results = run.process(items, ctx, force=force)
    style_aliases = json.load(open(intake / "style_aliases.json")) if (intake / "style_aliases.json").exists() else {}
    ctx["style_aliases"] = style_aliases
    docs_by_name = dict(items)
    specs_all, skipped_all = {}, []
    allowed = [n for n, r in results if r.decision == "CREATE"][:MAX_NEW_POS_PER_RUN]   # Produkte nur fuer POs, die in diesem Lauf wirklich angelegt werden (Limit)
    for n, r in results:
        if r.decision != "CREATE" or n not in allowed:
            continue
        po = docs_by_name[n]
        vendor, _ = core.match_vendor(po.get("vendor") or "", ctx["vendors"], ctx["aliases"])
        if not vendor:
            continue
        sp, sk = new_products.plan_products(po, vendor, ctx["products"], style_aliases)
        for x in sp:
            specs_all.setdefault(x["sku"], x)
        skipped_all += [(n, a, b) for a, b in sk]
    rep += ["## Neue Produkte (Stylenummer des Lieferanten als vorlaeufige SKU, Tag SKU-OFFEN)"]
    rep += (["- %s | %s | Groessen %s | Farben %s" % (x["sku"], x["name"], ",".join(x["sizes"]), ",".join(x["colors"]) or "-") for x in specs_all.values()] or ["- keine"])
    rep += ["- nicht angelegt (%s): %s" % (n, "%s: %s" % (a, b)) for n, a, b in skipped_all] + [""]
    if a.apply and specs_all:
        def find_product(sku):
            st, d = plm_client.call("GET", "products", search=sku)
            lst = d if isinstance(d, list) else d.get("data", [])
            return next((x for x in lst if x.get("sku") == sku), None)
        try:
            new_products.create_products(list(specs_all.values()), find_product, log=lambda m: rep.append("- " + m))
        except Exception as e:
            rep += ["", "ABBRUCH bei Produktanlage: %s. Nichts wiederholen, Stand im PLM pruefen." % e]
            (intake / "auto_report.md").write_text("\n".join(rep)); print("\n".join(rep)); return 1
        from plm_intake.context import fetch_all
        ctx["products"] = fetch_all(plm_client.call, "products")
        results = run.process(items, ctx, force=force)   # jetzt mit Produkt-/Varianten-Links
    payloads = {n: r.payload for n, r in results if r.decision == "CREATE"}
    forced_open = [(n, r) for n, r in results if n in force and r.decision != "CREATE"]   # Mensch wollte CREATE, aber die Pruefung laesst es nicht zu: nie stillschweigend
    over = list(payloads)[MAX_NEW_POS_PER_RUN:]   # Sicherheitsgrenze: mehr als N neue POs in einem Lauf wartet auf einen Menschen
    for n in over:
        payloads.pop(n)
    rep += ["## Neue Bestellungen (CREATE)"] + (["- %s -> %s (%s Stk, %s)" % (n, p["title"], p["totalNumberOfPieces"], p["totalCost"]) for n, p in payloads.items()] or ["- keine"]) + [""]

    # (4) Belege zu bestehenden Orders -> Ereignis-Dateien
    rows, ev_files = docs_existing.run(inbox, ctx, overrides, intake, only={f.name for f in docs})
    rep += ["## Belege zu bestehenden Bestellungen", docs_existing.report(rows)]
    doc_event_paths = sorted((intake / "doc_events").glob("*_events.json"))

    # (5) Ereignisse (Mail-Ereignisse + Beleg-Ereignisse in EINEM Plan, Marker verhindern Doppel-Zeilen)
    # Belegnummern, die oben EINDEUTIG einer Order zugeordnet wurden (Rechnung LIEFERANT_AA26104, AK/623/26, ...-AIR), gelten fuer Ereignisse derselben Nummer als Alias
    by_id = {o["id"]: o["title"] for o in ctx["orders"]}
    for r in rows:
        if r.get("pid") and r.get("po") and r["pid"] in by_id:
            po_aliases.setdefault(str(r["po"]), by_id[r["pid"]])
    evt = events.load_events(evs) + events.load_events(doc_event_paths)
    pl = events.plan(evt, ctx["orders"], ctx["vendors"], po_aliases, ctx["aliases"], vendor_only=True, products=ctx["products"], style_aliases=style_aliases)
    rep += ["## Notizen/Ereignisse", events.report(pl)]

    # (5b) Sendungen: Packlisten/Rechnungen -> Sendung je Beleg (pending), Versand-Meilensteine -> in_transit/delivered + Tracking
    from plm_intake.context import fetch_all, fetch_order_details
    ship_now = fetch_all(plm_client.call, "shipments")
    deliveries = [(r["file"], r["doc"], r["pid"]) for r in rows if r.get("kind") == "DELIVERY_DOC" and r.get("doc_type") in ("INVOICE", "PACKING_LIST") and r.get("pid")]
    ev_ship = {o["id"]: (o["title"], o["ship"]) for o in pl["orders"] if o.get("ship")}
    need = {d[2] for d in deliveries} | set(ev_ship)
    detail = fetch_order_details(need) if need else {}
    pby = {x["id"]: x.get("sku") for x in ctx["products"]}
    sh_create, sh_update, sh_human = [], [], []
    c1, h1 = shp.plan_from_docs(deliveries, detail, ship_now, pby)
    sh_create += c1; sh_human += h1
    for oid, (title, evl) in ev_ship.items():
        c2, u2, h2 = shp.plan_from_events(oid, title, evl, detail, ship_now + [{"notes": c["notes"], "products": [{"orderId": oid}]} for c in sh_create if False])
        sh_create += c2; sh_update += u2; sh_human += h2
    rep += ["## Sendungen (Bereich Shipments)"]
    rep += ["- neu: %s (%s, %s, %s Pos.)" % (c["title"], c["method"], c["status"], len(c["products"])) for c in sh_create]
    rep += ["- aktualisiert: %s %s" % (u["title"], {k: v for k, v in u["patch"].items() if k != "notes"}) for u in sh_update]
    rep += ["- Mensch: %s: %s" % (n, w) for n, w in sh_human]
    if not (sh_create or sh_update or sh_human): rep += ["- keine"]
    rep += [""]

    js_run = js_ev = None
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if payloads:
        js_run = intake / ("run_%s.js" % stamp); js_run.write_text(run.make_js(list(payloads.values()), not a.apply))
    if pl["orders"]:
        js_ev = intake / ("events_%s.js" % stamp); js_ev.write_text(events.make_js(pl))

    applied = {"orders": [], "event_orders": [], "shipments": []}
    if a.apply:
        if sh_create or sh_update:
            try:
                slog = shp.apply(sh_create, sh_update, plm_client.call)
            except Exception as e:
                rep += ["", "ABBRUCH bei Sendungen: %s" % e]
                (intake / "auto_report.md").write_text("\n".join(rep)); print("\n".join(rep)); return 1
            after = fetch_all(plm_client.call, "shipments")
            missing = [c["title"] for c in sh_create if not any(x.get("title") == c["title"] for x in after)]
            rep += ["## Ergebnis Sendungen"] + ["- " + l for l in slog] + (["- FEHLT nach Anlage: %s" % missing] if missing else ["- per REST zurueckgelesen: alle vorhanden"]) + [""]
            applied["shipments"] = [c["title"] for c in sh_create] + [u["title"] for u in sh_update]
        if js_run:
            res = browser(js_run); rep += ["## Ergebnis PO-Anlage", "```", json.dumps(res, ensure_ascii=False, indent=1), "```"]
            if any(r.get("error") or r.get("fatal") or r.get("unsure") for r in res):
                rep += ["", "ABBRUCH: unsicheres Ergebnis bei der PO-Anlage. Nichts wiederholen, per REST nach Titel pruefen."]
                (intake / "auto_report.md").write_text("\n".join(rep)); print("\n".join(rep)); return 1
            applied["orders"] = [r["title"] for r in res if r.get("orderNumber")]
        if js_ev:
            res = browser(js_ev); rep += ["## Ergebnis Notizen", "```", json.dumps(res, ensure_ascii=False, indent=1), "```"]
            bad = [r for r in res if r.get("error") or r.get("fatal") or r.get("ABBRUCH") or r.get("dataUnchanged") is False or r.get("notesOk") is False or r.get("datesOk") is False or r.get("statusOk") is False]
            if bad:
                rep += ["", "ABBRUCH: Rueckpruefung der Notizen meldet Abweichung: %s" % bad]
                (intake / "auto_report.md").write_text("\n".join(rep)); print("\n".join(rep)); return 1
            applied["event_orders"] = [r["title"] for r in res]
        # Merkbuch: neue POs, Belege mit Ereignis, vollstaendig zugeordnete Ereignis-Dateien
        for n, p in payloads.items():
            if p["title"] in applied["orders"]: ledger.mark(led, inbox / n, "applied", p["title"])
        for stem in ev_files:
            f = inbox / (stem + ".json")
            if f.exists() and applied["event_orders"]: ledger.mark(led, f, "applied")
        done_titles = set(applied["event_orders"])   # nur wirklich geschriebene Orders (Lauf kann vorher abbrechen)
        matched = {l["marker"] for o in pl["orders"] if o.get("title") in done_titles for l in o["lines"]}
        for f in evs:
            ids = [events.marker(e) for e in events.load_events([f])]
            if ids and all(m in matched for m in ids) and applied["event_orders"]: ledger.mark(led, f, "applied")
        ledger.save(led_path, led)
    # Klaerfaelle -> PLM-Tabelle "Klärfälle Einpflege" (nur echte, bestellbezogene Faelle; zugeordnete werden abgehakt)
    try:
        from plm_intake import klaerfaelle
        if klaerfaelle.CFG.exists():
            if a.apply:
                def _run(js):
                    p_ = intake / ("klaerfaelle_%s.js" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")); p_.write_text(js); return browser(p_)
                kf_rows, kf_res = klaerfaelle.sync(pl, ctx, ctx.get("aliases"), runner=_run)
                rep += ["", "## Klärfälle (PLM-Tabelle)", "- Kandidaten %d, neu eingetragen %s, abgehakt %s, offen gesamt %s%s" % (
                    len(kf_rows), kf_res.get("created"), kf_res.get("closed"), kf_res.get("open_total"), (" | Fehler: %s" % kf_res["errors"][:3]) if kf_res.get("errors") else "")]
            else:
                kf_rows = klaerfaelle.select(pl["unmatched"], ctx["vendors"], ctx.get("aliases"), events.domain_vendors(ctx["vendors"]))
                rep += ["", "## Klärfälle (PLM-Tabelle)", "- %d Faelle wuerden eingetragen bzw. stehen schon drin (Trockenlauf)" % len(kf_rows)]
    except (Exception, SystemExit) as e:   # Klaerfaelle duerfen den Lauf nie abbrechen
        rep += ["", "## Klärfälle (PLM-Tabelle)", "- FEHLER: %s" % str(e)[:200]]
    # Techpacks/Specs aus neuen Mail-Anhaengen als Datei ans Produkt (Fehler brechen den Lauf nie ab; Trockenlauf schreibt nichts)
    try:
        from plm_intake import techpack_daily
        tp_lines, _ = techpack_daily.run(ctx["products"], intake / techpack_daily.STATE_NAME, apply=a.apply)
        rep += ["", "## Techpacks"] + tp_lines
    except (Exception, SystemExit) as e:
        rep += ["", "## Techpacks", "- FEHLER: %s" % str(e)[:200]]
    # Menschen-Liste
    human = [r for r in rows if r["kind"] in ("BLOCKER", "AMBIGUOUS_DOC", "ORPHAN_DOC", "REORDER_QUESTION", "OTHER_BLOCK", "FEHLER")]
    blocked = [(n, r) for n, r in results if r.decision != "CREATE" and n not in {x["file"] for x in rows}]
    um_h = [u for u in pl["unmatched"] if not str(u["reason"]).startswith("info:")]
    rep += ["", "## Mensch entscheidet (%d)" % (len(human) + len(um_h) + len(sh_human) + len(over) + len(forced_open))]
    rep += ["- CREATE gewollt, aber nicht moeglich (%s): %s" % (n, "; ".join(i.msg for i in r.issues if i.level == "ERROR" or i.code in ("duplicate", "exists_changed"))[:300] or r.decision) for n, r in forced_open]
    rep += ["- Neue PO nicht angelegt (Limit %d pro Lauf): %s" % (MAX_NEW_POS_PER_RUN, n) for n in over]
    rep += ["- Sendung: %s: %s" % (n, w) for n, w in sh_human]
    rep += ["- %s: %s %s" % (r["file"], r["kind"], r.get("why") or r.get("parent") or r.get("po") or "") for r in human]
    rep += ["- Ereignis nicht zuordenbar: %s (%s)" % ((u["event"].get("summary") or "")[:90], u["reason"]) for u in um_h]
    out = "\n".join(rep) + "\n"
    (intake / "auto_report.md").write_text(out)
    print(out)
    print("Erledigt: %s" % json.dumps(applied, ensure_ascii=False) if a.apply else "TROCKENLAUF: nichts geschrieben. Mit --apply ausfuehren.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
