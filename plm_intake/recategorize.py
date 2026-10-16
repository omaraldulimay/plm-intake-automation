"""Produkte mit Tag KATEGORIE-OFFEN (Collection Uncategorized/General) in die BESTEHENDE Struktur einsortieren (keine neuen Collections/Kategorien).

  python3 -m plm_intake.recategorize            TROCKENLAUF: Vorschlag je Produkt mit Regel und Sicherheit, Bericht output/recategorize.md
  python3 -m plm_intake.recategorize --apply    setzt Collection + Kategorie + Kategorie-Code per REST PUT (nur diese Felder, Tags angepasst), liest zurueck
Sicherheit 'sicher' = eindeutiger Produkttyp; 'aehnlich' = naechstliegende vorhandene Kategorie (z. B. Set -> Jogginghose, Kleid -> Jumpsuit): Tag KATEGORIE-PRUEFEN statt KATEGORIE-OFFEN.
Nie loeschen, ZZ-Testobjekte werden uebersprungen."""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import new_products as npd  # noqa: E402

# (Regex auf den Namen, Collection, Kategorie-Code, Sicherheit) -- Reihenfolge = Prioritaet
RULES = [
    (r"fu(ß|ss)ball\s*trikot|\btrikot\b", "T-Shirt", "TEE", "sicher"),
    (r"bikini|badeanzug|badehose|swimsuit", "Bademode", "SWM", "sicher"),
    (r"maxi\s*dress|kleid|dress\b|\brock\b|skirt", "Kleider / Röcke", "DRS", "sicher"),
    (r"boxershorts?\s*&|boxer.*unterhemd|unterhemd.*boxer", "Unterwäsche", "UWE", "sicher"),   # Packs aus Boxershorts + Unterhemd sind Unterwaesche
    (r"unterhemd|spaghetti\s*top|\btank\b(?!\s*hood)", "Tank / Stringer", "TNK", "sicher"),   # 'Tank Hoodie' bleibt Hoodie
    (r"\bstring\b|\bslip\b|unterw(ä|ae)sche|bodysuit|\bpanty\b|\btanga\b", "Unterwäsche", "UWE", "sicher"),
    (r"\bset\b|outfit|trainingsanzug|anzug", "Sets / Anzüge", "SET", "sicher"),
    (r"turnbeutel|\bbag\b|tasche|rucksack", "Accessoires", "BAG", "sicher"),
    (r"badelatschen|badeschlappen|\bslides?\b|sandale", "Badelatschen", "SLD", "sicher"),
    (r"springseil|schal\b|haarband|stirnband|zubeh", "Accessoires", "ACC", "sicher"),
    (r"\btop\b", "Crop Top", "CRP", "aehnlich"),
]


def classify(name):
    n = str(name or "").lower()
    for rx, col, code, conf in RULES:
        if re.search(rx, n):
            return col, code, conf, rx
    return None


def targets(products, cats):
    """{(Collection-Name, Kategorie-Code): (collection_id, category_id, category_name)} aus Collections-Liste und Kategorien (nur vorhandene)."""
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--recheck", action="store_true", help="auch schon einsortierte Skript-Produkte (plenty-import) neu pruefen und bei geaendertem Ziel umhaengen")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake import barcodes as bc
    from plm_intake.context import fetch_all
    products = fetch_all(plm_client.call, "products")
    st, cols = plm_client.call("GET", "collections"); cname = {c["id"]: c["name"] for c in cols}; cid = {c["name"]: c["id"] for c in cols}
    cats = bc.run_js(open(ROOT / "plm_intake" / "browser" / "list_categories.js").read())
    tgt = {}
    for c in cats:
        m = re.match(r"\s*([A-Z]{3})\b", c["name"])
        if m and cname.get(c["collectionId"]):
            tgt[(cname[c["collectionId"]], m.group(1))] = (c["collectionId"], c["id"], c["name"])
    def wanted(p):
        r = classify(p["name"]); t = tgt.get((r[0], r[1])) if r else None
        return t[1] if t else None
    todo = [p for p in products if "KATEGORIE-OFFEN" in str(p.get("tags") or "") and (p.get("collection") or {}).get("name") == "Uncategorized"
            and not re.match(r"(?i)zz", str(p.get("sku"))) and not re.match(r"(?i)zz", str(p.get("name")))]
    if a.recheck:   # schon einsortierte Skript-Produkte, deren Regelziel inzwischen ein anderes ist (z. B. neue Kategorien)
        ids = {p["id"] for p in todo}
        todo += [p for p in products if p["id"] not in ids and "plenty-import" in str(p.get("tags") or "") and not re.match(r"(?i)zz", str(p.get("sku")))
                 and wanted(p) and wanted(p) != (p.get("category") or {}).get("id")]
    rep = ["# Kategorien zuordnen (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Stand %s, %d Produkte" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), len(todo)), "",
           "| SKU | Name | -> Collection / Kategorie | Sicherheit |", "|---|---|---|---|"]
    plan, open_ = [], []
    for p in todo:
        r = classify(p["name"])
        t = tgt.get((r[0], r[1])) if r else None
        if not r or not t:
            open_.append(p); continue
        plan.append((p, r, t))
        rep.append("| %s | %s | %s / %s | %s |" % (p["sku"], p["name"][:44], r[0], t[2], r[2]))
    rep += ["", "Ohne passende vorhandene Kategorie (bleiben offen): %s" % ", ".join("%s %s" % (p["sku"], p["name"][:30]) for p in open_) if open_ else "", "Zugeordnet: %d von %d" % (len(plan), len(todo))]
    if a.apply and plan:
        import time
        rep += ["", "## Schreibergebnis"]
        for p, r, t in plan:
            cf = dict(p.get("customFields") or {}); cf[npd.KATCODE_KEY] = r[1]
            tags = [x for x in str(p.get("tags") or "").split(",") if x and x not in ("KATEGORIE-OFFEN", "KATEGORIE-PRUEFEN")]
            if r[2] != "sicher":
                tags.append("KATEGORIE-PRUEFEN")
            body = {"collectionId": t[0], "categoryId": t[1], "customFields": cf, "tags": ",".join(tags), "expectedUpdatedAt": p["updatedAt"]}
            s, resp = plm_client.call("PUT", "products/" + p["id"], body)
            rep.append("- %s: HTTP %s" % (p["sku"], s))
        time.sleep(3)
        now = {x["id"]: x for x in fetch_all(plm_client.call, "products")}
        bad = [p["sku"] for p, r, t in plan if (now[p["id"]].get("collection") or {}).get("id") != t[0] or (now[p["id"]].get("category") or {}).get("id") != t[1]]
        rep += ["", "## Rueckpruefung", "- %s" % ("ALLES zurueckgelesen und gleich (%d Produkte)" % len(plan) if not bad else "ABWEICHUNG: %s" % bad)]
    (ROOT / "output" / "recategorize.md").write_text("\n".join(rep))
    print("\n".join(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
