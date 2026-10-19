"""Betriebsueberwachung des Alltagslaufs: Vorabpruefung, Status, Warnungen.

  python3 -m plm_intake.health preflight          # Exit 0 = Lauf darf starten; Exit 3 = Abbruch (nicht eingeloggt / PLM nicht erreichbar), Warnung geht raus
  python3 -m plm_intake.health finish <exit> [dry|apply]   # nach dem Lauf: STATUS.md/status.json schreiben, bei Fehler warnen
Warnungen: macOS-Mitteilung + Zeile in output/intake/alerts.log (+ ganz oben in STATUS.md). Schreibt nie ins PLM.
"""
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INTAKE = ROOT / "output" / "intake"
BROWSER = ROOT / "plm_intake" / "browser"
STALE_HOURS = 26   # laenger ohne erfolgreichen Lauf = Warnung (2 Laeufe/Tag, 08:00 und 13:30)


def notify(title, body):
    """macOS-Mitteilung; scheitert still (z. B. ohne Desktop-Sitzung)."""
    try:
        t = re.sub(r'["\\]', "'", str(title))[:120]; b = re.sub(r'["\\]', "'", str(body))[:240]
        subprocess.run(["osascript", "-e", 'display notification "%s" with title "PLM-Einpflege: %s" sound name "Basso"' % (b, t)], capture_output=True, timeout=15)
    except Exception:
        pass


def _now():
    return dt.datetime.now()


def alert(intake, title, body, now=None):
    now = now or _now()
    intake = Path(intake); intake.mkdir(parents=True, exist_ok=True)
    with open(intake / "alerts.log", "a") as f:
        f.write("%s | %s | %s\n" % (now.isoformat(timespec="seconds"), title, str(body).replace("\n", " ")[:500]))
    notify(title, body)


def check_rest(call=None):
    """REST-Zugang (API-Key, Netz). Rueckgabe (ok, Meldung)."""
    try:
        if call is None:
            import plm_client
            call = plm_client.call
        st, _ = call("GET", "vendors")
        return (st == 200, "REST ok" if st == 200 else "REST-Zugang antwortet HTTP %s (API-Key/Rechte/Netz pruefen)" % st)
    except Exception as e:
        return False, "REST-Zugang nicht erreichbar: %s" % str(e)[:150]


def check_browser(runner=None):
    """Ist das Browser-Profil im PLM eingeloggt? (Browser-Teil liest PO-Nummern/Notizen und schreibt POs). Rueckgabe (ok, Meldung)."""
    if runner is None:
        def runner():
            r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), str(BROWSER / "ping.js")], capture_output=True, text=True, cwd=BROWSER, timeout=120)
            return r.returncode, (r.stderr or r.stdout)
    try:
        rc, out = runner()
    except Exception as e:
        return False, "Browser-Pruefung fehlgeschlagen: %s" % str(e)[:150]
    if rc == 0:
        return True, "Browser eingeloggt"
    if rc == 3:
        return False, "PLM-Browser NICHT eingeloggt: einmal 'cd plm_intake/browser && node run_in_plm.js --login' ausfuehren und im Fenster einloggen"
    return False, "Browser-Lauf scheitert (Exit %s): %s" % (rc, str(out)[-150:])


def inbox_age_hours(inbox, now=None):
    """Stunden seit der juengsten Datei im Inbox-Ordner (None = leer/nicht lesbar)."""
    try:
        times = [f.stat().st_mtime for f in Path(inbox).glob("*.json")]
    except OSError:
        return None
    if not times:
        return None
    return ((now or _now()).timestamp() - max(times)) / 3600


def inbox_stale(age, now):
    """Zu lange keine neue Auslese-Datei? Werktags-Schwelle 30 h, montags 66 h (Wochenende), Sa/So nie."""
    if age is None or now.weekday() >= 5:
        return False
    return age > (66 if now.weekday() == 0 else 30)


def load_status(intake):
    p = Path(intake) / "status.json"
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def stale_hours(status, now=None):
    """Stunden seit dem letzten erfolgreichen Lauf (None = noch nie)."""
    ok = status.get("last_ok")
    if not ok:
        return None
    return ((now or _now()) - dt.datetime.fromisoformat(ok)).total_seconds() / 3600


def preflight(intake=INTAKE, rest=None, browser=None, now=None, inbox=None):
    """Rueckgabe (ok, [Meldungen]). Bei Misserfolg wird gewarnt und der Status auf ALARM gesetzt. Eine veraltete Inbox (Auslese liefert nichts mehr) warnt, bricht aber nicht ab."""
    now = now or _now()
    msgs, failed, ok = [], [], True
    for check in (rest or check_rest, browser or check_browser):
        good, m = check()
        msgs.append(m); ok = ok and good
        if not good:
            failed.append(m)
    if inbox is not None:
        age = inbox_age_hours(inbox, now)
        if inbox_stale(age, now):
            msgs.append("Inbox: letzte neue Datei vor %.0f Stunden (Auslese in Apps Script pruefen: Trigger, Ausfuehrungen, Budget)" % age)
            alert(intake, "Auslese liefert nichts Neues", msgs[-1], now)
    h = stale_hours(load_status(intake), now)
    if h is not None and h > STALE_HOURS:
        msgs.append("Letzter erfolgreicher Lauf vor %.0f Stunden" % h)
        alert(intake, "Lange kein erfolgreicher Lauf", msgs[-1], now)
    if not ok:
        alert(intake, "Lauf abgebrochen (Vorabpruefung)", "; ".join(failed), now)
        write_status(intake, "ALARM", "Vorabpruefung: " + "; ".join(msgs), now=now)
    return ok, msgs


def summarize(report_text, exit_code):
    """Kennzahlen aus auto_report.md: (Status, Kurztext). ALARM bei Exit != 0 oder ABBRUCH im Bericht."""
    t = report_text or ""
    def first(rx, default=0):
        m = re.search(rx, t); return int(m.group(1)) if m else default
    new_docs = first(r"Neu: (\d+) Dokument"); new_evs = first(r"Dokument-Dateien, (\d+) Ereignis")
    human = first(r"## Mensch entscheidet \((\d+)\)")
    sec = re.search(r"## Neue Bestellungen \(CREATE\)\n(.*?)\n\n", t, re.S)
    pos = len([l for l in (sec.group(1).splitlines() if sec else []) if l.startswith("- ") and "keine" not in l])
    sh = re.search(r"## Sendungen \(Bereich Shipments\)\n(.*?)\n\n", t, re.S)
    ships = len([l for l in (sh.group(1).splitlines() if sh else []) if l.startswith("- neu") or l.startswith("- aktualisiert")])
    abort = [l for l in t.splitlines() if "ABBRUCH" in l]
    state = "ALARM" if exit_code or abort else "OK"
    txt = "%d neue Dokumente, %d Ereignis-Dateien | neue POs %d, Sendungen %d | Mensch entscheidet: %d" % (new_docs, new_evs, pos, ships, human)
    if abort:
        txt = abort[0].strip()[:200] + " | " + txt
    return state, txt


def write_status(intake, state, text, mode="", now=None):
    now = now or _now()
    intake = Path(intake); intake.mkdir(parents=True, exist_ok=True)
    st = load_status(intake)
    st.update({"last_run": now.isoformat(timespec="seconds"), "state": state, "mode": mode or st.get("mode", ""), "text": text})
    if state == "OK":
        st["last_ok"] = now.isoformat(timespec="seconds")
    with open(intake / "status.json", "w") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)
    alerts = ""
    try:
        alerts = "\n".join("- " + l for l in (intake / "alerts.log").read_text().splitlines()[-5:])
    except OSError:
        pass
    (intake / "STATUS.md").write_text("# Status Einpflege-Automatik\n\n**%s** (%s, %s)\n\n%s\n\nLetzter erfolgreicher Lauf: %s\n\n## Letzte Warnungen\n%s\n" % (
        state, st["last_run"].replace("T", " "), st["mode"] or "-", text, (st.get("last_ok") or "noch nie").replace("T", " "), alerts or "- keine"))


HEARTBEAT = "lokaler_lauf_heartbeat.json"


def write_heartbeat(intake, state, mode, text, now=None, inbox=None):
    """Herzschlag fuer den Waechter in Apps Script (plmWatchdog): liegt im Drive-Ordner PLM-Mails (Elternordner der Inbox). Scheitert still."""
    now = now or _now()
    try:
        from plm_intake import cloud, daily
        folder = Path(intake) if cloud.is_cloud_inbox() else Path(inbox or daily.resolve_inbox(None, Path(intake))).resolve().parent   # Cloud: Heartbeat im Zustandsordner (Drive nur lesbar)
        (folder / HEARTBEAT).write_text(json.dumps({"last_run": now.astimezone().isoformat(timespec="seconds"), "state": state, "mode": mode, "text": str(text)[:300]}, ensure_ascii=False))
        return True
    except Exception:
        return False


def finish(intake, exit_code, mode="dry", now=None):
    now = now or _now()
    intake = Path(intake)
    try:
        rep = (intake / "auto_report.md").read_text()
    except OSError:
        rep = ""
    state, text = summarize(rep, int(exit_code))
    write_status(intake, state, text, mode, now)
    write_heartbeat(intake, state, mode, text, now)
    wrote = mode == "apply" and re.search(r"Erledigt|Ergebnis ", rep)
    if state == "ALARM":
        alert(intake, "Lauf mit Problem (%s)" % mode, text, now)
    elif wrote or now.hour >= 19:   # sonst keine Mitteilung bei jedem ruhigen Lauf
        notify("Lauf ok (%s)" % mode, text)
    return state, text


def main(argv=None):
    a = list(argv if argv is not None else sys.argv[1:])
    if a[:1] == ["preflight"]:
        from plm_intake import daily
        ok, msgs = preflight(inbox=daily.resolve_inbox(None, INTAKE)); print("\n".join(msgs)); return 0 if ok else 3
    if a[:1] == ["finish"] and len(a) >= 2:
        s, t = finish(INTAKE, a[1], a[2] if len(a) > 2 else "dry"); print(s, t); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
