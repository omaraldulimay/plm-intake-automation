#!/bin/zsh
# Einmal-Lauf: verarbeitet alles, was seit dem letzten Lauf in der Inbox aufgelaufen ist (Trockenlauf, schreibt NICHTS ins PLM).
#   ./plm_intake/nachholen.sh            # Trockenlauf + Status
#   ./plm_intake/nachholen.sh apply      # nur nach Freigabe: schreibt ins PLM (Limits: 3 neue POs, 8 neue Produkte pro Lauf)
# Voraussetzung: Mac an, Google Drive fuer Desktop gestartet, PLM-Browser eingeloggt (sonst bricht die Vorabpruefung mit Warnung ab).
cd "$(dirname "$0")/.." || exit 1
PLM_MODE=$([ "$1" = "apply" ] && echo apply || echo dry) ./plm_intake/scheduled_run.sh
RC=$?
echo; cat output/intake/STATUS.md; echo; echo "Bericht: output/intake/auto_report.md"
exit $RC
