from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import (
    aggregate_trade_pnl_metrics,
    compute_trade_setup,
    simulate_trade_outcome,
)
from app.services.consumer_signal_backtest_audit import _build_proxy_samples
from app.services.consumer_signals import _round, _to_float
from app.services.expectancy_breakdown import (
    DIMENSIONS,
    build_bucket_row,
    extract_sample_segments,
)


BEST_ADAPTIVE_POLICY: dict[str, Any] = {
    "policy_type": "atr_multiple",
    "target_atr_mult": 1.5,
    "stop_atr_mult": 1.6,
    "horizon": 30,
    "min_rr": 0.8,
}

FILTER_DIMENSIONS = [
    "ticker",
    "action",
    "market_regime",
    "volatility_bucket",
    "liquidity_bucket",
    "probability_bucket",
    "ml_probability_bucket",
    "rr_bucket",
    "audit_confidence",
    "news_effect",
    "macro_effect",
    "sector",
    "asset_type",
]


def _sample_value(sample: dict[str, Any], dimension: str) -> Any:
    segments = sample.get("segments")
    if not isinstance(segments, dict):
        segments = extract_sample_segments(sample)
    return segments.get(dimension, "unknown")


def _value_matches(actual: Any, op: str, expected: Any) -> bool:
    actual_values = actual if isinstance(actual, list) else [actual]
    actual_text = {str(item) for item in actual_values}
    if op == "==":
        return str(expected) in actual_text
    if op == "!=":
        return str(expected) not in actual_text
    if op == "in":
        expected_values = {str(item) for item in (expected if isinstance(expected, list) else [expected])}
        return bool(actual_text & expected_values)
    if op == "not_in":
        expected_values = {str(item) for item in (expected if isinstance(expected, list) else [expected])}
        return not bool(actual_text & expected_values)
    return False


def _rule_matches(sample: dict[str, Any], rule: dict[str, Any]) -> bool:
    return _value_matches(_sample_value(sample, str(rule.get("dimension") or "")), str(rule.get("op") or "=="), rule.get("value"))


def apply_candidate_filter(sample: dict[str, Any], filter_config: dict[str, Any]) -> bool:
    filter_type = str(filter_config.get("filter_type") or "")
    rules = filter_config.get("rules") or []
    if not isinstance(rules, list) or not rules:
        return True
    matches = [_rule_matches(sample, rule) for rule in rules if isinstance(rule, dict)]
    if not matches:
        return True
    if filter_type == "include_only":
        return all(matches)
    if filter_type == "exclude":
        return all(matches)
    if filter_type == "combo_exclude":
        return not all(matches)
    return all(matches)


def _empty_bucket() -> dict[str, Any]:
    return {
        "samples": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "timeouts": 0,
        "forward_returns": [],
        "mfe_values": [],
        "mae_values": [],
        "trade_rows": [],
    }


def _add_bucket_sample(bucket: dict[str, Any], sample: dict[str, Any]) -> None:
    bucket["samples"] += 1
    if sample.get("outcome") == "target_hit":
        bucket["target_hits"] += 1
    elif sample.get("outcome") == "stop_hit":
        bucket["stop_hits"] += 1
    elif sample.get("outcome") == "timeout":
        bucket["timeouts"] += 1
    for key, target in [("forward_return_pct", "forward_returns"), ("mfe_pct", "mfe_values"), ("mae_pct", "mae_values")]:
        value = _to_float(sample.get(key))
        if value is not None:
            bucket[target].append(value)
    if sample.get("trade_return_pct") is not None:
        bucket["trade_rows"].append({"outcome": sample.get("outcome"), "trade_return_pct": sample.get("trade_return_pct")})


def _metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": sample.get("outcome"), "trade_return_pct": sample.get("trade_return_pct")} for sample in samples]
    )
    return {"samples": len(samples), **pnl}


def _delta(left: Any, right: Any) -> float | None:
    left_value = _to_float(left)
    right_value = _to_float(right)
    if left_value is None or right_value is None:
        return None
    return _round(left_value - right_value, 3)


def score_filter_result(row: dict[str, Any], *, min_bucket_samples: int) -> float:
    avg_delta = _to_float(row.get("avg_trade_return_delta_pct")) or 0.0
    pf_delta = _to_float(row.get("profit_factor_delta")) or 0.0
    win_delta = _to_float(row.get("win_rate_delta_pct")) or 0.0
    stop_delta = _to_float(row.get("stop_hit_delta_pct")) or 0.0
    avoided_losses = int(row.get("avoided_losses") or 0)
    missed_wins = int(row.get("missed_wins") or 0)
    kept_samples = int(row.get("kept_samples") or 0)
    coverage = _to_float(row.get("coverage_after_filter_pct")) or 0.0
    score = 0.0
    score += avg_delta * 15.0
    score += pf_delta * 20.0
    score += win_delta * 0.5
    score += max(0.0, -stop_delta) * 1.0
    score += avoided_losses * 0.05
    score -= missed_wins * 0.08
    if kept_samples < min_bucket_samples:
        score -= 30.0
    if coverage < 20:
        score -= 20.0
    elif coverage < 40:
        score -= 10.0
    if abs(avg_delta) < 0.03 and abs(pf_delta) < 0.03:
        score = min(score, 10.0)
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _quality_label(row: dict[str, Any], *, min_bucket_samples: int) -> str:
    kept = int(row.get("kept_samples") or 0)
    coverage = _to_float(row.get("coverage_after_filter_pct")) or 0.0
    score = _to_float(row.get("score")) or 0.0
    filtered_pf = _to_float(row.get("filtered_profit_factor"))
    baseline_pf = _to_float(row.get("baseline_profit_factor"))
    filtered_avg = _to_float(row.get("filtered_avg_trade_return_pct"))
    baseline_avg = _to_float(row.get("baseline_avg_trade_return_pct"))
    if kept < min_bucket_samples or coverage < 20:
        return "unstable"
    if (
        score >= 25
        and filtered_pf is not None
        and baseline_pf is not None
        and filtered_avg is not None
        and baseline_avg is not None
        and filtered_pf > baseline_pf
        and filtered_avg > baseline_avg
    ):
        return "good"
    if score >= 10:
        return "medium"
    return "weak"


def evaluate_filter(
    samples: list[dict[str, Any]],
    filter_config: dict[str, Any],
    *,
    baseline_metrics: dict[str, Any],
    min_bucket_samples: int,
) -> dict[str, Any]:
    kept = [sample for sample in samples if apply_candidate_filter(sample, filter_config)]
    kept_ids = {id(sample) for sample in kept}
    removed = [sample for sample in samples if id(sample) not in kept_ids]
    filtered_metrics = _metrics(kept)
    removed_metrics = _metrics(removed)
    baseline_samples = len(samples)
    avoided_losses = sum(1 for sample in removed if (_to_float(sample.get("trade_return_pct")) or 0) < 0)
    missed_wins = sum(1 for sample in removed if (_to_float(sample.get("trade_return_pct")) or 0) > 0)
    row = {
        "rank": None,
        **filter_config,
        "baseline_samples": baseline_samples,
        "kept_samples": len(kept),
        "removed_samples": len(removed),
        "coverage_after_filter_pct": _round(len(kept) / baseline_samples * 100, 2) if baseline_samples else 0.0,
        "baseline_avg_trade_return_pct": baseline_metrics.get("avg_trade_return_pct"),
        "filtered_avg_trade_return_pct": filtered_metrics.get("avg_trade_return_pct"),
        "removed_avg_trade_return_pct": removed_metrics.get("avg_trade_return_pct"),
        "avg_trade_return_delta_pct": _delta(filtered_metrics.get("avg_trade_return_pct"), baseline_metrics.get("avg_trade_return_pct")),
        "baseline_profit_factor": baseline_metrics.get("profit_factor"),
        "filtered_profit_factor": filtered_metrics.get("profit_factor"),
        "removed_profit_factor": removed_metrics.get("profit_factor"),
        "profit_factor_delta": _delta(filtered_metrics.get("profit_factor"), baseline_metrics.get("profit_factor")),
        "baseline_win_rate_pct": baseline_metrics.get("win_rate_pct"),
        "filtered_win_rate_pct": filtered_metrics.get("win_rate_pct"),
        "win_rate_delta_pct": _delta(filtered_metrics.get("win_rate_pct"), baseline_metrics.get("win_rate_pct")),
        "baseline_stop_hit_rate_pct": baseline_metrics.get("stop_hit_rate_pct"),
        "filtered_stop_hit_rate_pct": filtered_metrics.get("stop_hit_rate_pct"),
        "stop_hit_delta_pct": _delta(filtered_metrics.get("stop_hit_rate_pct"), baseline_metrics.get("stop_hit_rate_pct")),
        "filtered_expectancy_pct": filtered_metrics.get("expectancy_pct"),
        "filtered_payoff_ratio": filtered_metrics.get("payoff_ratio"),
        "avoided_losses": avoided_losses,
        "missed_wins": missed_wins,
        "removed_total_trade_return_pct": removed_metrics.get("total_trade_return_pct"),
        "warnings": [],
    }
    if len(kept) < min_bucket_samples:
        row["warnings"].append("kept_samples below min_bucket_samples")
    if row["coverage_after_filter_pct"] < 40:
        row["warnings"].append("coverage_after_filter below 40%; overfitting risk is high")
    row["score"] = score_filter_result(row, min_bucket_samples=min_bucket_samples)
    row["quality_label"] = _quality_label(row, min_bucket_samples=min_bucket_samples)
    return row


def _filter_id(prefix: str, dimension: str, bucket: Any) -> str:
    safe = str(bucket).replace(" ", "_").replace("/", "_").replace("<", "lt").replace(">=", "gte").replace("=", "")
    return f"{prefix}_{dimension}_{safe}"


def _make_single_filter(row: dict[str, Any], *, include_only: bool) -> dict[str, Any]:
    dimension = str(row.get("dimension"))
    bucket = str(row.get("bucket"))
    if include_only:
        return {
            "filter_id": _filter_id("include_only", dimension, bucket),
            "filter_type": "include_only",
            "dimension": dimension,
            "bucket": bucket,
            "description": f"Оставить только {dimension}={bucket}",
            "rules": [{"dimension": dimension, "op": "==", "value": bucket}],
        }
    return {
        "filter_id": _filter_id("exclude", dimension, bucket),
        "filter_type": "exclude",
        "dimension": dimension,
        "bucket": bucket,
        "description": f"Исключить {dimension}={bucket}",
        "rules": [{"dimension": dimension, "op": "!=", "value": bucket}],
    }


def _make_group_ticker_filter(tickers: list[str], *, include_only: bool, n: int) -> dict[str, Any]:
    if include_only:
        return {
            "filter_id": f"include_only_top_{n}_positive_tickers",
            "filter_type": "include_only",
            "dimension": "ticker",
            "bucket": f"top_{n}_positive",
            "description": f"Оставить только top {n} positive tickers",
            "rules": [{"dimension": "ticker", "op": "in", "value": tickers[:n]}],
        }
    return {
        "filter_id": f"exclude_top_{n}_negative_tickers",
        "filter_type": "exclude",
        "dimension": "ticker",
        "bucket": f"top_{n}_negative",
        "description": f"Исключить top {n} negative tickers",
        "rules": [{"dimension": "ticker", "op": "not_in", "value": tickers[:n]}],
    }


def _candidate_filters_from_pockets(
    positive_pockets: list[dict[str, Any]],
    negative_pockets: list[dict[str, Any]],
    *,
    max_filters: int,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in negative_pockets:
        if row.get("dimension") in FILTER_DIMENSIONS:
            item = _make_single_filter(row, include_only=False)
            if item["filter_id"] not in seen:
                filters.append(item)
                seen.add(item["filter_id"])
    for row in positive_pockets:
        if row.get("dimension") in FILTER_DIMENSIONS:
            item = _make_single_filter(row, include_only=True)
            if item["filter_id"] not in seen:
                filters.append(item)
                seen.add(item["filter_id"])

    negative_tickers = [str(row.get("bucket")) for row in negative_pockets if row.get("dimension") == "ticker"]
    positive_tickers = [str(row.get("bucket")) for row in positive_pockets if row.get("dimension") == "ticker"]
    for n in [5, 10, 15]:
        if len(negative_tickers) >= n:
            filters.append(_make_group_ticker_filter(negative_tickers, include_only=False, n=n))
        if len(positive_tickers) >= n:
            filters.append(_make_group_ticker_filter(positive_tickers, include_only=True, n=n))

    filters.extend(
        [
            {
                "filter_id": "exclude_risk_off_low_probability",
                "filter_type": "combo_exclude",
                "description": "Исключить risk_off + low probability",
                "rules": [
                    {"dimension": "market_regime", "op": "==", "value": "risk_off"},
                    {"dimension": "probability_bucket", "op": "in", "value": ["<40", "40-50"]},
                ],
                "combo_logic": "exclude_if_all_match",
            },
            {
                "filter_id": "exclude_high_vol_low_liquidity",
                "filter_type": "combo_exclude",
                "description": "Исключить high/extreme volatility + low liquidity",
                "rules": [
                    {"dimension": "volatility_bucket", "op": "in", "value": ["high", "extreme"]},
                    {"dimension": "liquidity_bucket", "op": "==", "value": "low"},
                ],
                "combo_logic": "exclude_if_all_match",
            },
        ]
    )
    unique: list[dict[str, Any]] = []
    seen.clear()
    for item in filters:
        if item["filter_id"] not in seen:
            unique.append(item)
            seen.add(item["filter_id"])
        if len(unique) >= max_filters:
            break
    return unique


def _apply_trade_policy(
    samples: list[dict[str, Any]],
    *,
    horizon: int,
    target_pct: float,
    stop_pct: float,
    commission_bps: float,
    slippage_bps: float,
    use_best_adaptive_policy: bool,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    policy = BEST_ADAPTIVE_POLICY if use_best_adaptive_policy else {
        "policy_type": "fixed_pct",
        "target_pct": target_pct,
        "stop_pct": stop_pct,
        "horizon": horizon,
        "min_rr": 0.0,
    }
    warnings: set[str] = set()
    enriched: list[dict[str, Any]] = []
    for sample in samples:
        close = _to_float(sample.get("close"))
        future = sample.get("future") if isinstance(sample.get("future"), list) else []
        if close is None or close <= 0 or not future:
            warnings.add("some_samples_missing_close_or_future")
            continue
        setup = compute_trade_setup(
            close=close,
            candles=sample.get("history") or [],
            policy=policy,
            instrument=sample.get("instrument"),
            market_regime=sample.get("market_regime"),
        )
        for warning in setup.get("warnings") or []:
            warnings.add(str(warning))
        outcome = simulate_trade_outcome(
            entry_price=close,
            target_price=float(setup["target_price"]),
            stop_price=float(setup["stop_price"]),
            future_candles=future[: int(setup.get("horizon") or horizon)],
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        )
        updated = {
            **sample,
            "segments": extract_sample_segments({**sample, "risk_reward_ratio": setup.get("risk_reward_ratio")}),
            "trade_policy_type": setup.get("policy_type"),
            "policy_id": "atr_t1_5_s1_6_h30_rr0_8" if use_best_adaptive_policy else "fixed_pct",
            "risk_reward_ratio": setup.get("risk_reward_ratio"),
            "volatility_pct": setup.get("volatility_pct"),
            "volatility_bucket": setup.get("volatility_bucket"),
            "liquidity_bucket": setup.get("liquidity_bucket"),
            "outcome": outcome.get("outcome"),
            "success": outcome.get("success"),
            "forward_return_pct": outcome.get("forward_return_pct"),
            "trade_return_pct": outcome.get("trade_return_pct"),
            "gross_trade_return_pct": outcome.get("gross_trade_return_pct"),
            "mfe_pct": outcome.get("mfe_pct"),
            "mae_pct": outcome.get("mae_pct"),
        }
        updated["segments"] = extract_sample_segments(updated)
        enriched.append(updated)
    return enriched, sorted(warnings), policy


def _pockets(samples: list[dict[str, Any]], *, min_bucket_samples: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_dimensions: dict[str, dict[str, dict[str, Any]]] = {dimension: defaultdict(_empty_bucket) for dimension in DIMENSIONS}
    for sample in samples:
        segments = sample.get("segments") or extract_sample_segments(sample)
        for dimension in DIMENSIONS:
            value = segments.get(dimension, "unknown")
            buckets = value if isinstance(value, list) else [value]
            for bucket in buckets:
                _add_bucket_sample(raw_dimensions[dimension][str(bucket or "unknown")], sample)
    rows: list[dict[str, Any]] = []
    for dimension, bucket_map in raw_dimensions.items():
        for bucket, raw_bucket in bucket_map.items():
            rows.append(
                build_bucket_row(
                    dimension=dimension,
                    bucket=bucket,
                    raw_bucket=raw_bucket,
                    total_samples=len(samples),
                    min_bucket_samples=min_bucket_samples,
                )
            )
    positive = sorted(
        [row for row in rows if row.get("quality_label") == "positive"],
        key=lambda row: (_to_float(row.get("avg_trade_return_pct")) or -999, _to_float(row.get("profit_factor")) or -999),
        reverse=True,
    )
    negative = sorted(
        [row for row in rows if row.get("quality_label") == "negative"],
        key=lambda row: (_to_float(row.get("avg_trade_return_pct")) or 999, _to_float(row.get("profit_factor")) or 999),
    )
    return positive, negative


def _recommendation(best: dict[str, Any] | None, *, samples: int, min_bucket_samples: int) -> str:
    if samples < min_bucket_samples:
        return "needs_more_data"
    if not best:
        return "no_material_filter"
    avg_delta = _to_float(best.get("avg_trade_return_delta_pct")) or 0.0
    pf = _to_float(best.get("filtered_profit_factor")) or 0.0
    coverage = _to_float(best.get("coverage_after_filter_pct")) or 0.0
    if best.get("quality_label") == "good" and pf > 1.05 and avg_delta > 0.05 and coverage >= 40:
        return "promising"
    if (_to_float(best.get("score")) or 0.0) <= 10:
        return "no_material_filter"
    return "recalibrate_needed"


def build_candidate_filter_calibration(
    db: Session,
    max_tickers: int = 100,
    max_samples: int = 3000,
    horizon: int = 30,
    target_pct: float = 0.05,
    stop_pct: float = 0.03,
    min_history: int = 80,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_bucket_samples: int = 20,
    max_filters: int = 80,
    use_best_adaptive_policy: bool = True,
) -> dict[str, Any]:
    base_samples, tickers_used = _build_proxy_samples(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=max(horizon, 30 if use_best_adaptive_policy else horizon),
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_history=min_history,
        use_market_regime_filter=False,
        commission_bps=0.0,
        slippage_bps=0.0,
    )
    samples, policy_warnings, policy = _apply_trade_policy(
        base_samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        use_best_adaptive_policy=use_best_adaptive_policy,
    )
    baseline_metrics = _metrics(samples)
    positive_pockets, negative_pockets = _pockets(samples, min_bucket_samples=min_bucket_samples)
    filters = _candidate_filters_from_pockets(positive_pockets, negative_pockets, max_filters=max_filters)
    results = [
        evaluate_filter(samples, filter_config, baseline_metrics=baseline_metrics, min_bucket_samples=min_bucket_samples)
        for filter_config in filters
    ]
    quality_rank = {"good": 3, "medium": 2, "weak": 1, "unstable": 0}
    results.sort(
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label")), 0),
            _to_float(row.get("score")) or -999,
            _to_float(row.get("filtered_profit_factor")) or -999,
            _to_float(row.get("filtered_avg_trade_return_pct")) or -999,
            _to_float(row.get("coverage_after_filter_pct")) or -999,
        ),
        reverse=True,
    )
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    best = results[0] if results else None
    warnings = list(policy_warnings)
    if len(samples) < min_bucket_samples:
        warnings.append("Sample count is below min_bucket_samples; filter calibration is unstable.")
    if not filters:
        warnings.append("No candidate filters were generated from current pockets.")
    summary = {
        "samples": len(samples),
        "tickers_used": len(tickers_used),
        "baseline_policy": policy,
        "baseline_policy_id": "atr_t1_5_s1_6_h30_rr0_8" if use_best_adaptive_policy else "fixed_pct",
        "baseline_metrics": baseline_metrics,
        "filters_tested": len(results),
        "best_filter_id": (best or {}).get("filter_id"),
        "best_score": (best or {}).get("score"),
        "best_quality_label": (best or {}).get("quality_label"),
        "recommendation": _recommendation(best, samples=len(samples), min_bucket_samples=min_bucket_samples),
        "warnings": warnings,
    }
    return {
        "ok": True,
        "mode": "candidate_filter_calibration",
        "summary": summary,
        "best_filters": results[:10],
        "results": results,
        "positive_pockets_used": positive_pockets[:20],
        "negative_pockets_used": negative_pockets[:20],
        "limitations": [
            "Candidate filter calibration is a research layer and does not change production signal logic.",
            "Historical samples are proxy candle-only and do not replay full live news/global/ML context.",
            "Daily candles do not provide intraday high/low order; same-day target and stop is treated conservatively.",
            "Commission and slippage are simplified bps inputs.",
            "Filters can overfit this sample and must be validated with walk-forward or paper trading.",
            "Current instrument universe can introduce survivorship bias.",
        ],
        "parameters": {
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "horizon": horizon,
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "min_history": min_history,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "min_bucket_samples": min_bucket_samples,
            "max_filters": max_filters,
            "use_best_adaptive_policy": use_best_adaptive_policy,
        },
    }
