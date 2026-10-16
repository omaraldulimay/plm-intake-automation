"""Fehlende Lieferantendaten (Ansprechpartner-Name, E-Mail, Telefon, Adresse, Website) im PLM ergaenzen. Nur ERGAENZEN, nie ueberschreiben oder loeschen.

  python3 -m plm_intake.vendors_fill [--sheet <Protokoll.xlsx>]            TROCKENLAUF (Standard): Vorschlag je Lieferant mit Quelle, Bericht output/vendors_fill.md
  python3 -m plm_intake.vendors_fill --apply [--sheet ...]                 schreibt per PUT /vendors/{id} (voller Stand + expectedUpdatedAt) und liest zurueck
Quellen: (A) Plenty-Lieferanteneinstellungen (Kontakt, E-Mail, Telefon), (B) Briefkopf/Signatur aus den Belegen der Inbox (vendor_info), (C) Absender der Mails (Name zur E-Mail,
nur Domains, die der Lieferant im PLM schon hat, und nur bei mindestens 5 eingehenden Mails). Bankdaten werden nie uebernommen. Testobjekte (ZZ-...) und 'Default Vendor' bleiben aussen vor."""
import argparse
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import barcodes as bc, core, daily  # noqa: E402

FREE = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com", "qq.com", "163.com", "126.com", "gmx.de", "web.de", "icloud.com"}
GENERIC = {"tekstil", "textile", "textiles", "textil", "sports", "sport", "apparel", "garment", "garments", "industry", "industrial", "trading", "trade", "international", "import", "export",
           "fashion", "company", "limited", "group", "wear", "knitting", "seamless", "outdoor", "packaging", "plastic", "products", "housewares", "microfiber", "dis", "ticaret", "sanayi", "ve"}
BANK = re.compile(r"iban|swift|account\s*(no|number)|\bbic\b", re.I)


def clean_phone(p):
    p = re.sub(r"\s+", " ", str(p or "")).strip()
    return p if re.fullmatch(r"[+\d][\d\s()./-]{5,}", p) and len(re.sub(r"\D", "", p)) >= 6 else ""


def clean_name(n, email=""):
    n = re.sub(r"^[A-Za-z]{2,6}\s*\|\s*", "", str(n or "").replace('"', ""))   # 'SPEDITION_B | Granit' -> 'Granit'
    n = re.sub(r"[/|]+\s*$", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    if re.search(r"mahalle|sokak|street|\bstr\b|cadde|road|\broad\b|bldg|building", n, re.I):   # Adresse statt Name
        return ""
    if not n or "@" in n or n.lower() == str(email).split("@")[0].lower() or len(n) > 40 or re.search(r"\d{3,}|ltd|co\.|gmbh|sports|textile|tekstil|group|import|trading", n, re.I):
        return ""
    if "|" in n or re.search(r"\b(export|info|sales|office|team|gloves|support|admin|service)\b", n, re.I):   # Funktionspostfach statt Person
        return ""
    words = n.split()[:3]
    while words and re.fullmatch(r"[/|\\-]+", words[-1]):
        words.pop()
    return " ".join(words)


def sender_stats(sheet, since="2025-10-01"):
    """{email: (Anzeigename, Anzahl eingehender Mails)} aus dem Protokoll-Blatt (Spalte Von); nur nicht-interne Absender."""
    if not sheet or not Path(sheet).exists():
        return {}
    import openpyxl
    wb = openpyxl.load_workbook(sheet, read_only=True)
    cnt, names = collections.Counter(), collections.defaultdict(collections.Counter)
    for r in list(wb["Exportiert"].iter_rows(values_only=True))[1:]:
        m = re.search(r'^\s*"?([^"<]*?)"?\s*<([^>]+@[^>]+)>', str(r[2] or ""))
        em, nm = (m.group(2).lower(), m.group(1)) if m else (str(r[2] or "").strip().lower(), "")
        if "@" not in em or "smilodox" in em:
            continue
        cnt[em] += 1
        n = clean_name(nm, em)
        if n:
            names[em][n] += 1
    return {e: (names[e].most_common(1)[0][0] if names[e] else "", c) for e, c in cnt.items()}


def plenty_contacts():
    import subprocess
    sql = "select supplier_name, coalesce(plenty_company,''), coalesce(plenty_contact_name,''), coalesce(plenty_email,''), coalesce(plenty_phone,'') from logistics.reorder_supplier_settings"
    r = subprocess.run([bc.PSQL, bc.CONN, "-At", "-F", "\t", "-c", sql], capture_output=True, text=True, cwd=str(ROOT), timeout=120,
                       env=dict(__import__("os").environ, PGOPTIONS="-c default_transaction_read_only=on"))
    return [x.split("\t") for x in r.stdout.splitlines()] if r.returncode == 0 else []


def inbox_contacts(inbox, vendors, aliases):
    out = collections.defaultdict(list)
    for f in Path(inbox).glob("*.json"):
        if f.name.endswith("_events.json"):
            continue
        try:
            d = json.load(open(f))
        except ValueError:
            continue
        vi = d.get("vendor_info")
        if not isinstance(vi, dict) or vi.get("role") not in (None, "SUPPLIER"):
            continue
        v, _ = core.match_vendor(d.get("vendor") or "", vendors, aliases)
        if v:
            out[v["id"]].append(vi)
    return out


def propose(v, plenty, inbox_vi, senders):
    """-> dict(contacts=[Kontakt-Ergaenzungen], fill=[(Index, Feld, Wert, Quelle)], address=..., website=...); nur Ergaenzungen."""
    cs = v.get("contacts") or []
    have_email = {str(c.get("email") or "").lower(): c for c in cs if c.get("email")}
    add, fill = [], []
    cand = []   # (name, email, phone, quelle)
    for sup, comp, cname, em, ph in plenty:
        if core.norm(sup) and (core.norm(sup) == core.norm(v["name"]) or core.norm(v["name"]) in core.norm(sup) or core.norm(sup) in core.norm(v["name"]) or core.norm(comp) == core.norm(v["name"])):
            cand.append((clean_name(cname, em), em.strip().lower(), clean_phone(ph), "Plenty"))
    for vi in inbox_vi:
        for c in vi.get("contacts") or []:
            cand.append((clean_name(c.get("name"), c.get("email") or ""), str(c.get("email") or "").strip().lower(), clean_phone(c.get("phone")), "Beleg"))
    domains = {e.split("@")[1] for e in have_email}
    vtok = [t for t in core.vendor_tokens(v["name"]) if len(t) >= 5 and t not in GENERIC]   # nur unterscheidende Namensteile, keine Branchenwoerter
    for em, (nm, n) in senders.items():
        d = em.split("@")[1]
        label = d.split(".")[-2] if d.count(".") >= 1 else d
        by_name = any(t in label or (len(label) >= 5 and label in t) for t in vtok)   # Lieferant ohne Kontakt: Domain traegt den Firmennamen (z. B. Lieferant Extra -> lieferant-extra.example.tr)
        if d not in FREE and ((d in domains and n >= 5) or (not domains and by_name and n >= 3)):
            cand.append((nm, em, "", "Mails (%d)" % n))
    seen = set()
    for nm, em, ph, src in cand:
        if em and BANK.search(em):
            continue
        if em and em in have_email:
            c = have_email[em]; i = cs.index(c)
            if nm and not c.get("name") and (i, "name") not in seen:
                fill.append((i, "name", nm, src)); seen.add((i, "name"))
            if ph and not c.get("phone") and (i, "phone") not in seen:
                fill.append((i, "phone", ph, src)); seen.add((i, "phone"))
        elif em and (nm or ph or re.fullmatch(r"(export|info|sales|office|contact|service)", em.split("@")[0])) and em not in {a["email"] for a in add}:
            if not nm and re.fullmatch(r"(export|info|sales|office|contact|service)", em.split("@")[0]):
                nm = em.split("@")[0].title()   # Funktionspostfach: der Postfachname dient als Bezeichnung
            # gleicher Vorname wie ein vorhandener Kontakt ohne E-Mail: E-Mail dort ergaenzen statt neuen Kontakt anlegen
            same = [c for c in cs if not c.get("email") and nm and c.get("name") and core.norm(c["name"].split()[0]) == core.norm(nm.split()[0])]
            if len(same) == 1 and (cs.index(same[0]), "email") not in seen:
                i = cs.index(same[0]); fill.append((i, "email", em, src)); seen.add((i, "email"))
                if ph and not same[0].get("phone"):
                    fill.append((i, "phone", ph, src))
            else:
                add.append({"name": nm, "email": em, "phone": ph, "src": src})
        elif not em and ph and cs:   # nur Telefon (z. B. Plenty): an den Hauptkontakt, wenn dort leer
            i = next((k for k, c in enumerate(cs) if c.get("main")), 0)
            if not cs[i].get("phone") and (i, "phone") not in seen:
                fill.append((i, "phone", ph, src)); seen.add((i, "phone"))
    # bei jedem Lieferanten zaehlt: hoechstens 2 neue Kontakte pro Lauf (keine Flut aus Mail-Absendern)
    return {"fill": fill, "add": add[:2]}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--sheet"); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    import plm_client
    import requests
    import os
    from plm_intake.context import fetch_all
    vendors = [v for v in fetch_all(plm_client.call, "vendors") if not re.match(r"(?i)zz|default vendor|smilodox", v["name"])]
    aliases = json.load(open(daily.INTAKE / "vendor_aliases.json"))
    plenty = plenty_contacts(); senders = sender_stats(a.sheet); ibx = inbox_contacts(daily.resolve_inbox(None, daily.INTAKE), vendors, aliases)
    rep = ["# Lieferantendaten ergaenzen (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Stand %s, %d Lieferanten, Quellen: Plenty %d, Belege %d, Mail-Absender %d" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), len(vendors), len(plenty), sum(len(x) for x in ibx.values()), len(senders)), ""]
    todo = []
    for v in vendors:
        pr = propose(v, plenty, ibx.get(v["id"], []), senders)
        if pr["fill"] or pr["add"]:
            todo.append((v, pr))
            rep.append("## %s" % v["name"])
            rep += ["- Kontakt %s: %s = %s [%s]" % ((v["contacts"][i].get("name") or v["contacts"][i].get("email") or "#%d" % i), f, val, src) for i, f, val, src in pr["fill"]]
            rep += ["- NEUER Kontakt: %s <%s> %s [%s]" % (c["name"] or "?", c["email"], c["phone"], c["src"]) for c in pr["add"]]
    rep += ["", "Lieferanten mit Ergaenzungen: %d von %d" % (len(todo), len(vendors))]
    if a.apply and todo:
        H = {"Authorization": "Bearer " + os.environ.get("LIFECYCLE_API_KEY", ""), "Content-Type": "application/json"}
        BASE = "https://app-be.lifecycleplm.com/api/v1/vendors"
        rep += ["", "## Schreibergebnis"]
        for v, pr in todo:
            g = requests.get("%s/%s" % (BASE, v["id"]), headers=H, timeout=30).json()
            base = {k: g[k] for k in g if k not in ("recentOrders", "components", "samples", "performance")}
            cs = [dict(c) for c in g.get("contacts", [])]
            by_id = {c.get("email") or c.get("name"): c for c in cs}
            for i, f, val, _ in pr["fill"]:
                src = v["contacts"][i]
                tgt = next((c for c in cs if c.get("_id") == src.get("_id")), None)
                if tgt is not None and not tgt.get(f):
                    tgt[f] = val
            have = {str(c.get("email") or "").lower() for c in cs}
            for c in pr["add"]:
                if c["email"] not in have:
                    cs.append({k: val for k, val in (("name", c["name"]), ("email", c["email"]), ("phone", c["phone"])) if val} | {"main": not any(x.get("main") for x in cs)})
            base["contacts"] = cs; base["expectedUpdatedAt"] = g["updatedAt"]
            r = requests.put("%s/%s" % (BASE, v["id"]), json=base, headers=H, timeout=30)
            after = requests.get("%s/%s" % (BASE, v["id"]), headers=H, timeout=30).json()
            ok = all(any(c.get("_id") == v["contacts"][i].get("_id") and c.get(f) == val for c in after.get("contacts", [])) for i, f, val, _ in pr["fill"]) and \
                all(any(str(c.get("email") or "").lower() == n["email"] for c in after.get("contacts", [])) for n in pr["add"])
            rep.append("- %s: PUT %s | %s" % (v["name"], r.status_code, "zurueckgelesen und gleich" if ok else "ABWEICHUNG: " + r.text[:160]))
    (ROOT / "output" / "vendors_fill.md").write_text("\n".join(rep))
    print("\n".join(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
