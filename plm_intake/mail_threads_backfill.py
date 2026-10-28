"""Rueckwirkend: Thread-ID in die Ereignis-Dateien und gelernten Stand output/intake/mail_threads.json aufbauen. NUR LOKAL, schreibt nichts ins PLM.

1) Mail-Archive (PLM-Mails/mails_*.txt, Bloecke 'Message-ID:' + 'Thread-ID:') -> Message-ID -> Thread-ID.
2) Noch nicht erledigte Inbox/*_events.json (Merkbuch beachten) ohne 'thread_id' bekommen es ergaenzt. ERLEDIGTE Dateien werden nie angefasst
   (das Merkbuch vergleicht den Datei-Hash; eine Aenderung wuerde sie erneut einspielen).
3) Aus ALLEN Ereignis-Dateien (erledigte + offene, Thread-ID nur im Speicher) wird per events.plan der Zuordnungsstand gerechnet; sicher zugeordnete Ereignisse
   -> mail_threads.json (zum bestehenden Stand hinzu).
Trockenlauf ist Standard (zeigt Zahlen und wie viele Klaerfaelle durch die Verlauf-Zuordnung wegfallen); --apply schreibt Dateien + Zustand.

  python3 -m plm_intake.mail_threads_backfill [--inbox DIR] [--apply]"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import events, klaerfaelle, ledger, mail_threads  # noqa: E402

PAIR = re.compile(r"^Message-ID: (\S+)\s*\nThread-ID: (\S+)", re.M)


def thread_map(root=None):
    """Message-ID -> Thread-ID aus allen Mail-Archiven."""
    out = {}
    for f in Path(root or klaerfaelle.MAILS).rglob("*.txt"):
        try:
            txt = f.read_text(errors="ignore")
        except OSError:
            continue
        for m, t in PAIR.findall(txt):
            out[m] = t
    return out


def with_threads(evs, th):
    """Ereignisse ohne Thread bekommen ihn (im Speicher) aus der Archiv-Zuordnung."""
    for e in evs:
        m = e.get("_mail") or {}
        if not m.get("thread"):
            m["thread"] = th.get(str(m.get("id")))
    return evs


def run(inbox, intake, ctx, th, apply=False, dirs=None):
    led = ledger.load(Path(intake) / "ledger.json")
    files = sorted(Path(inbox).glob("*_events.json"))
    res = Counter()
    patch = []
    for f in files:
        d = json.load(open(f))
        if d.get("thread_id"):
            res["Datei hat thread_id"] += 1; continue
        t = th.get(str(d.get("mail_id")))
        done = ledger.is_done(led, f)
        if done:
            res["erledigt (nicht angefasst)"] += 1
        elif not t:
            res["offen, Thread unbekannt"] += 1
        else:
            res["offen, wird ergaenzt"] += 1; patch.append((f, d, t))
    evt = with_threads(events.load_events(files), th)
    res["Ereignisse gesamt"] = len(evt); res["davon mit Thread"] = sum(1 for e in evt if (e["_mail"] or {}).get("thread"))
    intake = Path(intake)
    al = json.load(open(intake / "vendor_aliases.json")) if (intake / "vendor_aliases.json").exists() else {}
    poal = json.load(open(intake / "po_aliases.json")) if (intake / "po_aliases.json").exists() else {}
    kw = dict(vendor_only=True, products=ctx["products"], style_aliases=ctx.get("style_aliases"), event_overrides=events.load_event_overrides(intake))
    pl_all = events.plan(evt, ctx["orders"], ctx["vendors"], poal, al, thread_orders={}, **kw)
    state = mail_threads.load(intake / "mail_threads.json")
    n_new = mail_threads.learn(state, pl_all["assigned"])
    res["Verlaeufe im Zustand"] = len(state); res["neue Verlauf-Order-Paare"] = n_new
    res["Verlaeufe mit >= 2 Orders (mehrdeutig)"] = sum(1 for v in state.values() if len(v) > 1)
    # Wirkung auf die Klaerfaelle: nur offene (nicht erledigte) Dateien, mit und ohne Verlauf-Zuordnung
    pend = [f for f in files if not ledger.is_done(led, f)]
    evp = with_threads(events.load_events(pend), th)
    old = os.environ.get("THREAD_MATCH")
    os.environ["THREAD_MATCH"] = "0"
    try:
        p0 = events.plan(evp, ctx["orders"], ctx["vendors"], poal, al, thread_orders=state, **kw)
    finally:
        if old is None:
            os.environ.pop("THREAD_MATCH", None)
        else:
            os.environ["THREAD_MATCH"] = old
    p1 = events.plan(evp, ctx["orders"], ctx["vendors"], poal, al, thread_orders=state, **kw)
    dom = events.domain_vendors(ctx["vendors"])
    dirs = {} if dirs is None else dirs   # Fundort-Text der Tabelle wird fuer die Zaehlung nicht gebraucht (mail_dirs liest alle Archive erneut, langsam)
    r0 = klaerfaelle.select(p0["unmatched"], ctx["vendors"], al, dom, dirs, ctx.get("orders"))
    r1 = klaerfaelle.select(p1["unmatched"], ctx["vendors"], al, dom, dirs, ctx.get("orders"))
    res["Klaerfaelle ohne Verlauf"] = len(r0); res["Klaerfaelle mit Verlauf"] = len(r1)
    res["Ereignisse ueber Verlauf zugeordnet"] = sum(1 for o in p1["orders"] for l in o["lines"] if "ueber Mail-Verlauf zugeordnet" in l["text"])
    if apply:
        for f, d, t in patch:
            d["thread_id"] = t
            tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1)); tmp.replace(f)
        mail_threads.save(intake / "mail_threads.json", state)
        res["Dateien geschrieben"] = len(patch)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--inbox", default=os.path.expanduser("~/Library/CloudStorage/kontakt@firma.example/Meine Ablage/Inbox"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    from plm_intake.context import add_po_numbers, load_context
    ctx = load_context(); add_po_numbers(ctx)
    th = thread_map()
    print("Mails mit Thread-ID (Archive): %d" % len(th))
    res = run(a.inbox, ROOT / "output" / "intake", ctx, th, apply=a.apply)
    for k, v in res.items():
        print("  %-42s %s" % (k, v))
    print("(%s)" % ("geschrieben" if a.apply else "Trockenlauf, nichts geschrieben; --apply schreibt Dateien + mail_threads.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
