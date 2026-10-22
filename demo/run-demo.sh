#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
run_id="inv-demo-$(date -u +%Y%m%d-%H%M%S)"
env_file="${CAIRN_ENV_FILE:-.env}"

if [[ ! -f "$env_file" ]]; then
  printf 'ERROR: live credentials file not found: %s\n' "$env_file" >&2
  printf 'Set CAIRN_ENV_FILE to an uncommitted local env file.\n' >&2
  exit 2
fi

set -a
. "$env_file"
set +a
export CAIRN_ENV_FILE="$env_file"

echo "== Cairn live dynamic investigation: ${run_id} =="
python3 scripts/investigate.py \
  --source real-test-subject \
  --report-file real-test-subject/security-report.txt \
  --runtime python \
  --start-argv python3 app.py \
  --port 5002 \
  --investigation-id "${run_id}"

echo
echo "== Markdown report =="
python3 - "${run_id}" <<'PY'
import json
import sys
from pathlib import Path

run_id = sys.argv[1]
report = json.loads(
    (Path("reports/investigations") / f"{run_id}.json").read_text(encoding="utf-8")
)
evidence = report["evidence"]
print(f"verdict={report['verdict']}")
print(f"route={evidence.get('request', {}).get('path')}")
print(f"parameter={evidence.get('request', {}).get('param_name')}")
print(f"attempts={len(evidence.get('attempts', []))}")
print(f"independent_recheck={evidence.get('independent_recheck')}")
print(f"sandbox_deleted={report['lifecycle'].get('sandbox_deleted')}")
PY

echo
echo "== Remaining Celesto Cloud guests (should be empty) =="
celesto computer list --cloud --json
