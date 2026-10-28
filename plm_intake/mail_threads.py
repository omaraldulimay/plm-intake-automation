"""Gmail-Verlauf (Thread) -> Bestellung, gelernt aus zugeordneten Ereignissen (Zustand output/intake/mail_threads.json).

Format: {"<Thread-ID>": ["<Order-ID>", ...]}
Gelernt wird aus eigenen Zuordnungen der Ereignisse (PO-Nr, Alias, Klaerung, aber auch einzige laufende Order/Menge/Text; nie aus Verlauf geerbte, nie Info). Die Thread-ID steht seit dem Apps-Script-Update
als 'thread_id' in jeder *_events.json (events.load_events -> e['_mail']['thread']); aeltere Dateien bekommen sie ueber plm_intake/mail_threads_backfill.py.
Benutzt wird ein Verlauf nur, wenn er GENAU EINE Order ergibt (events.plan, Grund 'verlauf'); mehrere Orders = mehrdeutig = bleibt Klaerfall.
Schalter THREAD_MATCH: Standard an, '0' schaltet die Nutzung aus (Lernen laeuft immer weiter)."""
import json
import os

IGNORE = ('thread', 'verlauf')   # aus dem Verlauf geerbte Zuordnungen lernen wir nie weiter
MAX_ORDERS = 5   # mehr als ein paar Orders pro Verlauf braucht es nicht (>= 2 heisst ohnehin mehrdeutig)


def enabled():
    return os.environ.get("THREAD_MATCH", "1").strip() != "0"


def load(path):
    try:
        d = json.load(open(path))
    except (OSError, ValueError):
        return {}
    return {str(k): [str(x) for x in v] for k, v in d.items() if isinstance(v, list)} if isinstance(d, dict) else {}


def learn(state, assigned):
    """state (dict) wird veraendert; assigned = [(event, order_id, why)]. -> Anzahl neuer (Verlauf, Order)-Paare."""
    n = 0
    for e, oid, why in assigned:
        t = (e.get("_mail") or {}).get("thread")
        if not t or not oid or why in IGNORE:
            continue
        cur = state.setdefault(str(t), [])
        if oid not in cur and len(cur) < MAX_ORDERS:
            cur.append(oid); n += 1
    return n


def save(path, state):
    from pathlib import Path
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True)); tmp.replace(p)
