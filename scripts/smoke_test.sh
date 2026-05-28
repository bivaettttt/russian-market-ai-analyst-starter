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
check_get "signals consumer data ml v2 gate" "/signals/consumer.json?limit=5&use_ml_v2_research_gate=true"
check_get "signals consumer data ml v2 soft gate" "/signals/consumer.json?limit=5&use_ml_v2_research_gate=true&ml_v2_gate_mode=soft_downgrade"
check_get "signals consumer search" "/signals/consumer.json?limit=5&q=SBER"
check_get "signals consumer ticker" "/signals/consumer/SBER.json"
check_get "signals consumer ticker SBER" "/signals/consumer/SBER.json"
check_get "signals consumer ticker SBER ml v2 gate" "/signals/consumer/SBER.json?use_ml_v2_research_gate=true"
check_get "signals consumer ticker SBER ml v2 diagnostic" "/signals/consumer/SBER.json?use_ml_v2_research_gate=true&ml_v2_gate_mode=diagnostic_only"
check_get "signals consumer ticker SBER ml v2 soft gate" "/signals/consumer/SBER.json?use_ml_v2_research_gate=true&ml_v2_gate_mode=soft_downgrade"
check_get "signals consumer ticker SBER event risk overlay" "/signals/consumer/SBER.json?use_event_risk_overlay=true&event_risk_overlay_mode=diagnostic_only"
check_get "signals consumer ticker SBER conservative overlay" "/signals/consumer/SBER.json?use_conservative_event_overlay=true"
check_get "signals consumer ml v2 gate compare" "/signals/consumer/ml-v2-gate-compare?limit=5&ml_v2_gate_mode=soft_downgrade"
check_get "signals consumer event risk overlay compare" "/signals/consumer/event-risk-overlay-compare?limit=5&event_risk_overlay_mode=soft_adjust"
check_get "signals consumer ml v2 gate backtest" "/signals/consumer/ml-v2-gate-backtest?max_tickers=5&max_samples=300&min_signals=10&folds=2"
check_get "signals consumer ml v2 gate backtest page" "/signals/consumer/ml-v2-gate-backtest-page"
check_get "signals consumer long" "/signals/consumer.json?limit=20&scenario=long"
check_get "signals consumer downside" "/signals/consumer.json?limit=20&scenario=downside"
check_get "signals consumer all with events" "/signals/consumer.json?limit=20&scenario=all&news=with_events"
check_get "signals consumer list event risk overlay" "/signals/consumer.json?limit=5&use_event_risk_overlay=true&event_risk_overlay_mode=soft_adjust"
check_get "signals consumer list conservative overlay" "/signals/consumer.json?limit=5&use_conservative_event_overlay=true"
check_get "signals market regime" "/signals/market-regime"
check_get "signals ml v2 dataset summary" "/signals/ml-v2/dataset-summary?max_tickers=5&max_samples=200"
check_get "signals ml v2 evaluation" "/signals/ml-v2/evaluation?max_tickers=5&max_samples=200"
check_get "signals ml v2 report page" "/signals/ml-v2/report-page"
check_get "signals ml v2 high confidence validation" "/signals/ml-v2/high-confidence-validation?max_tickers=5&max_samples=300&folds=2&min_train_samples=100&min_test_samples=50"
check_get "signals ml v2 high confidence page" "/signals/ml-v2/high-confidence-page"
check_get "signals ml v2 gate impact" "/signals/ml-v2/gate-impact?max_tickers=5&max_samples=300&min_signals=10"
check_get "signals ml v2 gate impact page" "/signals/ml-v2/gate-impact-page"
check_get "signals ml v2 gate walk forward" "/signals/ml-v2/gate-walk-forward?max_tickers=5&max_samples=300&folds=2&min_train_samples=100&min_test_samples=50&min_signals=10"
check_get "signals ml v2 gate walk forward page" "/signals/ml-v2/gate-walk-forward-page"
check_get "signals ml v3 consumer candidate dataset" "/signals/ml-v3/consumer-candidate/dataset-summary?max_tickers=5&max_samples=200"
check_get "signals ml v3 consumer candidate evaluation" "/signals/ml-v3/consumer-candidate/evaluation?max_tickers=5&max_samples=200"
check_get "signals ml v3 consumer candidate walk forward" "/signals/ml-v3/consumer-candidate/walk-forward?max_tickers=5&max_samples=300&folds=2&min_train_samples=50&min_test_samples=30&min_signals=10"
check_get "signals ml v3 consumer candidate page" "/signals/ml-v3/consumer-candidate/page"
check_get "signals setup family research" "/signals/setup-family/research?max_tickers=5&max_samples=200&min_signals=5"
check_get "signals setup family sweep" "/signals/setup-family/sweep?max_tickers=5&max_samples=200&max_configs=10&min_signals=5"
check_get "signals setup family research page" "/signals/setup-family/research-page"
check_get "signals event coverage" "/signals/events/coverage?max_events=100"
check_get "signals event coverage full" "/signals/events/coverage?max_events=10000"
check_get "signals event bootstrap status" "/signals/events/bootstrap-status"
check_get "signals event aware research" "/signals/event-aware/research?max_tickers=5&max_samples=200&max_events=100&min_signals=5"
check_get "signals event aware sweep" "/signals/event-aware/sweep?max_tickers=5&max_samples=200&max_events=100&max_configs=10&min_signals=5"
check_get "signals event aware research page" "/signals/event-aware/research-page"
check_get "signals event aware walk forward" "/signals/event-aware/walk-forward?max_tickers=5&max_samples=200&max_events=200&folds=2&min_train_samples=20&min_test_samples=10&min_signals=2&top_k_combos=3"
check_get "signals event aware walk forward page" "/signals/event-aware/walk-forward-page"
check_get "signals event aware rule search" "/signals/event-aware/rule-search?max_tickers=5&max_samples=200&max_events=200&folds=2&min_train_samples=20&min_test_samples=10&min_signals=2&max_rules=30&top_k_rules=3"
check_get "signals event aware rule search page" "/signals/event-aware/rule-search-page"
check_get "signals event aware dual side research" "/signals/event-aware/dual-side-research?max_tickers=5&max_samples=200&max_events=200&min_signals=2&max_rules=30"
check_get "signals event aware dual side walk forward" "/signals/event-aware/dual-side-walk-forward?max_tickers=5&max_samples=200&max_events=200&folds=2&min_train_samples=20&min_test_samples=10&min_signals=2&max_rules=30&top_k_rules=3"
check_get "signals event aware dual side page" "/signals/event-aware/dual-side-page"
check_get "signals event aware rule stability" "/signals/event-aware/rule-stability?max_tickers=5&max_samples=200&max_events=200&min_signals=2&max_rules=30"
check_get "signals event aware rule stability page" "/signals/event-aware/rule-stability-page"
check_get "signals event aware risk overlay backtest" "/signals/event-aware/risk-overlay-backtest?max_tickers=5&max_samples=200&max_events=200"
check_get "signals event aware risk overlay page" "/signals/event-aware/risk-overlay-page"
check_get "signals event aware risk overlay walk forward" "/signals/event-aware/risk-overlay-walk-forward?max_tickers=5&max_samples=200&max_events=200&folds=2&min_train_samples=20&min_test_samples=10&max_configs=10"
check_get "signals event aware risk overlay walk forward page" "/signals/event-aware/risk-overlay-walk-forward-page"
check_get "signals event aware conservative overlay calibration" "/signals/event-aware/risk-overlay-conservative-calibration?max_tickers=5&max_samples=200&max_events=200&folds=2&min_train_samples=20&min_test_samples=10&max_configs=10"
check_get "signals event aware conservative overlay page" "/signals/event-aware/risk-overlay-conservative-page"
check_get "signals event aware conservative overlay paper snapshot" "/signals/event-aware/conservative-overlay-paper-snapshot?limit=5"
check_get "signals event aware conservative overlay paper page" "/signals/event-aware/conservative-overlay-paper-page"
check_get "signals event aware conservative overlay paper dashboard" "/signals/event-aware/conservative-overlay-paper-dashboard?limit=5"
check_get "signals event aware conservative overlay paper lifecycle status" "/signals/event-aware/conservative-overlay-paper-lifecycle-status"
check_get "signals event aware conservative overlay paper ready" "/signals/event-aware/conservative-overlay-paper-ready?limit=5"
check_get "signals event aware conservative overlay paper snapshots csv" "/signals/event-aware/conservative-overlay-paper-snapshots.csv?limit=5"
check_get "signals event aware conservative overlay paper dashboard csv" "/signals/event-aware/conservative-overlay-paper-dashboard.csv"
check_get "signals event aware conservative overlay paper tracking page" "/signals/event-aware/conservative-overlay-paper-tracking-page"
check_get "signals event aware conservative overlay quality report" "/signals/event-aware/conservative-overlay-quality-report?limit=10"
check_get "signals event aware conservative overlay notification summary" "/signals/event-aware/conservative-overlay-notification-summary?limit=10"
check_get "signals event aware conservative overlay data health" "/signals/event-aware/conservative-overlay-data-health"
check_get "signals event aware conservative overlay quality report csv" "/signals/event-aware/conservative-overlay-quality-report.csv?limit=10"
check_get "signals event aware conservative overlay quality report page" "/signals/event-aware/conservative-overlay-quality-report-page"
check_get "signals daily ops status" "/signals/daily-ops/status"
check_get "signals daily ops market data freshness" "/signals/daily-ops/market-data-freshness"
check_get "signals daily ops page" "/signals/daily-ops/page"
check_post_json "signals daily ops dry run" "/signals/daily-ops/run?dry_run=true&refresh_market_data=false&limit=5" "{}"
check_get "signals daily ops market refresh report" "/signals/daily-ops/market-refresh-report"
check_get "signals daily ops market refresh notification" "/signals/daily-ops/market-refresh-notification"
check_get "signals daily ops market refresh report csv" "/signals/daily-ops/market-refresh-report.csv"
check_get "signals daily ops market refresh report page" "/signals/daily-ops/market-refresh-report-page"
check_get "signals live paper validation status" "/signals/live-paper-validation/status"
check_get "signals live paper validation page" "/signals/live-paper-validation/page"
check_post_json "signals live paper validation dry run" "/signals/live-paper-validation/start?dry_run=true&refresh_market_data=false&require_fresh_market_data=false&limit=5" "{}"
check_get "signals data coverage" "/signals/data-coverage?max_tickers=100&min_history=80&horizon=20"
check_get "signals data coverage page" "/signals/data-coverage-page"
check_get "signals data bootstrap status" "/signals/data-bootstrap-status"
check_get "signals consumer backtest audit" "/signals/consumer/backtest-audit?max_tickers=5&max_samples=100"
check_get "signals consumer backtest audit page" "/signals/consumer/backtest-audit-page"
check_get "signals consumer threshold sweep" "/signals/consumer/threshold-sweep?max_tickers=5&max_samples=120&max_configs=20"
check_get "signals consumer threshold sweep page" "/signals/consumer/threshold-sweep-page"
check_get "signals consumer walk forward" "/signals/consumer/walk-forward?max_tickers=5&max_samples=200&max_configs=20&folds=2"
check_get "signals consumer walk forward page" "/signals/consumer/walk-forward-page"
check_get "signals consumer regime historical evaluation" "/signals/consumer/regime-historical-evaluation?max_tickers=5&max_samples=120"
check_get "signals consumer regime historical evaluation page" "/signals/consumer/regime-historical-evaluation-page"
check_get "signals consumer regime formula calibration" "/signals/consumer/regime-formula-calibration?max_tickers=5&max_samples=120&max_configs=20"
check_get "signals consumer regime formula calibration page" "/signals/consumer/regime-formula-calibration-page"
check_get "signals consumer adaptive trade calibration" "/signals/consumer/adaptive-trade-calibration?max_tickers=5&max_samples=120&max_policies=20"
check_get "signals consumer adaptive trade calibration page" "/signals/consumer/adaptive-trade-calibration-page"
check_get "signals consumer expectancy breakdown" "/signals/consumer/expectancy-breakdown?max_tickers=5&max_samples=120"
check_get "signals consumer expectancy breakdown page" "/signals/consumer/expectancy-breakdown-page"
check_get "signals consumer candidate filter calibration" "/signals/consumer/candidate-filter-calibration?max_tickers=5&max_samples=120&max_filters=20"
check_get "signals consumer candidate filter calibration page" "/signals/consumer/candidate-filter-calibration-page"
check_get "signals consumer composite rule calibration" "/signals/consumer/composite-rule-calibration?max_tickers=5&max_samples=120&max_rules=20"
check_get "signals consumer composite rule calibration page" "/signals/consumer/composite-rule-calibration-page"
check_get "signals consumer adaptive trade calibration costs" "/signals/consumer/adaptive-trade-calibration?max_tickers=5&max_samples=120&max_policies=20&commission_bps=10&slippage_bps=5"
check_get "signals consumer expectancy breakdown costs" "/signals/consumer/expectancy-breakdown?max_tickers=5&max_samples=120&commission_bps=10&slippage_bps=5"
check_get "signals consumer backtest audit costs" "/signals/consumer/backtest-audit?max_tickers=5&max_samples=100&commission_bps=10&slippage_bps=5"
check_get "signals consumer threshold sweep costs" "/signals/consumer/threshold-sweep?max_tickers=5&max_samples=120&max_configs=20&commission_bps=10&slippage_bps=5"
check_get "signals consumer walk forward costs" "/signals/consumer/walk-forward?max_tickers=5&max_samples=200&max_configs=20&folds=2&commission_bps=10&slippage_bps=5"
check_get "signals consumer backtest audit regime filter" "/signals/consumer/backtest-audit?max_tickers=5&max_samples=120&use_market_regime_filter=true"
check_get "signals consumer threshold sweep regime filter" "/signals/consumer/threshold-sweep?max_tickers=5&max_samples=120&max_configs=20&use_market_regime_filter=true"
check_get "signals consumer walk forward regime filter" "/signals/consumer/walk-forward?max_tickers=5&max_samples=200&max_configs=20&folds=2&use_market_regime_filter=true"
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
