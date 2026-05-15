#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

ok_count=0

check_get() {
  local name="$1"
  local path="$2"

  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}${path}")"

  if [[ "$code" != "200" ]]; then
    echo "FAIL GET ${name}: ${code} ${path}"
    exit 1
  fi

  echo "OK   GET ${name}: ${code}"
  ok_count=$((ok_count + 1))
}

check_post_json() {
  local name="$1"
  local path="$2"
  local payload="$3"

  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -d "$payload")"

  if [[ "$code" != "200" ]]; then
    echo "FAIL POST ${name}: ${code} ${path}"
    exit 1
  fi

  echo "OK   POST ${name}: ${code}"
  ok_count=$((ok_count + 1))
}

create_snapshot() {
  local quality_mode="$1"

  curl -fsS \
    -X POST "${BASE_URL}/portfolio/construct/snapshot" \
    -H "Content-Type: application/json" \
    -d "{\"budget\":100000,\"risk_profile\":\"balanced\",\"horizon\":\"medium\",\"quality_mode\":\"${quality_mode}\"}" \
    | python3 -c 'import json,sys; data=json.load(sys.stdin); print((data.get("snapshot") or {}).get("id") or "")'
}

echo "Smoke test base URL: ${BASE_URL}"
echo

check_get "dashboard" "/dashboard"
check_get "signals" "/signals"
check_get "signals champion" "/signals/champion"
check_get "portfolio constructor" "/portfolio/construct/demo"
check_get "portfolio history" "/portfolio/construct/history"
check_get "portfolio snapshots latest" "/portfolio/construct/snapshots/latest"
check_get "portfolio snapshots stats" "/portfolio/construct/snapshots/stats"
check_get "portfolio snapshots csv" "/portfolio/construct/snapshots.csv?limit=20"
check_get "AI report page" "/ai/report/demo"
check_get "AI reports list" "/ai/reports"

check_post_json "portfolio construct" "/portfolio/construct" \
  '{"budget":100000,"risk_profile":"balanced","horizon":"medium","quality_mode":"normal"}'

check_post_json "portfolio csv" "/portfolio/construct.csv" \
  '{"budget":100000,"risk_profile":"balanced","horizon":"medium","quality_mode":"strict"}'

echo
echo "Creating test snapshots..."
normal_id="$(create_snapshot normal)"
strict_id="$(create_snapshot strict)"

echo "normal snapshot id: ${normal_id}"
echo "strict snapshot id: ${strict_id}"

if [[ -n "$normal_id" ]]; then
  check_get "snapshot detail view" "/portfolio/construct/snapshots/${normal_id}/view"
fi

check_get "portfolio compare latest" "/portfolio/construct/compare"
check_get "portfolio compare latest json" "/portfolio/construct/compare.json"
check_get "portfolio compare latest csv" "/portfolio/construct/compare.csv"

if [[ -n "$normal_id" && -n "$strict_id" && "$normal_id" != "$strict_id" ]]; then
  check_get "portfolio compare selected" "/portfolio/construct/compare?left_id=${normal_id}&right_id=${strict_id}"
  check_get "portfolio compare selected json" "/portfolio/construct/compare.json?left_id=${normal_id}&right_id=${strict_id}"
  check_get "portfolio compare selected csv" "/portfolio/construct/compare.csv?left_id=${normal_id}&right_id=${strict_id}"
fi

echo
echo "Smoke test passed: ${ok_count} checks"
