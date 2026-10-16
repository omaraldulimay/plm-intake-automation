#!/bin/zsh
# Bearbeitet die echten PLM-Produkte (neu -> alt) in Batches: Varianten -> EAN/SKU -> HS-Code. Jeder Schritt ist idempotent und liest zurueck.
#   ./plm_intake/batch_chain.sh <offset> [n]     z. B. ./plm_intake/batch_chain.sh 0 25
# Stoppt bei Fehler. Berichte: output/variants, output/barcodes, output/packaging, Zusammenfassung: output/batch_chain.log
cd "$(dirname "$0")/.." || exit 1
OFF="${1:-0}"; N="${2:-25}"
echo "=== Batch offset $OFF n $N $(date +%H:%M) ===" | tee -a output/batch_chain.log
for step in variants barcodes packaging; do
  python3 -m plm_intake.$step --all --offset "$OFF" --n "$N" --apply > "/tmp/chain_${step}.txt" 2>&1 || { echo "FEHLER in $step" | tee -a output/batch_chain.log; tail -5 "/tmp/chain_${step}.txt"; exit 1; }
  echo "-- $step: $(grep -E 'Gesamt|Zu schreiben' /tmp/chain_${step}.txt | head -1) | $(grep -E 'ALLES|alle Varianten|ABWEICH|FEHLT|ACHTUNG|ABBRUCH' /tmp/chain_${step}.txt | head -2 | tr '\n' ' ')" | tee -a output/batch_chain.log
  grep -qE "ABWEICH|FEHLT:|ACHTUNG|ABBRUCH" "/tmp/chain_${step}.txt" && { echo "STOPP wegen Abweichung in $step" | tee -a output/batch_chain.log; exit 2; }
done
exit 0
