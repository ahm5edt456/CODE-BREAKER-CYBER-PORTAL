#!/usr/bin/env bash
set -euo pipefail
# Regression assertions must not disappear due to inherited Python settings.
unset PYTHONOPTIMIZE PYTHONPATH PYTHONHOME
cd -- "$(dirname -- "$0")"
export PATH="$PWD/tools/bin:$PATH"
python_bin="${PYTHON:-python3}"
for tool in g++ java javac; do
  command -v "$tool" >/dev/null || { printf 'Required tool unavailable: %s\n' "$tool" >&2; exit 1; }
done
javac -version
"$python_bin" -u test_local_runtime.py
"$python_bin" -u test_security_review.py
"$python_bin" -u test_environment_sanitization.py
"$python_bin" -u test_cpp_toolchain.py
"$python_bin" -u test_runner_security.py
"$python_bin" - <<'PYTHON'
from execution_isolation import isolation_error
error = isolation_error()
if error:
    print(error)
    print('BLOCKED: language execution regressions require functioning isolation; no unsafe fallback.')
    raise SystemExit(2)
PYTHON
"$python_bin" -u verify_playability.py
for suite in test_language_regressions.py test_round_rotation.py test_game.py test_campaign.py test_requested_updates.py test_portal.py test_speed_scores.py test_score_store.py; do
  printf '\nRunning %s\n' "$suite"
  "$python_bin" -u "$suite"
done
