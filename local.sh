#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export PATH="$PWD/tools/bin:$PATH"
python_bin=python3
if [ -x .venv_portal/bin/python ]; then
  python_bin="$PWD/.venv_portal/bin/python"
fi
exec "$python_bin" "$PWD/local_runtime.py" "${1:-play}"
