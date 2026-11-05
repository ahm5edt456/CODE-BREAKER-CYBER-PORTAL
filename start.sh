#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "$0")"
if [ -x .venv_portal/bin/python ]; then
  exec .venv_portal/bin/python main.py
fi
printf 'First install the new interface libraries: bash setup.sh\n'
exit 1
