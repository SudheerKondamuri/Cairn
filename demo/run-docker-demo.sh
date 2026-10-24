#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  printf 'ERROR: .env is required for the local Docker demo and is ignored by Git.\n' >&2
  exit 2
fi

set -a
. ./.env
set +a

api_headers=()
if [[ "${CAIRN_REQUIRE_API_AUTH:-false}" == "true" || -n "${CAIRN_API_KEY:-}" ]]; then
  if [[ -z "${CAIRN_API_KEY:-}" || "${CAIRN_API_KEY}" == "replace-me" ]]; then
    printf 'ERROR: API authentication is enabled but CAIRN_API_KEY is not configured.\n' >&2
    exit 2
  fi
  api_headers=(-H "X-Cairn-API-Key: ${CAIRN_API_KEY}")
fi

command -v docker >/dev/null 2>&1 || {
  printf 'ERROR: Docker is not installed or is not on PATH.\n' >&2
  exit 2
}
docker compose version >/dev/null 2>&1 || {
  printf 'ERROR: Docker Compose is not available.\n' >&2
  exit 2
}

archive="$(mktemp /tmp/cairn-northstar-XXXXXX.tar.gz)"
trap 'rm -f "$archive"' EXIT

echo "== Start Cairn API, Postgres ledger, and worker containers =="
docker compose --profile worker up --build -d

echo "== Wait for the trusted control plane =="
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8080/ready >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8080/ready

tar -czf "$archive" -C demo-subject .
manifest='{"subject_type":"http_app","runtime":"python","start_argv":["python3","app.py"],"port":5002,"working_directory":".","dependency_mode":"offline"}'

echo
echo "== Queue Northstar diagnostics investigation through the API =="
response="$(curl -fsS \
  "${api_headers[@]}" \
  -F "source=@${archive}" \
  -F "report=<demo-subject/security-report.txt" \
  -F "manifest=${manifest}" \
  http://localhost:8080/api/investigations)"
printf '%s\n' "$response"
investigation_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["investigation_id"])' <<<"$response")"

echo
echo "== Poll the Postgres-backed investigation job =="
final=""
for _ in $(seq 1 90); do
  final="$(curl -fsS "${api_headers[@]}" "http://localhost:8080/api/investigations/${investigation_id}")"
  status="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$final")"
  printf 'status=%s\n' "$status"
  if [[ "$status" == "completed" || "$status" == "failed" ]]; then
    break
  fi
  sleep 2
done

if [[ "$status" != "completed" && "$status" != "failed" ]]; then
  printf 'ERROR: investigation did not finish; last status=%s\n' "$status" >&2
  docker compose logs --tail=100 worker >&2 || true
  exit 1
fi

python3 - "$final" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
print(f"investigation_id={payload['investigation_id']}")
print(f"status={payload['status']}")
if payload.get("status") == "failed":
    raise SystemExit(payload.get("error") or "worker failed")
result = payload.get("result") or {}
recheck = evidence.get("independent_recheck") or {}
lifecycle = result.get("lifecycle") or {}
request = evidence.get("request") or {}
print(f"verdict={result.get('verdict')}")
print(f"route={request.get('path')}")
print(f"parameter={request.get('param_name')}")
print(f"independent_recheck={recheck.get('marker_detected')}")
print(f"sandbox_name={lifecycle.get('sandbox_name')}")
print(f"sandbox_deleted={lifecycle.get('sandbox_deleted')}")
PY

echo
echo "== Host report written by the worker =="
printf '%s\n' "reports/investigations/${investigation_id}.md"
echo
echo "Docker services remain running for inspection. After recording, run:"
echo "docker compose --profile worker down"
