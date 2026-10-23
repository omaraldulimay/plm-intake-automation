#!/usr/bin/env bash
# Cloud-Lauf (GitHub Actions), spiegelt scheduled_run.sh ohne macOS-Pfade.
# Env: PLM_MODE=dry (Standard) | apply, PLM_INBOX_MODE=drive_api, CI=true, PLM_EMAIL/PLM_PASSWORD, LIFECYCLE_API_KEY, GOOGLE_SA_JSON.
# Zustand: STATE_DIR (Standard _state) wird vorher geholt (cloud pull) und nachher gesichert (cloud push) - das Committen macht der Workflow.
cd "$(dirname "$0")/.." || exit 1
MODE="${PLM_MODE:-dry}"
STATE_DIR="${STATE_DIR:-_state}"
export PLM_INBOX_MODE="${PLM_INBOX_MODE:-drive_api}"
export CI="${CI:-true}"
export PLM_STORAGE_STATE="${PLM_STORAGE_STATE:-${RUNNER_TEMP:-/tmp}/plm_storage_state.json}"
mkdir -p output/intake/logs
export PLM_DEBUG_DIR="$PWD/output/intake/logs"
export PLM_RUN_START="$(date +%s)"
LOG="output/intake/logs/auto_$(date -u +%Y%m%d_%H%M).log"
python3 -m plm_intake.cloud pull "$STATE_DIR" >> "$LOG" 2>&1
if [ "${SKIP_IF_RECENT_MIN:-0}" -gt 0 ] && python3 - "$SKIP_IF_RECENT_MIN" "$MODE" >> "$LOG" 2>&1 <<'PY'
import json, sys, datetime as dt
# Nur ueberspringen, wenn der letzte Lauf im GLEICHEN Modus erfolgreich war (ein Trockenlauf von Hand darf einen Schreiblauf nicht blockieren).
try:
    st = json.load(open("output/intake/status.json"))
    ok = st.get("last_ok")
    same = st.get("state") == "OK" and st.get("mode") == sys.argv[2]
    age = (dt.datetime.utcnow() - dt.datetime.fromisoformat(ok)).total_seconds() / 60 if ok and same else 1e9
except Exception:
    age = 1e9
print("Letzter erfolgreicher Lauf im Modus %s vor %s Min" % (sys.argv[2], "%.0f" % age if age < 1e8 else "?"))
sys.exit(0 if age < int(sys.argv[1]) else 1)
PY
then
  echo "=== Uebersprungen: Lauf in den letzten ${SKIP_IF_RECENT_MIN} Min schon erfolgt ===" >> "$LOG"
  tail -n 5 "$LOG"; exit 0
fi
echo "=== $(date -u) Modus $MODE (Cloud) ===" >> "$LOG"
RC=0
if ! python3 -m plm_intake.health preflight >> "$LOG" 2>&1; then
  echo "=== Abbruch: Vorabpruefung (Exit 3) ===" >> "$LOG"; RC=3
  python3 -m plm_intake.tagesbericht 3 "$MODE" >> "$LOG" 2>&1   # Tagesbericht auch beim Abbruch (Job-Summary)
else
  if [ "$MODE" = "apply" ]; then python3 -m plm_intake.auto_run --apply >> "$LOG" 2>&1; else python3 -m plm_intake.auto_run >> "$LOG" 2>&1; fi
  RC=$?
  echo "=== Ende (Exit $RC) ===" >> "$LOG"
  cp output/intake/auto_report.md "output/intake/logs/report_$(date -u +%Y%m%d_%H%M).md" 2>/dev/null
  python3 -m plm_intake.health finish "$RC" "$MODE" >> "$LOG" 2>&1
  if [ "$(date -u +%u)" = "7" ]; then python3 -m plm_intake.audit >> "$LOG" 2>&1; fi
fi
python3 -m plm_intake.cloud push "$STATE_DIR" >> "$LOG" 2>&1
tail -n 40 "$LOG"
exit $RC
