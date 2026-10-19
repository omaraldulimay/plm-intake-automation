#!/bin/zsh
# Zeitgesteuerter Lauf. PLM_MODE=dry (Standard): nur planen und berichten, schreibt NICHTS ins PLM. PLM_MODE=apply: schreibt.
# Ablauf: Vorabpruefung (REST + Browser-Login; bei Problem Warnung und Abbruch) -> auto_run -> Status/Warnung (health finish) -> sonntags nach dem Abendlauf Stichprobe (audit).
# Bericht: output/intake/auto_report.md, Status: output/intake/STATUS.md, Warnungen: output/intake/alerts.log, Protokoll je Lauf: output/intake/logs/
cd "/path/to/project Produktion" || exit 1
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
[ -f .venv/bin/activate ] && source .venv/bin/activate   # gleiche Python-Umgebung wie von Hand (requests usw.), auch wenn launchd startet
mkdir -p output/intake/logs
MODE="${PLM_MODE:-dry}"
LOG="output/intake/logs/auto_$(date +%Y%m%d_%H%M).log"
echo "=== $(date) Modus $MODE ===" >> "$LOG"
if ! python3 -m plm_intake.health preflight >> "$LOG" 2>&1; then
  echo "=== Abbruch: Vorabpruefung (Exit 3) $(date) ===" >> "$LOG"
  exit 3
fi
if [ "$MODE" = "apply" ]; then
  python3 -m plm_intake.auto_run --apply >> "$LOG" 2>&1
else
  python3 -m plm_intake.auto_run >> "$LOG" 2>&1
fi
RC=$?
echo "=== Ende (Exit $RC) $(date) ===" >> "$LOG"
cp output/intake/auto_report.md "output/intake/logs/report_$(date +%Y%m%d_%H%M).md" 2>/dev/null
python3 -m plm_intake.health finish "$RC" "$MODE" >> "$LOG" 2>&1
if [ "$(date +%u)" = "7" ] && [ "$(date +%H)" -ge 19 ]; then
  python3 -m plm_intake.audit >> "$LOG" 2>&1
fi
exit $RC
