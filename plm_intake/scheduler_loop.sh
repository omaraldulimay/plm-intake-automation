#!/bin/zsh
# Variante ohne Systemeinstellungen: in einem Terminal-Fenster starten und offen lassen (Terminal hat Zugriff auf Dokumente).
#   PLM_MODE=dry ./plm_intake/scheduler_loop.sh      # nur berichten (Standard)
#   PLM_MODE=apply ./plm_intake/scheduler_loop.sh    # schreibt ins PLM
# Laeuft taeglich um 08:00 und 13:30 (lokale Zeit) plm_intake/scheduled_run.sh. Mac darf nicht schlafen (caffeinate wird mitgestartet).
cd "$(dirname "$0")/.." || exit 1
caffeinate -i -w $$ &
HOURS=("08:00" "13:30")
last=""
while true; do
  now=$(date +%H:%M); day=$(date +%Y%m%d)
  for t in "${HOURS[@]}"; do
    if [ "$now" = "$t" ] && [ "$last" != "$day$t" ]; then
      last="$day$t"; echo "$(date) Lauf $t"; ./plm_intake/scheduled_run.sh
    fi
  done
  sleep 20
done
