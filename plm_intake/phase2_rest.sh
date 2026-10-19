#!/bin/zsh
cd "/path/to/project Produktion"
source .venv/bin/activate
unset ANTHROPIC_API_KEY
args=()
for s in lieferant_u lieferant_h medico muevret $(python3 -c "import json;print(' '.join(json.load(open('output/phase2/lieferanten.json'))['batches'][6]))"); do args+=(--lieferant $s); done
caffeinate -i python3 -m plm_intake.phase2_chain "${args[@]}" >> output/phase2/nacht2.log 2>&1
echo "=== FERTIG $(date)" >> output/phase2/nacht2.log
python3 -m plm_intake.phase2_status --nr 26 --nr 44 --nr 45 --nr 60 --apply > output/phase2/status_apply.log 2>&1
echo "=== STATUS FERTIG $(date)" >> output/phase2/nacht2.log
