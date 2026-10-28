"""Kurzer Tagesbericht des Einpflege-Laufs (deutsch, ohne Fachjargon, ca. 15 Zeilen) + Stichprobe an Dienstag und Freitag.

Quelle: output/intake/tagesdaten.json (schreibt auto_run am Lauf-Ende) + status/Exit-Code (health.finish).
Ablage: output/intake/tagesbericht.md (im Zustandszweig gesichert), GitHub-Actions-Job-Summary (cloud_run.sh) und Verlauf in tagesbericht_verlauf.json
(offen gesamt je Tag -> Veraenderung zum Vortag; schon gemeldete Klaerfaelle -> 'neu entstanden').
Kein Mailversand: aus dem Lauf gibt es keinen (Warnungen laufen ueber macOS-Mitteilung/Apps-Script-Waechter). Schreibt nie ins PLM.

  python3 -m plm_intake.tagesbericht <exit> [dry|apply]     # fuer Faelle ohne health.finish (Abbruch der Vorabpruefung)
"""
import datetime as dt
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "output" / "intake"
DATEN = "tagesdaten.json"
VERLAUF = "tagesbericht_verlauf.json"
BERICHT = "tagesbericht.md"
TAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
STICHPROBE_TAGE = (1, 4)   # Dienstag, Freitag
STICHPROBE_N = 10
MAX_FAELLE = 5
PREIS_AUFFAELLIG_TAGE = 14   # Order ohne Preis seit mindestens so vielen Tagen = auffaellig
MAX_PREIS_ZEILEN = 8


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


def _kurz(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def neue_faelle(rows, verlauf):
    """(neu, erstlauf): Klaerfall-Zeilen, deren Marker noch in keinem frueheren Bericht vorkamen. Ohne Vorgaenger = Erstlauf (alles gilt als bekannt)."""
    seen = set(verlauf.get("gesehen") or [])
    if not verlauf.get("gesehen") and not verlauf.get("tage"):
        return [], True
    return [r for r in rows if r.get("marker") not in seen], False


def warn_key(w):
    """Schluessel einer Warnung = Art + Datei/Order (Text bis zum ersten ': ', ohne Zaehler in Klammern); Meldungstext und Zahlen zaehlen nicht."""
    w = " ".join(str(w or "").split())
    parts = w.split(": ")
    k = ": ".join(parts[:2]) if w.startswith(("UNSTIMMIG/Mensch: ", "Lieferant ohne Lieferanten-ID: ")) and len(parts) > 2 else parts[0]
    return re.sub(r" \(\d+\)$", "", k)[:160]


def warnungen_split(warnungen, verlauf, now):
    """(neu, bekannt_anzahl, aelteste_tage, neuer_stand). neuer_stand = {schluessel: Datum erstmals gesehen}; verschwundene Warnungen fallen heraus."""
    alt = verlauf.get("warnungen") or {}
    heute = now.strftime("%Y-%m-%d")
    neu, stand, bekannt = [], {}, 0
    for w in warnungen:
        k = warn_key(w)
        if k in alt:
            stand[k] = alt[k]
            if k not in {warn_key(x) for x in neu}:
                bekannt += 1
        elif k not in stand:
            stand[k] = heute; neu.append(w)
    tage = None
    if bekannt:
        try:
            tage = max((now.date() - dt.date.fromisoformat(stand[k])).days for k in stand if k in alt)
        except ValueError:
            tage = None
    return neu, bekannt, tage, stand


def stichprobe(pool, now, n=STICHPROBE_N, rng=None):
    """Nur an Dienstag/Freitag: bis zu n zufaellige Eintraege aus pool (Liste von dict order/betreff/text). Sonst None."""
    if now.weekday() not in STICHPROBE_TAGE:
        return None
    pool = list(pool or [])
    rng = rng or random.Random(now.strftime("%Y-%m-%d %H"))
    return rng.sample(pool, min(n, len(pool)))


def _pct(a, n):
    return "%.0f %%" % (100.0 * a / n) if n else "-"


def quote_summe(stand):
    """{marker: 'ok'|'info'|'offen'} -> (ok, info, offen)."""
    v = list((stand or {}).values())
    return v.count("ok"), v.count("info"), v.count("offen")


def quote_zeilen(quote, verlauf):
    """Automatisierungsquote = geschriebene Ereignisse+Belege / alle verarbeiteten (geschrieben + Info + offen). Lauf und seit Start (letzter Zustand je Marker, Verlauf 'quote_stand' inkl. dieses Laufs)."""
    if not quote:
        return []
    ok, info, offen = len(quote.get("ok") or []), len(quote.get("info") or []), len(quote.get("offen") or [])
    stand = dict(verlauf.get("quote_stand") or {})
    for k in ("ok", "info", "offen"):
        for m in quote.get(k) or []:
            stand[m] = k
    so, si, sf = quote_summe(stand)
    n = ok + info + offen
    return ["   Automatisierungsquote (ohne Mensch = geschrieben + Info): Lauf %s (geschrieben %d, Info %d, offen %d, zusammen %d) | seit Start %s (zusammen %d) | neu offen %d, neu Info %d" % (
        _pct(ok + info, n), ok, info, offen, n,
        _pct(so + si, so + si + sf), so + si + sf,
        sum(1 for m in quote.get("offen") or [] if (verlauf.get("quote_stand") or {}).get(m) != "offen"),
        sum(1 for m in quote.get("info") or [] if (verlauf.get("quote_stand") or {}).get(m) != "info"))]


def build(facts, exit_code, mode, state_text="", now=None, verlauf=None, dauer_s=None, rng=None):
    """Berichtstext (Markdown). facts darf None/leer sein (Lauf vorzeitig abgebrochen)."""
    now = now or dt.datetime.now()
    facts = facts or {}
    verlauf = verlauf if verlauf is not None else {}
    apply = mode == "apply"
    fehler = int(exit_code or 0) != 0 or bool(facts.get("abbruch"))
    dauer = dauer_s if dauer_s is not None else facts.get("dauer_s")
    dtxt = ("%d Min" % max(1, round(dauer / 60)) if dauer >= 60 else "%d Sek" % dauer) if isinstance(dauer, (int, float)) else "unbekannt"
    L = ["# Tagesbericht Einpflege %s (%s)" % (now.strftime("%d.%m.%Y %H:%M"), TAGE[now.weekday()])]
    L.append("1. Status: %s | Modus: %s | Dauer: %s" % ("FEHLER" if fehler else "OK", "schreibt ins PLM (apply)" if apply else "Trockenlauf (dry, schreibt nichts)", dtxt))
    if fehler and (facts.get("abbruch") or state_text):
        L.append("   Grund: " + _kurz(facts.get("abbruch") or state_text, 220))
    if not facts:
        L.append("   Keine Lauf-Daten vorhanden (Lauf vor Ende abgebrochen oder gar nicht gestartet).")
        L.append("   Bitte Job-Protokoll in GitHub Actions bzw. output/intake/STATUS.md ansehen.")
        return "\n".join(L) + "\n"
    z = facts.get("zahlen") or {}
    L.append("2. Zahlen (%s): neue Bestellungen %s | ergaenzte Notizen %s | Sendungen neu/aktualisiert %s/%s | neue Techpacks %s | neu gelernte Aliase %s" % (
        "geschrieben" if apply else "nur geplant", z.get("orders", 0), z.get("notes", 0), z.get("ship_new", 0), z.get("ship_upd", 0), z.get("techpacks", 0), len(facts.get("aliase") or [])))
    if z.get("inhalt_aktiv"):   # Inhaltsbasierte Zuordnung (content_match, Schalter CONTENT_MATCH): nur Notiz, belegter Treffer steht in der Notizzeile
        L.append("   inhaltlich zugeordnet %s (nur Notiz, nie Termin/Status/Zahlung)" % z.get("inhalt", 0))
    if z.get("programm") or z.get("nummer") or z.get("info_regel"):   # Programm-Gruppen / Betreffnummer / Info-Regel (nur Notizen bzw. Info)
        L.append("   ueber Programm zugeordnet %s | ueber Betreffnummer/Positionswort %s | als Info (Muster/Streichung ohne Order) %s (nur Notiz, nie Termin/Status/Zahlung)" % (z.get("programm", 0), z.get("nummer", 0), z.get("info_regel", 0)))
    if facts.get("zuordnung") is not None:   # Eingaben des Menschen in der Klaerfaelle-Tabelle (Spalte 'Zuordnung')
        L.append("   Zuordnungen aus der Tabelle: angewendet %s, abgelehnt %s" % (facts["zuordnung"].get("angewendet", 0), facts["zuordnung"].get("abgelehnt", 0)))
    # 3. Klaerfaelle
    rows = facts.get("klaer_rows") or []
    offen = facts.get("klaer_offen")
    neu, erst = neue_faelle(rows, verlauf)
    m = facts.get("mensch")
    prev = None
    for tag in sorted((verlauf.get("tage") or {}), reverse=True):
        if tag < now.strftime("%Y-%m-%d") and verlauf["tage"][tag] is not None:
            prev = verlauf["tage"][tag]; break
    if offen is None:
        offen_txt = "offen gesamt unbekannt (Trockenlauf: %d Kandidaten)" % len(rows)
    else:
        diff = ("%+d zum Vortag" % (offen - prev)) if prev is not None else "kein Vortagswert"
        offen_txt = "%s %d (%s)" % ("in Klaerfaelle-Tabelle offen" if m else "offen gesamt", offen, diff)
        if facts.get("klaer_rows_total") is not None:
            offen_txt = "in Tabelle offen %d (gesamt %d, geloescht heute %d; %s)" % (offen, facts["klaer_rows_total"], facts.get("klaer_geloescht") or 0, diff)
    L.append("3. Klaerfaelle: %s%s" % (offen_txt, ", Erstlauf (alle gelten als bekannt)" if erst else ", neu entstanden: %d" % len(neu)))
    if m:
        L.append("   Mensch entscheidet %d (wie Konsole): Belege %d | Ereignisse %d | Sendungen %d | Limit/sonstige %d" % (
            m.get("gesamt", 0), m.get("belege", 0), m.get("ereignisse", 0), m.get("sendungen", 0), m.get("sonstige", 0)))
    q = quote_zeilen(facts.get("quote"), verlauf)
    if q:
        L += q
    for r in neu[:MAX_FAELLE]:
        v = r.get("values") or {}
        L.append("   - %s: %s" % (_kurz(r.get("category"), 40), _kurz(v.get("Warum offen") or v.get("Was"), 110)))
    if len(neu) > MAX_FAELLE:
        L.append("   - und %d weitere" % (len(neu) - MAX_FAELLE))
    # 4. Warnungen
    w = list(facts.get("warnungen") or [])
    wneu, wbek, wtage, _ = warnungen_split(w, verlauf, now)
    kopf = "keine" if not w else "%d neu" % len(wneu)
    if wbek:
        kopf += " | %d bekannte Warnungen seit frueheren Laeufen (aelteste besteht seit %s)" % (wbek, "%d Tag%s" % (wtage, "" if wtage == 1 else "en") if wtage is not None else "unbekannt")
    L.append("4. Warnungen: " + kopf)
    L += ["   - " + _kurz(x, 160) for x in wneu[:8]] + (["   - und %d weitere neue" % (len(wneu) - 8)] if len(wneu) > 8 else [])
    if facts.get("projekte") is not None:   # Lieferanten-Projekte (vendor_projects): neu / verknuepft / Fehler
        pj = facts["projekte"]
        L.append("   Projekte: neu %s, verknuepft %s, Fehler %s%s" % (pj.get("neu", 0), pj.get("verknuepft", 0), pj.get("fehler", 0), "  WARNUNG: Projekt-Verknuepfung fehlerhaft" if pj.get("fehler") else ""))
    if facts.get("status") is not None:   # Status-Regeln (status_apply.auto): Vorschlaege / gesetzt
        stt = facts["status"]
        L.append("   Status: Vorschlaege %s, gesetzt %s%s%s" % (stt.get("vorschlaege", 0), stt.get("gesetzt", 0), "" if stt.get("auto") else " (STATUS_AUTO aus)", "  WARNUNG: Status setzen fehlerhaft" if stt.get("fehler") else ""))
    if facts.get("anhaenge") is not None:   # Beleg-Anhaenge an Orders (order_attachments)
        an = facts["anhaenge"]
        L.append("   Anhaenge: neu %s, uebersprungen %s, Fehler %s%s" % (an.get("neu", 0), an.get("uebersprungen", 0), an.get("fehler", 0), "  WARNUNG: Anhang-Upload fehlerhaft" if an.get("fehler") else ""))
    if facts.get("zahlungen") is not None:   # Zahlungsplaene (payments_plan): Platzhalter entfernt / Plaene aufgebaut / Klaerfaelle / Paid gesetzt / Fehler
        zp = facts["zahlungen"]
        L.append("   Zahlungen: Platzhalter entfernt %s, Plaene aufgebaut %s, Klaerfaelle %s, Paid gesetzt %s, Fehler %s%s" % (
            zp.get("platzhalter", 0), zp.get("plaene", 0), zp.get("klaerfaelle", 0), zp.get("paid", 0), zp.get("fehler", 0), "  WARNUNG: Zahlungsaenderung fehlerhaft" if zp.get("fehler") else ""))
    if facts.get("projekt_produkte") is not None:   # Projekt-Produkte (vendor_project_products)
        pp = facts["projekt_produkte"]
        L.append("   Projekt-Produkte: neu %s, Fehler %s%s" % (pp.get("neu", 0), pp.get("fehler", 0), "  WARNUNG: Produkt-Verknuepfung fehlerhaft" if pp.get("fehler") else ""))
    # 5. Aliase
    al = facts.get("aliase") or []
    L.append("5. Auffaelligkeiten, neu gelernte Aliase (Kennung -> Bestellung): " + ("keine" if not al else str(len(al))))
    L += ["   - %s -> %s" % (_kurz(a.get("key"), 50), _kurz(a.get("order"), 70)) for a in al[:15]] + (["   - und %d weitere" % (len(al) - 15)] if len(al) > 15 else [])
    if "preis_ausstehend" in facts:   # 6. Preis ausstehend: Orders mit Menge aber Summe 0 (Preis kommt spaeter per Proforma/Rechnung, Skript traegt ihn nach)
        pa = facts.get("preis_ausstehend") or []
        alt = [x for x in pa if (x.get("tage") if x.get("tage") is not None else -1) >= PREIS_AUFFAELLIG_TAGE]
        L.append("6. Preis ausstehend: %s" % ("keine Bestellung" if not pa else "%d Bestellung%s ohne Preis | davon %d seit %d+ Tagen (auffaellig)" % (len(pa), "" if len(pa) == 1 else "en", len(alt), PREIS_AUFFAELLIG_TAGE)))
        for x in pa[:MAX_PREIS_ZEILEN]:
            t = x.get("tage")
            L.append("   - %s: %s%s" % (_kurz(x.get("order"), 60), "Alter unbekannt" if t is None else "%d Tag%s" % (t, "" if t == 1 else "e"), " AUFFAELLIG" if t is not None and t >= PREIS_AUFFAELLIG_TAGE else ""))
        if len(pa) > MAX_PREIS_ZEILEN:
            L.append("   - und %d weitere" % (len(pa) - MAX_PREIS_ZEILEN))
    sp = stichprobe(facts.get("stichprobe_pool"), now, rng=rng)
    if sp is not None:
        L += ["", "Stichprobe (%s, %d zufaellige %s Eintraege, nur zum Pruefen):" % (TAGE[now.weekday()], len(sp), "heute geschriebene" if apply else "geplante")]
        L += ["%d. %s | Mail: %s | %s" % (i, _kurz(s.get("order"), 45), _kurz(s.get("betreff"), 70), _kurz(s.get("text"), 110)) for i, s in enumerate(sp, 1)] or ["- keine Eintraege heute"]
    return "\n".join(L) + "\n"


def write(intake, exit_code, mode, state_text="", now=None, step_summary=None):
    """Bericht bauen, in intake/tagesbericht.md ablegen, Verlauf fortschreiben. Gibt den Text zurueck. Fehler hier brechen nie etwas ab (Aufrufer faengt ab)."""
    intake = Path(intake)
    now = now or dt.datetime.now()
    facts = _load(intake / DATEN, {})
    verlauf = _load(intake / VERLAUF, {"tage": {}, "gesehen": []})
    dauer = None
    try:
        dauer = max(0, int(now.timestamp() - float(os.environ["PLM_RUN_START"])))
    except (KeyError, ValueError):
        pass
    text = build(facts, exit_code, mode, state_text, now, verlauf, dauer)
    (intake / BERICHT).write_text(text)
    if facts:
        if facts.get("klaer_offen") is not None:
            verlauf.setdefault("tage", {})[now.strftime("%Y-%m-%d")] = facts["klaer_offen"]
        elif now.strftime("%Y-%m-%d") not in verlauf.setdefault("tage", {}):
            verlauf["tage"][now.strftime("%Y-%m-%d")] = None
        if facts.get("quote"):
            qs = dict(verlauf.get("quote_stand") or {})
            for k in ("ok", "info", "offen"):
                for m in facts["quote"].get(k) or []:
                    qs[m] = k
            verlauf["quote_stand"] = dict(list(qs.items())[-20000:])
        verlauf["warnungen"] = warnungen_split(facts.get("warnungen") or [], verlauf, now)[3]
        verlauf["tage"] = dict(sorted(verlauf["tage"].items())[-30:])
        seen = list(verlauf.get("gesehen") or [])
        seen += [r["marker"] for r in facts.get("klaer_rows") or [] if r.get("marker") and r["marker"] not in seen]
        verlauf["gesehen"] = seen[-3000:]
        (intake / VERLAUF).write_text(json.dumps(verlauf, ensure_ascii=False))
    step_summary = step_summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        try:
            with open(step_summary, "a") as f:
                f.write(text + "\n")
        except OSError:
            pass
    return text


if __name__ == "__main__":
    a = sys.argv[1:]
    st = _load(INTAKE / "status.json", {})
    print(write(INTAKE, int(a[0]) if a else 0, a[1] if len(a) > 1 else "dry", st.get("text", "")))
