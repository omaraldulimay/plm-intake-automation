"""Neue Lieferanten automatisch anlegen, wenn die Pruefung 'vendor_unknown' meldet.

  python3 -m plm_intake.vendors_new propose [--inbox ..]   # listet unbekannte Lieferanten + Vorschlag (Alias-Verdacht oder NEU), schreibt NICHTS
  python3 -m plm_intake.vendors_new create <spec.json> [--apply]   # legt NEU an (ohne --apply nur Trockenlauf)
Spec: {"name","country","website","description_parts":{"payee","goods","capability","terms","note"},"address","contacts":[{"name","email","phone"}]}
Regeln: nie anlegen, wenn ein aehnlicher Name schon existiert (Alias-Verdacht -> Mensch); keine Bankdaten; PLM schreibt per POST (name, description) + PUT (Kontakte/Adressen, expectedUpdatedAt).
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

LEGAL = {"co", "ltd", "limited", "pvt", "private", "gmbh", "inc", "llc", "company", "corp", "sti", "san", "tic", "kg", "ag", "the", "and", "industry", "trading"}
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())


GENERIC = LEGAL | {"hong", "kong", "manufacturing", "garment", "garments", "apparel", "textile", "tekstil", "sports", "group", "international", "myanmar", "dongguan", "kontor", "sanayi", "ticaret", "sirketi", "anonim", "ve", "san", "tic", "dis", "ihracat", "pazarlama", "industrial", "enterprises", "exports", "export", "import", "trade"}


def core_key(s):
    """Firmenkern ohne Rechtsform/Allerweltswoerter, zusammengeschrieben: 'LIEFERANT_V LIMITED' -> 'lieferant_v'."""
    return "".join(t for t in re.findall(r"[a-z0-9]+", str(s or "").lower()) if t not in GENERIC)


def tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", str(s or "").lower()) if t not in LEGAL and len(t) > 1}


def similar(name, vendors):
    """Aehnliche vorhandene Lieferanten: gleiche Firmen-Kerntokens oder hohe Textaehnlichkeit."""
    out = []
    tn = tokens(name)
    for v in vendors:
        tv = tokens(v["name"])
        ratio = difflib.SequenceMatcher(None, norm(name), norm(v["name"])).ratio()
        overlap = len(tn & tv) / max(1, min(len(tn), len(tv))) if tn and tv else 0
        ck, vk = core_key(name), core_key(v["name"])
        in_desc = bool(ck) and len(ck) >= 5 and ck in norm(v.get("description"))   # z. B. rechtlicher Zahlungsempfaenger (Payee) im Lieferanten hinterlegt
        typo = bool(ck and vk and min(len(ck), len(vk)) >= 5 and difflib.SequenceMatcher(None, ck, vk).ratio() >= 0.85)   # Tippfehler im Firmenkern: lieferant_i / lieferant_i
        if typo or ratio >= 0.8 or overlap >= 0.6 or norm(name) in norm(v["name"]) or norm(v["name"]) in norm(name) or (ck and vk and (ck == vk or ck.startswith(vk) or vk.startswith(ck)) and min(len(ck), len(vk)) >= 4) or in_desc:
            out.append((v["name"], round(max(ratio, overlap), 2) if not in_desc else "Payee/Beschreibung"))
    return out


def description(spec):
    d = spec.get("description_parts") or {}
    parts = []
    for key, label in (("payee", "Payee"), ("goods", "Goods"), ("capability", "Capability"), ("terms", "Payment terms"), ("note", "Note")):
        if d.get(key): parts.append("%s: %s" % (label, d[key]))
    if spec.get("country"): parts.insert(0, "Country: " + spec["country"])
    text = " | ".join(parts)
    for pat in core.BANK_PATTERNS:
        if re.search(pat, text): raise ValueError("Bankdaten in der Beschreibung erkannt: nicht ins PLM")
    return text


def mail_domain_vendor(spec, vendors):
    """Kontakt-Mail-Domain gleicht dem Namen eines vorhandenen Lieferanten ('kontakt@lieferant-e.example' -> 'Lieferant E'): Alias-Verdacht."""
    out = []
    for c in spec.get("contacts") or []:
        dom = (str(c.get("email") or "").split("@")[-1].split(".")[0]).lower()
        if len(dom) >= 5:
            for v in vendors:
                vk = core_key(v["name"])
                if len(vk) >= 4 and (dom.startswith(vk) or vk.startswith(dom)): out.append((v["name"], "Mail-Domain " + dom))
    return out


FREE_MAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com", "qq.com", "163.com", "126.com", "icloud.com", "web.de", "gmx.de", "gmx.net", "live.com", "foxmail.com"}


def domain_alias(spec, vendors, aliases=None):
    """Belegname unbekannt, aber die Kontakt-Mail-Domain des Belegs ist EXAKT die Domain eines Kontakts von genau EINEM vorhandenen Lieferanten
    (Rolle Lieferant/ohne Rolle, kein Freemail/Smilodox, Name ohne Namensaehnlichkeit zu irgendeinem Lieferanten): dann ist der Belegname ein Handels-/Firmenname desselben
    Lieferanten (z. B. 'Lieferant AC FZCO' mit Mail @lieferant-b.example = Lieferant B). -> Vendor oder None. Nie bei Spediteur/Carrier."""
    if (spec.get("role") or "SUPPLIER") != "SUPPLIER" or similar(spec["name"], vendors):
        return None
    doms = {str(c.get("email") or "").split("@")[-1].lower() for c in spec.get("contacts") or [] if "@" in str(c.get("email") or "")}
    doms = {d for d in doms if d and "smilodox" not in d and d not in FREE_MAIL}
    hit = [v for v in vendors if doms & {str(c.get("email") or "").split("@")[-1].lower() for c in v.get("contacts") or [] if "@" in str(c.get("email") or "")}]
    return hit[0] if len(hit) == 1 else None


def create(spec, vendors, apply=False):
    sim = similar(spec["name"], vendors) + mail_domain_vendor(spec, vendors)
    if sim:
        return {"status": "ALIAS_VERDACHT", "similar": sim, "hint": "Aehnlicher Lieferant existiert schon: Alias setzen oder Mensch entscheidet"}
    desc = description(spec)
    if not apply:
        return {"status": "TROCKENLAUF", "would_create": spec["name"], "description": desc}
    import plm_client
    st, _ = plm_client.call("POST", "vendors", {"name": spec["name"], "description": desc})
    s2, lst = plm_client.call("GET", "vendors")
    lst = lst if isinstance(lst, list) else lst.get("data", lst)
    v = next((x for x in lst if norm(x["name"]) == norm(spec["name"])), None)
    if not v: return {"status": "FEHLER", "msg": "nach POST (%s) nicht gefunden: nichts wiederholen, pruefen" % st}
    base = {k: v[k] for k in v if k not in ("recentOrders", "components", "samples", "performance")}
    contacts = [{"name": c["name"], "main": i == 0, **{k: c[k] for k in ("email", "phone") if c.get(k)}} for i, c in enumerate(spec.get("contacts") or [])]
    addresses = [{"name": spec["name"], "line1": spec["address"], "main": True}] if spec.get("address") else []
    base.update({"contacts": contacts, "addresses": addresses, "description": desc, "expectedUpdatedAt": v["updatedAt"]})
    if spec.get("website"): base["website"] = spec["website"]
    sp, _ = plm_client.call("PUT", "vendors/" + v["id"], base)
    s3, lst = plm_client.call("GET", "vendors")
    lst = lst if isinstance(lst, list) else lst.get("data", lst)
    after = next(x for x in lst if x["id"] == v["id"])
    ok = len(after["contacts"]) == len(contacts) and len(after["addresses"]) == len(addresses)
    return {"status": "ANGELEGT" if ok else "ABWEICHUNG", "id": v["id"], "put": sp, "contacts": len(after["contacts"]), "addresses": len(after["addresses"])}


def spec_from_info(name, info, goods_hint=None):
    """Aus dem vendor_info der Auslese (Briefkopf/Signatur) eine Anlage-Spec bauen. Fehlendes bleibt leer (nichts erfinden)."""
    info = info or {}
    role = info.get("role")
    note = {"FORWARDER": "Freight forwarder / customs broker, not a goods supplier", "CARRIER": "Carrier, not a goods supplier"}.get(role)
    return {"name": info.get("legal_name") or name, "country": info.get("country"), "website": info.get("website"), "address": info.get("address"),
            "description_parts": {"goods": goods_hint, "note": note or "Created automatically from mail data, please review"},
            "contacts": [c for c in info.get("contacts") or []]}


def auto(inbox, vendors, apply=False, aliases=None):
    """propose + create: legt NEU-Faelle an, Alias-Verdacht bleibt beim Menschen. Nach jedem Anlegen wird die Lieferantenliste neu gelesen (keine Dubletten im selben Lauf)."""
    results = []
    for e in propose(inbox, vendors, aliases):
        if not e["suggestion"].startswith("NEU_ANLEGEN"):
            results.append({"name": e["name"], "status": "MENSCH", "why": e["suggestion"]}); continue
        spec = spec_from_info(e["name"], e.get("vendor_info"))
        spec["role"] = (e.get("vendor_info") or {}).get("role")
        dv = domain_alias(spec, vendors, aliases)
        if dv:   # gleiche Mail-Domain wie ein vorhandener Lieferant: Alias statt Neuanlage (aliases wird im Speicher ergaenzt, der Aufrufer speichert nur bei --apply)
            results.append({"name": e["name"], "status": "ALIAS_AUTO", "vendor": dv["name"], "why": "Mail-Domain gehoert zu %s" % dv["name"]})
            if aliases is not None:   # im Speicher immer (Trockenlauf zeigt die Wirkung), gespeichert wird nur bei --apply (auto_run)
                aliases[e["name"]] = dv["name"]
            continue
        r = create(spec, vendors, apply)
        results.append({"name": e["name"], **r})
        if apply and r.get("status") == "ANGELEGT":
            import plm_client
            st, lst = plm_client.call("GET", "vendors"); vendors = lst if isinstance(lst, list) else lst.get("data", lst)
    return results


def propose(inbox, vendors, aliases=None):
    seen = {}
    for f in sorted(Path(inbox).glob("*.json")):
        if f.name.endswith("_events.json"): continue
        try: po = json.load(open(f))
        except ValueError: continue
        name = po.get("vendor")
        if not name or core.match_vendor(name, vendors, aliases or {})[0]: continue
        e = seen.setdefault(norm(name), {"name": name, "files": [], "items": 0, "vendor_info": po.get("vendor_info")})
        e["files"].append(f.name); e["items"] += len(po.get("items") or [])
        if po.get("vendor_info") and not e["vendor_info"]: e["vendor_info"] = po["vendor_info"]
    out = []
    for e in seen.values():
        sim = similar(e["name"], vendors)
        e["suggestion"] = ("ALIAS_PRUEFEN " + str(sim)) if sim else ("NEU_ANLEGEN" if e["items"] else "NEU_ANLEGEN_DIENSTLEISTER (keine Warenpositionen)")
        out.append(e)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("spec", nargs="?"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--inbox", default=str(core.__file__ and Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage/Inbox"))
    a = ap.parse_args()
    ctx = json.load(open(ROOT / "output/intake/ctx_snapshot.json")); vendors = ctx["vendors"]
    if a.cmd == "propose":
        for e in propose(a.inbox, vendors): print(json.dumps(e, ensure_ascii=False))
    elif a.cmd == "auto":
        import plm_client
        s, lst = plm_client.call("GET", "vendors"); vendors = lst if isinstance(lst, list) else lst.get("data", lst)
        for r in auto(a.inbox, vendors, a.apply): print(json.dumps(r, ensure_ascii=False))
    elif a.cmd == "create":
        import plm_client
        s, lst = plm_client.call("GET", "vendors"); vendors = lst if isinstance(lst, list) else lst.get("data", lst)
        print(json.dumps(create(json.load(open(a.spec)), vendors, a.apply), ensure_ascii=False))
