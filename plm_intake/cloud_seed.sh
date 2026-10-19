#!/usr/bin/env bash
# EINMALIG auf dem Mac: bisherigen Zustand (Merkbuch, Aliase, Klaerfaelle-Tabelle ...) in den Zweig einpflege-zustand des GitHub-Repos legen,
# damit der erste Cloud-Lauf nicht alles als "neu" behandelt. Pusht NUR diesen Zweig (nicht main). Voraussetzung: Remote "origin" ist das private Repo.
set -euo pipefail
cd "$(dirname "$0")/.."
REMOTE="$(git remote get-url origin)"
D="$(mktemp -d)"
python3 -m plm_intake.cloud push "$D"
cd "$D"
git init -q -b einpflege-zustand
git add -A
git -c user.name="plm-einpflege-bot" -c user.email="plm-einpflege-bot@users.noreply.github.com" commit -q -m "Start-Zustand vom Mac"
git remote add origin "$REMOTE"
git push origin einpflege-zustand
echo "Fertig: Zweig einpflege-zustand angelegt."
