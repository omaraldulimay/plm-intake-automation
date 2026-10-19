#!/bin/zsh
# Nachtlauf Phase 2: Batches 1-7 nacheinander (je Lieferant komplett, Trockenlauf + Schreiben + Ruecklesung). Log: output/phase2/nacht.log
cd "/path/to/project Produktion"
source .venv/bin/activate
unset ANTHROPIC_API_KEY
for b in 1 2 3 4 5 6 7; do
  echo "=== Batch $b $(date)" >> output/phase2/nacht.log
  caffeinate -i python3 -m plm_intake.phase2_chain --batch $b >> output/phase2/nacht.log 2>&1
done
echo "=== FERTIG $(date)" >> output/phase2/nacht.log
