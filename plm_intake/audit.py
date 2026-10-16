"""Stichprobe gegen die Quelle (nur lesen): vergleicht zufaellige, bereits eingepflegte Inbox-Dateien mit dem, was jetzt im PLM steht.

  python3 -m plm_intake.audit [--n 10] [--seed 1]
Prueft (1) angelegte POs: Stueck, Wert, Positionen/Mengen je Position gegen die Inbox-JSON, (2) eingepflegte Ereignisse: Marker ev:<hash> steht in den Notizen irgendeiner Order,
(3) alle Orders: keine Bankdaten in den Notizen, keine Dubletten (Vendor + PO-Nr). Bericht: output/intake/audit_<Datum>.md, Exit 1 bei Befund.
Grenze: vergleicht Inbox-Datei <-> PLM (faengt Fehler der Einpflege). Hat das Auslesen selbst falsch gelesen, steht es schon in der Inbox-Datei; dafuer prueft die Auslese eigene Summen."""
import argparse
import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core, daily, events, health, ledger  # noqa: E402

BANK = [re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b"), re.compile(r"swift[^\n]{0,60}", re.I), re.compile(r"\biban\b[^\n]{0,60}", re.I),
        re.compile(r"beneficiary[^\n]{0,20}a/?c[^\n]{0,60}", re.I), re.compile(r"account\s*(no|number|nr)[^\n]{0,60}", re.I)]


def source_totals(doc):
    """Stueck, Wert und Menge je Position aus der Inbox-JSON (Positionen ohne Menge zaehlen nicht)."""
    pcs, cost, per = 0, 0.0, []
    for it in doc.get("items") or []:
        q = 0
        for v in it.get("variants") or []:
            sz = v.get("sizes") or {}
            n = sum(float(x or 0) for x in sz.values()) if sz else float(v.get("quantity") or 0)
            q += n; cost += n * float(v.get("price") or 0)
        if q:
            per.append(int(round(q)))
        pcs += q
    return int(round(pcs)), round(cost, 2), sorted(per)


def live_totals(order):
    pcs, per = 0, []
    for it in order.get("items") or []:
        q = sum(a.get("quantity") or 0 for v in it.get("variants") or [] for a in v.get("amounts") or [])
        if q:
            per.append(int(round(q)))
        pcs += q
    return int(round(pcs)), round(order.get("totalCost") or 0, 2), sorted(per)


def compare(name, doc, order):
    sp, sc, sper = source_totals(doc); lp, lc, lper = live_totals(order)
    bad = []
    if sp != lp:
        bad.append("%s: Stueck Quelle %s != PLM %s" % (name, sp, lp))
    if abs(sc - lc) > max(core.TOL, 0.005 * sc):
        bad.append("%s: Wert Quelle %.2f != PLM %.2f" % (name, sc, lc))
    if sper != lper:
        bad.append("%s: Mengen je Position Quelle %s != PLM %s" % (name, sper, lper))
    return bad


def bank_findings(orders):
    out = []
    for o in orders:
        text = "%s\n%s" % (o.get("notes") or "", o.get("_notes") or "")
        if any(rx.search(text) for rx in BANK):
            out.append("BANKDATEN? in Notizen von #%s %s" % (o.get("orderNumber"), o.get("title")))
    return out


def pick(names, n, seed=None):
    names = sorted(names)
    return random.Random(seed).sample(names, min(n, len(names)))


def run(inbox, intake, orders, n=10, seed=None):
    """orders: REST-Orders mit _notes (add_po_numbers). Rueckgabe (Befunde, Zeilen)."""
    led = ledger.load(Path(intake) / "ledger.json")
    created = [k for k, v in led.items() if v.get("status") == "applied" and v.get("title") and not k.endswith("_events.json")]
    evfiles = [k for k, v in led.items() if v.get("status") == "applied" and k.endswith("_events.json")]
    by_title = {}
    for o in orders:
        by_title.setdefault(core.norm(o.get("title")), []).append(o)
    allnotes = "\n".join("%s\n%s" % (o.get("notes") or "", o.get("_notes") or "") for o in orders)
    bad, info = [], []
    for k in pick(created, n, seed):
        f = Path(inbox) / k
        if not f.exists():
            info.append("%s: Inbox-Datei fehlt (uebersprungen)" % k); continue
        hits = by_title.get(core.norm(led[k]["title"]), [])
        if len(hits) != 1:
            bad.append("%s: PO '%s' %d-mal im PLM" % (k, led[k]["title"], len(hits))); continue
        with open(f) as fh:
            b = compare(k, json.load(fh), hits[0])
        bad += b
        info.append("%s -> %s: %s" % (k, led[k]["title"], "stimmt" if not b else "ABWEICHUNG"))
    for k in pick(evfiles, n, seed):
        f = Path(inbox) / k
        if not f.exists():
            continue
        miss = [events.marker(e) for e in events.load_events([f]) if "ev:" + events.marker(e) not in allnotes]
        if miss:
            bad.append("%s: Marker %s nicht in den Notizen" % (k, ",".join(miss)))
        info.append("%s: Notizen %s" % (k, "vorhanden" if not miss else "FEHLEN"))
    bad += bank_findings(orders)
    seen = {}
    for o in orders:
        if o.get("poNumber"):
            mid = o["manufacturer"].get("id") if isinstance(o.get("manufacturer"), dict) else o.get("manufacturer")
            seen.setdefault((mid, core.norm(o["poNumber"])), []).append(o.get("orderNumber"))
    bad += ["DUBLETTE: Vendor %s PO-Nr %s in #%s" % (k[0], k[1], ", #".join(map(str, v))) for k, v in seen.items() if len(v) > 1]
    return bad, info


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10); ap.add_argument("--seed", type=int)
    ap.add_argument("--inbox"); ap.add_argument("--intake", default=str(daily.INTAKE))
    a = ap.parse_args(argv)
    intake = Path(a.intake); inbox = daily.resolve_inbox(a.inbox, intake)
    import plm_client
    from plm_intake.context import add_po_numbers, fetch_all
    orders = fetch_all(plm_client.call, "orders")
    ctx = {"orders": orders}
    add_po_numbers(ctx)
    bad, info = run(inbox, intake, orders, a.n, a.seed)
    rep = ["# Stichprobe %s: %d Befund(e)" % (dt.date.today().isoformat(), len(bad)), ""] + ["- BEFUND: " + b for b in bad] + ["- " + i for i in info]
    (intake / ("audit_%s.md" % dt.date.today().strftime("%Y%m%d"))).write_text("\n".join(rep) + "\n")
    print("\n".join(rep))
    if bad:
        health.alert(intake, "Stichprobe: %d Befund(e)" % len(bad), bad[0])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
