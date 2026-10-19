#!/bin/zsh
# Einmalig ausfuehren: richtet den Zeitplan fuer den PLM-Einpflege-Lauf ein (Mo-Fr 13:30 und 19:30, schreibt ins PLM).
#   ./plm_intake/launchd/install.sh            installieren/aktualisieren
#   ./plm_intake/launchd/install.sh test       sofort einen Lauf anstossen (zeigt, ob macOS den Zugriff erlaubt)
#   ./plm_intake/launchd/install.sh remove     Zeitplan entfernen
# VORAUSSETZUNG (einmal, nur du): Systemeinstellungen > Datenschutz & Sicherheit > Festplattenvollzugriff > "+" > /bin/zsh und /usr/bin/caffeinate hinzufuegen
#   (Cmd+Shift+G im Dateidialog, Pfad eintippen). Ohne das blockiert macOS den Zugriff auf Dokumente/Google Drive (genau daran ist der Job am 15.10. gescheitert).
LABEL=com.smilodox.plm-intake
SRC="$(cd "$(dirname "$0")" && pwd)/$LABEL.plist"
DST="$HOME/Library/LaunchAgents/$LABEL.plist"
case "$1" in
  remove) launchctl bootout gui/$UID "$DST" 2>/dev/null; rm -f "$DST"; echo "entfernt"; exit 0;;
  test) launchctl kickstart -k gui/$UID/$LABEL && echo "Lauf angestossen. Log: ~/Library/Logs/plm_intake.err und output/intake/logs/" ; exit $?;;
esac
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
launchctl bootout gui/$UID "$DST" 2>/dev/null
cp "$SRC" "$DST" && launchctl bootstrap gui/$UID "$DST" && launchctl enable gui/$UID/$LABEL && echo "eingerichtet: Mo-Fr 13:30 und 19:30" && launchctl print gui/$UID/$LABEL | grep -E "state|next" | head -3
echo "Testlauf wird angestossen ..."
launchctl kickstart -k gui/$UID/$LABEL && echo "Ergebnis in ca. 5-10 Min: cat output/intake/STATUS.md  (Fehler: ~/Library/Logs/plm_intake.err)"
echo
echo "Optional: Mac aufwecken (optional, braucht dein Passwort): sudo pmset repeat wakeorpoweron MTWRF 13:25:00"
