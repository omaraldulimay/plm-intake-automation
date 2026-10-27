"""Absender-Domain -> Lieferant, gelernt aus sicher zugeordneten Ereignissen (Zustand output/intake/vendor_domains.json).

Format: {"<domain>": {"vendor": "<Vendor-ID>" | "__mehrdeutig__", "mails": ["<MailId>", ...]}}
Gelernt wird nur aus STARKEN Zuordnungen (why ok/alias/po_id/klaerung); Absender = Domain von e['_mail']['from'] (nicht Smilodox, kein Freemail).
Benutzt wird eine Domain erst ab MIN_MAILS verschiedenen Mails mit demselben Lieferanten und ohne Gegenbeispiel (events.domain_vendors; vendor_of nimmt sie nur bei genau EINEM Treffer).
"""
import json
import re

AMBIG = "__mehrdeutig__"
STRONG = ("ok", "alias", "po_id", "klaerung")
MIN_MAILS = 2
MAX_MAILS = 5


def sender_domain(e):
    from plm_intake.events import FREE_MAIL
    m = re.search(r"@([\w.-]+)", str((e.get("_mail") or {}).get("from") or ""))
    d = m.group(1).lower().rstrip(".") if m else ""
    return "" if (not d or "smilodox" in d or d in FREE_MAIL) else d


def load(path):
    try:
        d = json.load(open(path))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def usable(state):
    """-> {domain: {vendor_id}} der benutzbaren Eintraege (>= MIN_MAILS Mails, kein Konflikt)."""
    out = {}
    for d, v in (state or {}).items():
        if isinstance(v, dict) and v.get("vendor") not in (None, "", AMBIG) and len(v.get("mails") or []) >= MIN_MAILS:
            out[d] = {v["vendor"]}
    return out


def learn(state, assigned, orders):
    """state (dict) wird veraendert; assigned = [(event, order_id, why)]. -> [(domain, vendor_id, 'neu'|'aktiv'|'Konflikt')]."""
    by_o = {o["id"]: o for o in orders}
    changes = []
    for e, oid, why in assigned:
        if why not in STRONG:
            continue
        d = sender_domain(e)
        vid = ((by_o.get(oid) or {}).get("manufacturer") or {}).get("id")
        mid = (e.get("_mail") or {}).get("id")
        if not d or not vid or not mid:
            continue
        cur = state.get(d)
        if not cur:
            state[d] = {"vendor": vid, "mails": [mid]}
            changes.append((d, vid, "neu"))
        elif cur["vendor"] == AMBIG:
            continue
        elif cur["vendor"] != vid:
            cur["vendor"] = AMBIG
            changes.append((d, vid, "Konflikt"))
        elif mid not in cur["mails"] and len(cur["mails"]) < MAX_MAILS:
            cur["mails"].append(mid)
            if len(cur["mails"]) == MIN_MAILS:
                changes.append((d, vid, "aktiv"))
    return changes
