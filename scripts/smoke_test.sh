#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
CLEANUP_SMOKE_SNAPSHOTS="${CLEANUP_SMOKE_SNAPSHOTS:-1}"

ok_count=0
created_snapshot_ids=()

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
    | python3 -c 'import json,sys; data=json.load(sys.stdin); snapshot=data.get("snapshot") or {}; print("{}|{}|{}".format(snapshot.get("id") or "", str(bool(data.get("created"))).lower(), str(bool(data.get("duplicate"))).lower()))'
}

remember_created_snapshot() {
  local snapshot_id="$1"
  local created="$2"

  if [[ -n "$snapshot_id" && "$created" == "true" ]]; then
    created_snapshot_ids+=("$snapshot_id")
  fi
}

cleanup_created_snapshots() {
  if [[ "$CLEANUP_SMOKE_SNAPSHOTS" == "0" ]]; then
    return
  fi

  if [[ "${#created_snapshot_ids[@]}" -eq 0 ]]; then
    return
  fi

  echo
  echo "Cleaning up smoke-test snapshots..."

  for snapshot_id in "${created_snapshot_ids[@]}"; do
    if [[ -z "$snapshot_id" ]]; then
      continue
    fi

    local code
    code="$(curl -s -o /dev/null -w "%{http_code}" \
      -X DELETE "${BASE_URL}/portfolio/construct/snapshots/${snapshot_id}")"

    if [[ "$code" == "200" || "$code" == "404" ]]; then
      echo "OK   DELETE smoke snapshot #${snapshot_id}: ${code}"
    else
      echo "WARN DELETE smoke snapshot #${snapshot_id}: ${code}"
    fi
  done
}

trap cleanup_created_snapshots EXIT

echo "Smoke test base URL: ${BASE_URL}"
echo

check_get "dashboard" "/dashboard"
check_get "signals" "/signals"
check_get "signals consumer data" "/signals/consumer.json?limit=5"
check_get "signals consumer search" "/signals/consumer.json?limit=5&q=SBER"
check_get "signals consumer ticker" "/signals/consumer/SBER.json"
check_get "signals consumer ticker SBER" "/signals/consumer/SBER.json"
check_get "signals consumer long" "/signals/consumer.json?limit=20&scenario=long"
check_get "signals consumer downside" "/signals/consumer.json?limit=20&scenario=downside"
check_get "signals consumer all with events" "/signals/consumer.json?limit=20&scenario=all&news=with_events"
check_get "signals market regime" "/signals/market-regime"
check_get "signals consumer backtest audit" "/signals/consumer/backtest-audit?max_tickers=5&max_samples=100"
check_get "signals consumer backtest audit page" "/signals/consumer/backtest-audit-page"
check_get "signals consumer threshold sweep" "/signals/consumer/threshold-sweep?max_tickers=5&max_samples=120&max_configs=20"
check_get "signals consumer threshold sweep page" "/signals/consumer/threshold-sweep-page"
check_get "signals consumer walk forward" "/signals/consumer/walk-forward?max_tickers=5&max_samples=200&max_configs=20&folds=2"
check_get "signals consumer walk forward page" "/signals/consumer/walk-forward-page"
check_get "ticker search" "/tickers/search?q=SBER&limit=5"
check_get "ticker universe" "/tickers/universe?limit=5"
check_get "ticker forecast page" "/tickers/SBER"
check_get "signals v4 data" "/signals/data?limit=5&model_version=tech_v4_quality_rr"
check_get "signals v4 backtest" "/signals/backtest.json?tickers=SBER,GAZP,LKOH,PLZL&limit=120&min_history=50&future_limit=20&max_points_per_ticker=10&model_version=tech_v4_quality_rr"
check_get "signals model quality" "/signals/models/quality"
check_get "signals model quality json" "/signals/models/quality.json?limit=20"
check_get "signals champion" "/signals/champion"
check_get "portfolio constructor" "/portfolio/construct/demo"
check_get "portfolio history" "/portfolio/construct/history"
check_get "portfolio snapshots latest" "/portfolio/construct/snapshots/latest"
check_get "portfolio snapshots stats" "/portfolio/construct/snapshots/stats"
check_get "portfolio snapshots csv" "/portfolio/construct/snapshots.csv?limit=20"
check_get "AI report page" "/ai/report/demo"
check_get "AI reports list" "/ai/reports"
check_get "AI reports dashboard" "/ai/reports/dashboard"
check_get "AI reports trends" "/ai/reports/trends"
check_get "AI reports trends json" "/ai/reports/trends.json"
check_get "AI reports trends csv" "/ai/reports/trends.csv"

check_post_json "portfolio construct" "/portfolio/construct" \
  '{"budget":100000,"risk_profile":"balanced","horizon":"medium","quality_mode":"normal"}'

check_post_json "portfolio csv" "/portfolio/construct.csv" \
  '{"budget":100000,"risk_profile":"balanced","horizon":"medium","quality_mode":"strict"}'

echo
echo "Creating test snapshots..."
normal_result="$(create_snapshot normal)"
strict_result="$(create_snapshot strict)"

IFS='|' read -r normal_id normal_created normal_duplicate <<< "$normal_result"
IFS='|' read -r strict_id strict_created strict_duplicate <<< "$strict_result"

remember_created_snapshot "$normal_id" "$normal_created"
remember_created_snapshot "$strict_id" "$strict_created"

echo "normal snapshot id: ${normal_id} (created=${normal_created}, duplicate=${normal_duplicate})"
echo "strict snapshot id: ${strict_id} (created=${strict_created}, duplicate=${strict_duplicate})"

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
else
  echo "SKIP selected compare: need two distinct snapshot IDs"
fi

echo
echo "Smoke test passed: ${ok_count} checks"
