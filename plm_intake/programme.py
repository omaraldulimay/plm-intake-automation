"""Programme = Gruppen von Orders, die ein Ereignis gemeinsam betrifft (Zustand output/intake/programme.json, Start: plm_intake/programme_start.json).

Warum: Programme wie KUNDE_X (Alpha) sind im PLM nach Land in mehrere Orders geteilt (DE, CH, LAGER). Ein Status-/Termin-/Containerereignis zum Programm gehoert zu ALLEN Orders
der Gruppe; eine einzelne Order ist nie die Antwort. Die Notiz geht deshalb in jede Order der Gruppe (nur Notiz, nie Termin/Status/Zahlung/Sendung, events.WEAK['programm']).

Format:
  {"programme": {"<Name>": {"lieferanten": ["<Lieferantenname>", ...],   # Pflicht: der Lieferant des Ereignisses muss dazugehoeren
                            "woerter": ["kunde_x"],                          # Programmwoerter (ganze Woerter)
                            "kennungen": ["561874", "AK/626/26"],         # IANs, Rechnungs-/Auftragsnummern des Programms
                            "orders": ["<Order-Titel oder ID>", ...],     # die Gruppe (abgeschlossene Orders werden uebersprungen)
                            "container": {"<Container>": ["<Order>", ...]}},   # optional: Container, die nur einen Teil der Gruppe betreffen
   "andere_woerter": ["kunde_y", ...]}                                   # Woerter anderer Programme: stehen sie im selben Text, wird NICHT zugeordnet

Treffer: 1) Text des Ereignisses (Zusammenfassung, Zitat, Details, Referenzen); nennt er GENAU ein Programm = Treffer, mehrere = nichts.
         2) nur wenn der Text kein Programm nennt: Mail-Betreff, aber nur, wenn er genau ein Programm und kein anderes Programmwort nennt.
Schalter PROGRAMM_MATCH: Standard an, '0' schaltet die Nutzung aus."""
import json
import os
import re
from pathlib import Path

from plm_intake import core

START = Path(__file__).resolve().parent / "programme_start.json"
SEP = r"[-_ /.]?"


def enabled():
    return os.environ.get("PROGRAMM_MATCH", "1").strip() != "0"


def load(path=None):
    """Zustandsdatei, sonst Startinhalt. -> {"programme": {...}, "andere_woerter": [...]} (leer bei Fehler)."""
    for p in (path, START):
        if not p:
            continue
        try:
            d = json.load(open(p))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and isinstance(d.get("programme"), dict):
            return d
    return {"programme": {}, "andere_woerter": []}


def _word_re(w):
    parts = [re.escape(x) for x in re.split(r"[-_ /.]+", str(w).strip()) if x]
    return re.compile(r"(?<![A-Za-z0-9])" + SEP.join(parts) + r"(?![A-Za-z0-9])", re.I) if parts else None


def _ident_re(k):
    parts = [re.escape(x) for x in re.split(r"[-_ /.]+", str(k).strip()) if x]
    return re.compile(r"(?<![A-Za-z0-9])" + SEP.join(parts) + r"(?!\d)", re.I) if parts else None


def _flat(x):
    if isinstance(x, dict):
        return " ".join(_flat(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return " ".join(_flat(v) for v in x)
    return "" if x in (None, False) else str(x)


def event_text(e):
    """Text des Ereignisses selbst (ohne Mail-Betreff): Zusammenfassung, Zitat, Details, Referenzen, eigener Betreff."""
    return " ".join([_flat(e.get("summary")), _flat(e.get("source_quote")), _flat(e.get("details")), _flat(e.get("ref")), _flat(e.get("subject"))])


def _hits(prog, text):
    for w in prog.get("woerter") or []:
        r = _word_re(w)
        if r and r.search(text):
            return "Wort '%s'" % w
    for k in prog.get("kennungen") or []:
        r = _ident_re(k)
        if r and r.search(text):
            return "Kennung '%s'" % k
    return None


def _has_other(cfg, text):
    return any(_word_re(w) and _word_re(w).search(text) for w in cfg.get("andere_woerter") or [])


def _resolve(refs, orders):
    out = []
    for r in refs or []:
        n = core.norm(r)
        for o in orders:
            if o.get("id") == r or core.norm(o.get("title")) == n:
                if o not in out:
                    out.append(o)
    return out


def _vendor_ok(prog, vendor, vendors):
    if not vendor:
        return False
    for name in prog.get("lieferanten") or []:
        n = core.norm(name)
        if core.norm(vendor.get("name")) == n or vendor.get("id") == name:
            return True
        v, _ = core.match_vendor(name, vendors)
        if v and v["id"] == vendor["id"]:
            return True
    return False


def find(e, vendor, vendors, orders, cfg, subject_too=True, active_not=("Complete",)):
    """-> dict(name, orders[laufende Order-dicts], hit, quelle 'text'|'betreff') oder None.
    Der Lieferant des Ereignisses muss zum Programm gehoeren (kein Lieferant = kein Treffer)."""
    progs = cfg.get("programme") or {}
    if not progs or not vendor:
        return None
    text = event_text(e)
    found = [(n, p, h, "text") for n, p in progs.items() if _vendor_ok(p, vendor, vendors) for h in [_hits(p, text)] if h]
    if not found and subject_too:
        subj = str((e.get("_mail") or {}).get("subject") or "")
        found = [(n, p, h, "betreff") for n, p in progs.items() if _vendor_ok(p, vendor, vendors) for h in [_hits(p, subj)] if h]
        if found and _has_other(cfg, subj):   # Betreff mit mehreren Programmen ('KUNDE_X / Kunde Y / XTRAFIT ...'): nichts zuordnen
            return None
    if len(found) != 1 or _has_other(cfg, text):
        return None
    name, p, hit, quelle = found[0]
    refs = p.get("orders") or []
    cn = core.norm(_flat((e.get("ref") or {}).get("container")) + " " + _flat((e.get("details") or {}).get("container")))
    for ck, cref in (p.get("container") or {}).items():   # Container, der nur einen Teil der Gruppe betrifft
        if core.norm(ck) and core.norm(ck) in cn:
            refs = cref
            break
    from plm_intake.events import _status
    grp = [o for o in _resolve(refs, orders) if _status(o) not in active_not]
    return {"name": name, "orders": grp, "hit": hit, "quelle": quelle} if grp else None


def group_ids(cfg, orders):
    """{Order-ID: [Programmname, ...]} (Hilfe fuer Pruefungen/Berichte)."""
    out = {}
    for n, p in (cfg.get("programme") or {}).items():
        for o in _resolve(p.get("orders"), orders):
            out.setdefault(o["id"], []).append(n)
    return out
