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


def stichprobe(pool, now, n=STICHPROBE_N, rng=None):
    """Nur an Dienstag/Freitag: bis zu n zufaellige Eintraege aus pool (Liste von dict order/betreff/text). Sonst None."""
    if now.weekday() not in STICHPROBE_TAGE:
        return None
    pool = list(pool or [])
    rng = rng or random.Random(now.strftime("%Y-%m-%d %H"))
    return rng.sample(pool, min(n, len(pool)))


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
    # 3. Klaerfaelle
    rows = facts.get("klaer_rows") or []
    offen = facts.get("klaer_offen")
    neu, erst = neue_faelle(rows, verlauf)
    prev = None
    for tag in sorted((verlauf.get("tage") or {}), reverse=True):
        if tag < now.strftime("%Y-%m-%d") and verlauf["tage"][tag] is not None:
            prev = verlauf["tage"][tag]; break
    if offen is None:
        offen_txt = "offen gesamt unbekannt (Trockenlauf: %d Kandidaten)" % len(rows)
    else:
        diff = ("%+d zum Vortag" % (offen - prev)) if prev is not None else "kein Vortagswert"
        offen_txt = "offen gesamt %d (%s)" % (offen, diff)
    L.append("3. Klaerfaelle: %s%s" % (offen_txt, ", Erstlauf (alle gelten als bekannt)" if erst else ", neu entstanden: %d" % len(neu)))
    for r in neu[:MAX_FAELLE]:
        v = r.get("values") or {}
        L.append("   - %s: %s" % (_kurz(r.get("category"), 40), _kurz(v.get("Warum offen") or v.get("Was"), 110)))
    if len(neu) > MAX_FAELLE:
        L.append("   - und %d weitere" % (len(neu) - MAX_FAELLE))
    # 4. Warnungen
    w = list(facts.get("warnungen") or [])
    L.append("4. Warnungen: " + ("keine" if not w else "%d" % len(w)))
    L += ["   - " + _kurz(x, 160) for x in w[:8]] + (["   - und %d weitere" % (len(w) - 8)] if len(w) > 8 else [])
    # 5. Aliase
    al = facts.get("aliase") or []
    L.append("5. Auffaelligkeiten, neu gelernte Aliase (Kennung -> Bestellung): " + ("keine" if not al else str(len(al))))
    L += ["   - %s -> %s" % (_kurz(a.get("key"), 50), _kurz(a.get("order"), 70)) for a in al[:15]] + (["   - und %d weitere" % (len(al) - 15)] if len(al) > 15 else [])
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
