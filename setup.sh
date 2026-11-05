#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "$0")"
python3 -m venv .venv_portal
.venv_portal/bin/python -m pip install -r requirements.txt
printf '\nReady. Start the game with: bash start.sh\n'
