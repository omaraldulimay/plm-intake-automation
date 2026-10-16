#!/bin/zsh
# Nachtlauf: wartet bis die laufende Batch-Kette fertig ist, prueft alle EANs, legt dann neue Produkte aus Plenty (Einkaufsbestellung in den letzten 12 Monaten) in Batches an
# und bearbeitet jeden Batch mit Farbvarianten -> EAN/SKU -> HS-Code. Jeder Schritt liest zurueck; bei Abweichung STOPP.
# Ablauf: erst ein kleiner Test-Batch (3 Produkte), nur bei Erfolg weiter mit Batches zu je 10 Styles (neue Styles haben oft 20-30 Farben).
#   ./plm_intake/overnight.sh            (im Terminal starten und das Fenster offen lassen; Mac bleibt dank caffeinate wach)
# Protokoll: output/overnight.log, Ergebnis: output/overnight_summary.md. Nie loeschen, nie ueberschreiben. Abbruch jederzeit mit Ctrl+C (alle Schritte sind wiederholbar).
cd "$(dirname "$0")/.." || exit 1
caffeinate -dimsu -w $$ &    # Mac bleibt wach, solange das Skript laeuft
export PLM_MAX_VARIANTS=500 PLM_MAX_ROWS=4000   # neue Styles haben viele Farben: Sicherheitsgrenzen fuer diesen Lauf hoeher (Standard 40 / 600)
LOG=output/overnight.log
say_() { echo "$(date '+%d.%m. %H:%M') $*" | tee -a "$LOG"; }
stop_() { say_ "STOPP: $*"; echo "STOPP: $* ($(date '+%H:%M'))" > output/overnight_summary.md; exit 2; }
bad_() { grep -qE "ABWEICH|FEHLT:|ACHTUNG|ABBRUCH|FEHLER|fatal" "$1"; }
say_ "Nachtlauf gestartet, warte auf die laufende Kette"
while pgrep -f "batch_chain.sh|plm_intake\.(variants|barcodes|packaging|plenty_new|ean_audit)" > /dev/null; do sleep 20; done
python3 -m plm_intake.ean_audit > /tmp/on_audit.txt 2>&1; say_ "EAN-Gesamtpruefung vorher: $(sed -n 3p /tmp/on_audit.txt)"
BASE=$(sed -n 3p /tmp/on_audit.txt | sed -n 's/.*FALSCH: \([0-9]*\).*/\1/p'); BASE=${BASE:-0}   # bekannte falsche Zellen (z. B. 26385) loesen keinen Stopp aus, nur NEUE
steps() {   # $1 = kommagetrennte SKUs
  for step in variants barcodes packaging; do
    extra=""; [ "$step" = "barcodes" ] && extra="--fast"
    python3 -m plm_intake.$step --skus "$1" --n 100 $extra --apply > /tmp/on_$step.txt 2>&1 || stop_ "$step abgebrochen (Exit)"
    say_ "  $step: $(grep -E 'Gesamt|Zu schreiben' /tmp/on_$step.txt | head -1)"
    bad_ /tmp/on_$step.txt && stop_ "Abweichung in $step (siehe output/*/plan_*.md)"
  done
}
batch() {   # $1 = Anzahl Styles
  python3 -m plm_intake.plenty_new --n "$1" --apply > /tmp/on_new.txt 2>&1 || stop_ "plenty_new abgebrochen (Exit)"
  say_ "Neu: $(grep -E 'dieser Batch' /tmp/on_new.txt | head -1 | sed 's/.*dieser Batch/dieser Batch/')"
  bad_ /tmp/on_new.txt && stop_ "Abweichung bei der Anlage (siehe output/plenty_new/plan_*.md)"
  grep -q "dieser Batch: 0" /tmp/on_new.txt && return 1
  SK=$(python3 -c "import json;print(','.join(json.load(open('output/plenty_new/last_created.json'))))")
  [ -z "$SK" ] && stop_ "keine Produkte angelegt"
  steps "$SK"
  return 0
}
say_ "Test-Batch (3 Produkte)"; batch 3 || stop_ "keine Kandidaten"
say_ "Test-Batch ok, starte Batches zu je 10"
i=0
while [ $i -lt 80 ]; do
  i=$((i+1)); say_ "Batch $i"
  batch 10 || { say_ "keine weiteren Kandidaten"; break; }
  if [ $((i % 6)) -eq 0 ]; then python3 -m plm_intake.ean_audit > /tmp/on_audit.txt 2>&1; say_ "EAN-Pruefung: $(sed -n 3p /tmp/on_audit.txt)"; NOW=$(sed -n 3p /tmp/on_audit.txt | sed -n 's/.*FALSCH: \([0-9]*\).*/\1/p'); [ "${NOW:-0}" -gt "$BASE" ] && stop_ "EAN-Pruefung meldet NEUE falsche Zellen ($NOW statt $BASE)"; fi
done
python3 -m plm_intake.ean_audit > /tmp/on_audit.txt 2>&1
{ echo "# Nachtlauf fertig $(date '+%d.%m. %H:%M')"; echo; echo "Batches: $i"; echo "EAN-Gesamtpruefung: $(sed -n 3p /tmp/on_audit.txt)"; echo; echo "Details: output/overnight.log, output/plenty_new/, output/variants/, output/barcodes/, output/packaging/"; } > output/overnight_summary.md
say_ "fertig"
exit 0
