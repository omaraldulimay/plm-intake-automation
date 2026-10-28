"""Zahlungsplaene der Bestellungen im Lifecycle-PLM (Tab "Payments").

Regeln (von Omar freigegeben, 26.10.):
 1. Platzhalter-Zeile 'Gesamtbetrag (Platzhalter ...)' (genau 1 Zeile) wird ENTFERNT, solange die Zahlungsbedingungen unbekannt sind (leere payments-Liste ist erlaubt).
 2. Sind die Bedingungen der Order selbst bekannt (Notiz 'Zahlungsbedingungen: ...' aus PO/PI dieser Order, oder durchgehend gleiche Open-Account-Angabe 'Mal Mukabili'
    in den Beleg-Zeilen der Order) und eindeutig (Prozente ergeben 100, kein Widerspruch zur Lieferanten-Bedingung), wird die Platzhalter-Zeile durch den Plan ersetzt:
    je Rate eine Zeile name '<n>% <Bedingung>', amount = n % vom Gesamtwert (letzte Rate = Rest, Summe = totalCost), terms = Originaltext, Status Unpaid,
    Faelligkeit aus PO-Datum (Deposit/vor Produktion), ETD bzw. ex-factory (+ N Tage), sonst KEINE Faelligkeit (nichts erfunden: Feld dueDate fehlt).
 3. Widerspruechliche oder nur als Lieferanten-Rahmen bekannte Bedingungen: keine Automatik, Klaerfall-Zeile in der PLM-Tabelle 'Klärfälle Einpflege' (Art Zahlung);
    die Platzhalter-Zeile wird trotzdem entfernt (falsche 'Payments Due').
 4. Status Paid nur bei 'Paid' im Beleg (Zeile 'Zahlungen: ... <Betrag> Paid') ODER ausdruecklicher Zahlungsmeldung mit genau EINEM Betrag, jeweils nur bei genau EINEM
    Betragstreffer (+-0,01) unter den offenen (Unpaid) Zahlungen. 'Zahlung erfolgt' ohne Betrag bleibt Notiz.
 Echte Plaene (Betraege > 0) werden sonst NIE veraendert. Test-Orders (ZZ-/T1-/TEST) und Orders ohne Platzhalter/Paid-Treffer werden nicht angefasst.

Schreiben: UpdateOrder mit dem GANZEN payments-Array (ersetzt!) ueber window.__updOrder (payments_plan_template.js), je Order Vorzustand VOLLSTAENDIG (inkl. ids) in
output/backup/payments_vor_<Zeit>.json, danach Zuruecklesen (nur payments geaendert, Summe == totalCost, Positionen/Mengen/Preise/Notizen unveraendert), Abbruch bei Abweichung.
Dry-Run ist Standard:  .venv/bin/python -m plm_intake.payments_plan [--apply] [--max 10]"""
import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSER = Path(__file__).resolve().parent / "browser"
BACKUP_DIR = ROOT / "output" / "backup"
MAX_ORDERS = 10
TOL = 0.01
VENDOR_TERMS_SUFFIX = "_payment_terms"
OPEN_ACCOUNT = re.compile(r"mal\s*mukab[iİı]l[iİı]?|open\s*account", re.I)
OPEN_ACCOUNT_NAME = {"mal mukabili": "Mal Mukabili (Zahlung gegen Ware)", "open account": "Open Account"}


def is_test(title):
    return bool(re.search(r"(?i)(^|[^a-z0-9])zz|(^|[^a-z0-9])T1([^a-z0-9]|$)|TEST", str(title or "")))


def is_placeholder(order):
    p = order.get("payments") or []
    return len(p) == 1 and "platzhalter" in str(p[0].get("name") or "").casefold()


def ms_of(d):
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


def to_date(v):
    """ms-Zeitstempel (Zahl/Text) oder ISO-String -> date | None."""
    if v in (None, "", 0, "0"):
        return None
    try:
        s = str(v).strip()
        if re.fullmatch(r"\d{10,14}", s):
            return dt.datetime.fromtimestamp(int(s) / 1000, dt.timezone.utc).date()
        return dt.date.fromisoformat(s[:10])
    except (ValueError, OverflowError, OSError):
        return None


def r2(x):
    return round(float(x) + 1e-9, 2)


# ---------------- Bedingungen lesen ----------------
def _num(s):
    return float(str(s).replace(",", "."))


def split_terms(text):
    """Notiz-/Feldtext -> Liste einzelner Bedingungen. Teilt auch '30% deposit ..., balance against B/L' (Rest ohne Prozent)."""
    out = []
    for part in re.split(r";|\n", text):
        for seg in re.split(r",\s*(?=balance\b)", part, flags=re.I):
            seg = seg.strip(" .'\"")
            if seg:
                out.append(seg)
    return out


def doc_terms(notes):
    """'Zahlungsbedingungen: [...]' bzw. '... a; b; c (keine Betraege/Termine ...)' aus der Order-Notiz (eigene PO/PI) -> Liste | None."""
    m = re.search(r"Zahlungsbedingungen:\s*(\[[^\]]*\]|[^.\n]*?(?=\s*\(keine|\.\s|\.$|\n|$))", notes or "")
    if not m:
        return None
    body = m.group(1).strip()
    if body.startswith("["):
        items = re.findall(r"'([^']*)'|\"([^\"]*)\"", body)
        parts = [a or b for a, b in items]
        out = []
        for p in parts:
            out += split_terms(p)
        return out or None
    return split_terms(body) or None


def parse_installment(raw):
    """Eine Bedingung -> {pct|None, anchor, days, raw} | None (nicht lesbar). anchor: po | ship | None (Zeitpunkt unbekannt, z. B. nach Inspektion)."""
    t = str(raw or "").strip()
    if not t or re.fullmatch(r"(?i)\s*(tba|tbc|tbd|n/?a|-)\s*", t):
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", t)
    pct = _num(m.group(1)) if m else None
    low = t.casefold()
    days = None
    md = re.search(r"(\d+)\s*(?:days?|tage?n?)", low)
    if md and re.search(r"after|nach", low):
        days = int(md.group(1))
    elif re.search(r"within\s+(?:one|1)\s+month", low):
        days = 30
    if days is not None or re.search(r"shipment|shipping|b/?l\b|versand|vor\s*ort|against|gegen|upon|loading", low):
        anchor = "ship"
        days = days or 0
    elif re.search(r"deposit|depost|advance|anzahlung|before production|vor produktion|pi confirmed|bei bestellung|vorkasse|prepay", low):
        anchor = "po"
    else:
        anchor = None
    if pct is None and not re.search(r"balance|rest", low):
        return None
    return {"pct": pct, "anchor": anchor, "days": days or 0, "raw": t}


def parse_plan(items):
    """Liste von Bedingungen -> (raten[{pct,anchor,days,raw}], fehler|None). Rate ohne Prozent ('balance ...') = Rest; Summe muss 100 ergeben."""
    raten = []
    for raw in items:
        p = parse_installment(raw)
        if p is None:
            return None, "Bedingung nicht lesbar/offen: '%s'" % str(raw)[:80]
        raten.append(p)
    if not raten:
        return None, "keine Bedingung"
    known = sum(r["pct"] for r in raten if r["pct"] is not None)
    blanks = [r for r in raten if r["pct"] is None]
    if len(blanks) > 1 or (blanks and raten[-1] is not blanks[0]):
        return None, "mehr als eine Restrate oder Restrate nicht am Ende"
    if blanks:
        if known >= 100 - TOL:
            return None, "Prozente %.2f lassen keinen Rest" % known
        blanks[0]["pct"] = round(100 - known, 4)
    elif abs(known - 100) > TOL:
        return None, "Prozente ergeben %.2f statt 100" % known
    return raten, None


def pct_list(text):
    """Prozente einer Freitext-Bedingung (Lieferantenfeld), Rest als letzte Rate."""
    p = [_num(x) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", str(text or ""))]
    if p and sum(p) < 100 - TOL and re.search(r"balance|rest", str(text), re.I):
        p.append(round(100 - sum(p), 4))
    return p


def po_date(notes):
    m = re.search(r"PO-Datum (\d{4}-\d{2}-\d{2})", notes or "")
    try:
        return dt.date.fromisoformat(m.group(1)) if m else None
    except ValueError:
        return None


def open_account_term(notes):
    """Durchgehend gleiche Open-Account-Angabe in den Beleg-/Zahlungs-Zeilen der Order ('Zahlungen: MAL MUKABILI 69671.6 Unpaid') -> Name | None.
    Mehrere verschiedene Angaben oder zusaetzlich echte Raten-Angaben (Prozent) = None (Widerspruch/Unklar)."""
    found = set()
    for line in (notes or "").split("\n"):
        if not re.match(r"\[[^\]]*\]\s*(BELEG|PAYMENT)", line):
            continue
        m = re.search(r"Zahlungen:\s*(.*?)\s+\d+(?:\.\d+)?\s+(?:Paid|Unpaid)\b", line)
        if not m:
            continue
        if re.search(r"\d\s*%", m.group(1)):
            return None
        if OPEN_ACCOUNT.search(m.group(1)):
            found.add("mal mukabili" if re.search(r"mukab", m.group(1), re.I) else "open account")
    return OPEN_ACCOUNT_NAME[next(iter(found))] if len(found) == 1 else None


# ---------------- Plan aufbauen ----------------
def due_for(rate, order, pod):
    """Faelligkeit als date | None (nichts erfinden)."""
    if rate["anchor"] == "po":
        return pod
    if rate["anchor"] == "ship":
        base = to_date(order.get("etdEstimatedDate")) or to_date(order.get("exFactoryExpectedDate"))
        return base + dt.timedelta(days=rate["days"]) if base else None
    return None


def build_rows(raten, order):
    total = r2(order.get("totalCost") or 0)
    pod = po_date(order.get("notes"))
    rows, rest = [], total
    for i, r in enumerate(raten):
        amt = rest if i == len(raten) - 1 else r2(total * r["pct"] / 100.0)
        rest = r2(rest - amt)
        raw = re.sub(r"^(?:T/?T\s+)", "", r["raw"]).strip()
        name = raw if re.match(r"\d", raw) else "%s%% %s" % ("%g" % r["pct"], raw)
        d = due_for(r, order, pod)
        rows.append({"name": name[:120], "status": "Unpaid", "amount": amt, "terms": r["raw"], "dueDate": ms_of(d) if d else None})
    return rows


def vendor_terms_text(order, vendor_terms):
    m = order.get("manufacturer") or {}
    return (vendor_terms or {}).get(m.get("id") if isinstance(m, dict) else m)


CONFLICT_RE = re.compile(r"Bedingungen weichen ab|Zahlungsbedingungen[^.\n]{0,80}(weichen|abweich|widerspr|nicht mit dem Lieferanten abgeglichen)", re.I)


def klaer_row(order, vendor_name, code, was, warum, aktion, today, key=None):
    mk = hashlib.sha1(("pay|%s|%s" % (code, key or order.get("id"))).encode()).hexdigest()[:8]
    return {"marker": mk, "category": vendor_name or "Ohne Lieferant",
            "values": __import__("plm_intake.klaerfaelle", fromlist=["kompakt"]).kompakt({"Datum": today, "Art": "Zahlung", "Was": was[:300], "Warum offen": "Datenpflege: " + warum[:190], "Nummer": (order.get("title") or "")[:200],
                       "Mögliche PO": "", "Aktion": aktion[:300], "Zitat": "", "Absender": "", "Betreff": "", "Mail-ID": "", "Suche": "",
                       "Quelle": "Zahlungsplan %s | %s | ev:%s" % (today, code, mk), "Status": "offen"})}


# ---------------- Paid-Regel ----------------
PAID_TOKEN = re.compile(r"(?:(?<=Zahlungen: )|(?<=, ))[^,]*?\s(\d+(?:\.\d+)?)\s+(Paid|Unpaid)\b")
MONEY = re.compile(r"(?:USD|EUR|\$|€)\s*([\d.,]+\d)|([\d.,]*\d)\s*(?:USD|EUR)\b")
PAYMENT_DONE = re.compile(r"\b(made|paid|bezahlt|überwiesen|ueberwiesen|receipt of remittance|erhalten|received)\b", re.I)
PAYMENT_NOT = re.compile(r"\b(will|plans?|requests?|requested|asks?|reminded?|reminds?|follow|bitte|bittet|fordert|mahnt|erinnert|please|waiting|wait|expected|arranged|unpaid|offen|schickt|sent for)\b", re.I)


def _money_val(s):
    s = s.strip(".,")
    if re.search(r",\d{2}$", s) and "." in s:    # 1.234,56
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def paid_evidence(notes):
    """-> [(betrag, quelle)] aus Notizzeilen: 'Paid'-Token der Beleg-Zahlungen und eindeutige Zahlungsmeldungen (genau EIN Betrag, Erfolgsverb, kein Wunsch/Mahnung)."""
    out = []
    for line in (notes or "").split("\n"):
        if not re.match(r"\[[^\]]*\]\s*(BELEG|PAYMENT)", line):
            continue
        for m in PAID_TOKEN.finditer(line):
            if m.group(2) == "Paid":
                out.append((float(m.group(1)), "Beleg 'Paid'"))
        if re.match(r"\[[^\]]*\]\s*PAYMENT:", line) and "Zahlungen:" not in line:
            if PAYMENT_DONE.search(line) and not PAYMENT_NOT.search(line.split("(Mail")[0]):
                vals = {_money_val(a or b) for a, b in MONEY.findall(line.split("(Mail")[0])}
                vals.discard(None)
                if len(vals) == 1:
                    out.append((vals.pop(), "Zahlungsmeldung"))
    return out


def paid_updates(payments, notes):
    """-> [(index, quelle)] fuer Unpaid-Zahlungen mit genau EINEM Betragstreffer. Betrag mit mehreren Treffern oder mehreren Zahlungen derselben Hoehe = nichts."""
    res, taken = [], set()
    for amt, why in paid_evidence(notes):
        c = [i for i, p in enumerate(payments) if p.get("status") != "Paid" and p.get("amount") is not None and abs(p["amount"] - amt) <= TOL]
        sameval = [i for i, p in enumerate(payments) if p.get("amount") is not None and abs(p["amount"] - amt) <= TOL]
        if len(c) == 1 and len(sameval) == 1 and c[0] not in taken:
            taken.add(c[0]); res.append((c[0], why, amt))
    return res


# ---------------- Gesamtplan ----------------
def plan(orders, vendor_terms=None, today=None, max_orders=MAX_ORDERS):
    """orders: Liste Order-dicts (id,title,notes,currency,totalCost,payments[{id,name,status,amount,dueDate,terms}],manufacturer{id,name},etdEstimatedDate,exFactoryExpectedDate,status).
    -> {"actions":[...], "klaer":[Klaerfall-Zeilen], "limit_offen": n, "warnings":[...]}   (actions: kind placeholder|plan|paid, begrenzt auf max_orders)"""
    today = today or dt.date.today().isoformat()
    actions, klaer, warnings = [], [], []
    vend_ph = {}   # Lieferant -> Titel der Orders, die nur als Rahmen/unbekannt gelten (eine Klaerfall-Zeile je Lieferant)
    for o in sorted(orders, key=lambda x: x.get("title") or ""):
        if is_test(o.get("title")):
            continue
        pays = o.get("payments") or []
        vname = (o.get("manufacturer") or {}).get("name") if isinstance(o.get("manufacturer"), dict) else None
        notes = o.get("notes") or ""
        vt = vendor_terms_text(o, vendor_terms)
        total = r2(o.get("totalCost") or 0)
        act = None
        if is_placeholder(o):
            raten, err, src = None, None, None
            dt_ = doc_terms(notes)
            if dt_:
                raten, err = parse_plan(dt_); src = "PO/PI-Notiz"
            oa = open_account_term(notes) if (not dt_ or err) else None
            if oa:   # PO/PI-Notiz leer oder offen (TBA/TBC): durchgehende Open-Account-Angabe der Belege
                raten, err, src = [{"pct": 100.0, "anchor": "ship", "days": 0, "raw": oa}], None, "Beleg-Zeilen (Open Account)"
            if raten and not err and total > 0:
                vp = pct_list(vt) if vt else []
                mine = [r["pct"] for r in raten]
                if src.startswith("PO/PI") and vp and [round(x, 2) for x in vp] != [round(x, 2) for x in mine]:
                    klaer.append(klaer_row(o, vname, "konflikt", "Zahlungsbedingungen widerspruechlich: Order-PO/PI %s, Lieferant %s" % ("/".join("%g" % x for x in mine), "/".join("%g" % x for x in vp)),
                                           "Order-PO/PI: %s | Lieferantenfeld: %s" % ("; ".join(r["raw"] for r in raten)[:150], str(vt)[:120]),
                                           "Welche Bedingung gilt fuer diese Order? Danach Plan eintragen (Platzhalter-Zeile ist entfernt).", today))
                    act = {"kind": "placeholder", "why": "Bedingungen widerspruechlich (Order %s vs Lieferant %s): Klaerfall" % ("/".join("%g" % x for x in mine), "/".join("%g" % x for x in vp))}
                else:
                    rows = build_rows(raten, o)
                    act = {"kind": "plan", "rows": rows, "why": "Plan aus %s: %s" % (src, "; ".join(r["raw"] for r in raten)[:160])}
            else:
                if err:
                    why = "Bedingungen offen/unlesbar (%s)" % err
                    klaer.append(klaer_row(o, vname, "offen", "Zahlungsbedingungen nicht eindeutig: %s" % err, "Notiz-Text: %s" % "; ".join(dt_ or [])[:200],
                                           "Zahlungsbedingungen dieser Order nennen (Platzhalter-Zeile ist entfernt).", today))
                elif vt:
                    why = "nur Lieferanten-Rahmen bekannt (%s): Klaerfall je Lieferant" % str(vt)[:90]
                    vend_ph.setdefault((vname, "rahmen", str(vt)), []).append(o)
                else:
                    why = "Zahlungsbedingungen unbekannt: Klaerfall je Lieferant"
                    vend_ph.setdefault((vname, "unbekannt", ""), []).append(o)
                act = {"kind": "placeholder", "why": why}
            if act:
                act["payments_after"] = act.get("rows") or []
        elif pays and any((p.get("amount") or 0) > 0 for p in pays):
            # echter Plan: nur Paid-Regel; Widerspruchs-Hinweise als Klaerfall (keine Aenderung)
            s = r2(sum(p.get("amount") or 0 for p in pays))
            reasons = []
            if abs(s - total) > TOL:
                reasons.append("Summe der Raten %.2f != Gesamtwert %.2f (%+.2f)" % (s, total, s - total))
            if CONFLICT_RE.search(notes):
                reasons.append("Notiz der Order nennt widerspruechliche/nicht abgeglichene Bedingungen")
            if len(pays) >= 3 and all(p.get("dueDate") not in (None, "") for p in pays) and len({str(p.get("dueDate")) for p in pays}) == 1 and not vt:
                reasons.append("alle %d Raten mit gleicher Faelligkeit (Vorlage, nicht abgeglichen)" % len(pays))
            if reasons:
                klaer.append(klaer_row(o, vname, "plan", "Zahlungsplan pruefen: " + "; ".join(reasons), "Plan unveraendert (echte Zahlungen). Lieferantenfeld: %s" % (str(vt)[:100] if vt else "keine"),
                                       "Plan/Bedingungen und Betraege pruefen, richtigen Plan nennen.", today))
        # Paid-Regel (auch fuer gerade geplante Zeilen)
        base = (act or {}).get("rows") if act and act["kind"] == "plan" else [p for p in pays if not is_placeholder(o)]
        pu = paid_updates(base or [], notes)
        if pu:
            if act and act["kind"] == "plan":
                for i, why, amt in pu:
                    act["rows"][i]["status"] = "Paid"
                act["paid"] = [(i, why, a) for i, why, a in pu]
            else:
                act = {"kind": "paid", "paid": pu, "why": "Paid gesetzt: " + "; ".join("%s (%s, %.2f)" % (pays[i].get("name"), why, a) for i, why, a in pu)}
        if act:
            act.update({"id": o["id"], "title": o.get("title"), "total": total, "before": pays, "currency": o.get("currency"), "vendor": vname})
            actions.append(act)
    for (vname, kind, vt), os_ in sorted(vend_ph.items(), key=lambda kv: str(kv[0][0])):
        titles = [x.get("title") for x in os_]
        if kind == "rahmen":
            was = "Zahlungsbedingungen unbekannt je Order: nur Lieferanten-Rahmen '%s' (%d Orders)" % (vt[:120], len(os_))
            akt = "Gilt der Rahmen fuer diese Orders? Wenn ja bestaetigen, dann Plaene eintragen."
        else:
            was = "Zahlungsbedingungen unbekannt (%d Orders), keine Quelle in Notiz/Lieferant" % len(os_)
            akt = "Zahlungsbedingungen des Lieferanten nennen (PI/Vertrag)."
        klaer.append(klaer_row(os_[0], vname, kind, was, "Orders: " + ", ".join(titles)[:170], akt, today, key="%s|%s|%s" % (vname, kind, vt)))
    limit_offen = max(0, len(actions) - max_orders)
    return {"actions": actions[:max_orders], "klaer": klaer, "limit_offen": limit_offen, "alle": len(actions)}


# ---------------- Browser ----------------
def run_js(js):
    """Browser-Lauf; wartet, wenn ein anderer Lauf das Chrome-Profil haelt (SingletonLock)."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    last = ""
    for _ in range(12):
        r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=1800)
        if r.returncode == 0:
            return json.loads(r.stdout)
        last = (r.stderr or r.stdout)[-300:]
        if "SingletonLock" not in last and "ProcessSingleton" not in last:
            break
        time.sleep(20)
    raise RuntimeError("Browser-Lauf gescheitert: " + last)


JS_READ = r'''(async()=>{
const c=window.__APOLLO_CLIENT__;const N=v=>({kind:'Name',value:v});
const F=(n,sub)=>({kind:'Field',name:N(n),...(sub?{selectionSet:{kind:'SelectionSet',selections:sub}}:{})});
const NNs=n=>({kind:'VariableDefinition',variable:{kind:'Variable',name:N(n)},type:{kind:'NonNullType',type:{kind:'NamedType',name:N('String')}}});
const A=(n,v)=>({kind:'Argument',name:N(n),value:{kind:'Variable',name:N(v)}});
const od={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'query',variableDefinitions:[NNs('id')],selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N('getOrderById'),arguments:[A('id','id')],selectionSet:{kind:'SelectionSet',selections:[F('id'),F('title'),F('notes'),F('currency'),F('totalCost'),F('totalNumberOfPieces'),F('exFactoryExpectedDate'),F('etdEstimatedDate'),F('manufacturer',[F('id'),F('name')]),F('status',[F('status')]),F('payments',[F('id'),F('name'),F('status'),F('amount'),F('dueDate'),F('terms')])]}}]}}]};
const vd={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'query',variableDefinitions:[NNs('m')],selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N('manufacturerById'),arguments:[A('manufacturerId','m')],selectionSet:{kind:'SelectionSet',selections:[F('id'),F('customFields')]}}]}}]};
const clean=a=>JSON.parse(JSON.stringify(a,(k,v)=>(k==='__typename'?undefined:v)));
const out={orders:[],vendors:{},err:[]};
for(const id of __IDS__){const r=await c.query({query:od,variables:{id},fetchPolicy:'no-cache',errorPolicy:'all'});
  if(r.data&&r.data.getOrderById) out.orders.push(clean(r.data.getOrderById)); else out.err.push(id+': '+(r.errors||[]).map(e=>e.message).join('; ').slice(0,120));}
const vids=[...new Set(out.orders.map(o=>o.manufacturer&&o.manufacturer.id).filter(Boolean))];
for(const m of vids){try{const r=await c.query({query:vd,variables:{m},fetchPolicy:'no-cache',errorPolicy:'all'});const cf=(r.data&&r.data.manufacturerById&&r.data.manufacturerById.customFields)||{};
  const k=Object.keys(cf).find(x=>x.endsWith('__SUFFIX__'));out.vendors[m]=k?cf[k]:null;}catch(e){out.err.push('Lieferant '+m+': '+String(e.message).slice(0,100));}}
return out;})()'''


def read_all(order_ids, runner=run_js):
    res = runner(JS_READ.replace("__IDS__", json.dumps(list(order_ids))).replace("__SUFFIX__", VENDOR_TERMS_SUFFIX))
    if res.get("err"):
        raise RuntimeError("Lesen unvollstaendig: %s" % res["err"][:3])
    return res["orders"], {k: v for k, v in (res.get("vendors") or {}).items() if v}


def write(actions, dry=False, runner=run_js):
    tpl = (Path(__file__).parent / "payments_plan_template.js").read_text()
    items = []
    for a in actions:
        before = a["before"]
        if a["kind"] == "paid":
            new = [{"name": p.get("name"), "status": p.get("status"), "amount": p.get("amount"), "terms": p.get("terms") or "",
                    **({"dueDate": int(p["dueDate"])} if p.get("dueDate") not in (None, "", 0) else {})} for p in before]
            for i, _, _ in a["paid"]:
                new[i]["status"] = "Paid"
        else:
            new = [{k: v for k, v in r.items() if not (k == "dueDate" and v is None)} for r in a["rows"]] if a["kind"] == "plan" else []
        items.append({"id": a["id"], "title": a["title"], "kind": a["kind"], "total": a["total"],
                      "before": [{"name": p.get("name"), "status": p.get("status"), "amount": p.get("amount"), "dueDate": str(p.get("dueDate")) if p.get("dueDate") is not None else None} for p in before],
                      "payments": new})
    js = tpl.replace("__PLAN__", json.dumps(items, ensure_ascii=False, separators=(",", ":"))).replace("__DRY__", "true" if dry else "false")
    return runner(js)


def verify(actions, res):
    """-> (ok_orders, fehler[]). Jede Order muss im Ergebnis ohne Fehler/ABBRUCH und mit allen Pruefungen stehen."""
    by = {r.get("title"): r for r in res or []}
    ok, errs = 0, []
    for a in actions:
        r = by.get(a["title"])
        if r is None:
            errs.append("%s: nicht ausgefuehrt (Lauf gestoppt)" % a["title"])
        elif r.get("error") or r.get("fatal") or r.get("ABBRUCH") or r.get("skipped_changed"):
            errs.append("%s: %s" % (a["title"], r.get("error") or r.get("fatal") or r.get("ABBRUCH") or r.get("skipped_changed")))
        elif r.get("dataUnchanged") is False or r.get("paymentsOk") is False or r.get("sumOk") is False:
            errs.append("%s: Zuruecklesen unstimmig %s" % (a["title"], {k: r.get(k) for k in ("dataUnchanged", "paymentsOk", "sumOk")}))
        else:
            ok += 1
    return ok, errs


def backup(actions, orders_by_id, now=None):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    p = BACKUP_DIR / ("payments_vor_%s.json" % (now or dt.datetime.now()).strftime("%Y-%m-%d_%H%M%S"))
    p.write_text(json.dumps([{"id": a["id"], "title": a["title"], "kind": a["kind"], "payments_vorher": orders_by_id[a["id"]].get("payments"),
                              "totalCost": orders_by_id[a["id"]].get("totalCost"), "geplant": a.get("rows") or a.get("paid") or []} for a in actions], ensure_ascii=False, indent=1))
    return p


def counts(actions, res_by_title=None):
    """Zaehler fuer den Tagesbericht aus erfolgreich geschriebenen Aktionen."""
    ok = lambda a: res_by_title is None or a["title"] in res_by_title
    return {"platzhalter": sum(1 for a in actions if a["kind"] == "placeholder" and ok(a)),
            "plaene": sum(1 for a in actions if a["kind"] == "plan" and ok(a)),
            "paid": sum(len(a.get("paid") or []) for a in actions if ok(a))}


def klaer_sync(rows, runner=run_js):
    """Klaerfall-Zeilen in die PLM-Tabelle 'Klärfälle Einpflege' (nur neue, Marker ev:<hash>; nichts loeschen/aendern). -> (neu, fehler[])"""
    from plm_intake import klaerfaelle
    if not rows or not klaerfaelle.CFG.exists():
        return 0, []
    cfg = json.loads(klaerfaelle.CFG.read_text())
    js = klaerfaelle.SYNC_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "brandId": cfg["brandId"], "rows": rows, "resolved": [], "fill": []}, ensure_ascii=False))
    r = runner(js) or {}
    return r.get("created") or 0, r.get("errors") or []


def run(orders_light, apply=False, max_orders=MAX_ORDERS, runner=run_js, backup_fn=backup):
    """orders_light: Orders aus REST (nur ids/Titel noetig). -> (zeilen, ergebnis{platzhalter,plaene,klaerfaelle,paid,fehler,warnungen,plan})."""
    ids = [o["id"] for o in orders_light if not is_test(o.get("title"))]
    orders, vterms = read_all(ids, runner)
    pl = plan(orders, vterms, max_orders=max_orders)
    res = {"platzhalter": 0, "plaene": 0, "klaerfaelle": 0, "paid": 0, "fehler": 0, "warnungen": [], "plan": pl}
    L = ["- Orders geprueft: %d | Aktionen: %d (diesen Lauf %d, Rest %d) | Klaerfall-Kandidaten: %d" % (len(orders), pl["alle"], len(pl["actions"]), pl["limit_offen"], len(pl["klaer"]))]
    for a in pl["actions"]:
        L.append("  - %s [%s] %s" % (a["title"], {"placeholder": "Platzhalter entfernen", "plan": "Plan aufbauen", "paid": "Paid setzen"}[a["kind"]], a["why"]))
        for r in a.get("rows") or []:
            L.append("      %s | %.2f %s | %s | faellig %s" % (r["name"], r["amount"], r["status"], r["terms"][:50], dt.datetime.fromtimestamp(r["dueDate"] / 1000, dt.timezone.utc).date() if r.get("dueDate") else "unbekannt"))
    L += ["  - KLAERFALL [%s] %s: %s" % (k["category"], k["values"]["Warum offen"][:50], k["values"]["Was"][:110]) for k in pl["klaer"]]
    if not apply:
        return ["- (Trockenlauf) nichts geschrieben"] + L, res
    if not pl["actions"] and not pl["klaer"]:
        return L + ["- nichts zu tun"], res
    errs = []
    if pl["actions"]:
        by_id = {o["id"]: o for o in orders}
        L.append("- Backup: %s" % backup_fn(pl["actions"], by_id))
        out = write(pl["actions"], False, runner)
        ok, errs = verify(pl["actions"], out)
        done = {r["title"] for r in out if not (r.get("error") or r.get("fatal") or r.get("ABBRUCH") or r.get("skipped_changed"))}
        c = counts(pl["actions"], done)
        res.update(platzhalter=c["platzhalter"], plaene=c["plaene"], paid=c["paid"], fehler=len(errs))
        L.append("- Zahlungen: Platzhalter entfernt %d, Plaene aufgebaut %d, Paid gesetzt %d, Orders ok %d, Fehler %d" % (c["platzhalter"], c["plaene"], c["paid"], ok, len(errs)))
        L += ["- FEHLER %s" % e for e in errs[:8]]
    if not errs:   # Klaerfaelle nur eintragen, wenn die Schreibphase sauber war (Platzhalter ist dann weg, Frage bleibt offen)
        try:
            n, kerr = klaer_sync(pl["klaer"], runner)
            res["klaerfaelle"] = n
            if kerr:
                res["warnungen"] += ["Zahlungen-Klaerfaelle: %s" % e for e in kerr[:3]]
            L.append("- Klaerfaelle neu eingetragen: %d (Kandidaten %d, bekannte uebersprungen)" % (n, len(pl["klaer"])))
        except Exception as e:   # noqa: BLE001
            res["warnungen"].append("Zahlungen-Klaerfaelle fehlgeschlagen: %s" % str(e)[:120])
    res["warnungen"] += ["Zahlungen: %s" % e for e in errs[:5]]
    return L, res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max", type=int, default=MAX_ORDERS)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    import plm_client
    from plm_intake.context import fetch_all
    L, res = run(fetch_all(plm_client.call, "orders"), a.apply, a.max)
    print("\n".join(L))
    return 1 if res["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
