from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.services.candidate_filter_calibration import BEST_ADAPTIVE_POLICY, _apply_trade_policy, _delta, _metrics
from app.services.consumer_signal_backtest_audit import _build_proxy_samples
from app.services.consumer_signals import _round, _to_float
from app.services.expectancy_breakdown import extract_sample_segments


POLICY_ID = "atr_t1_5_s1_6_h30_rr0_8"


def _sample_features(sample: dict[str, Any]) -> dict[str, Any]:
    segments = sample.get("segments") if isinstance(sample.get("segments"), dict) else extract_sample_segments(sample)
    probability = _to_float(sample.get("target_probability_pct") or sample.get("probability_pct"))
    ml_probability = _to_float(sample.get("ml_probability_pct") or sample.get("proxy_ml_probability_pct"))
    return {
        **segments,
        "ticker": sample.get("ticker") or segments.get("ticker") or "unknown",
        "sector": sample.get("sector") or segments.get("sector") or "unknown",
        "asset_type": sample.get("asset_type") or segments.get("asset_type") or "unknown",
        "market_regime": segments.get("market_regime") or sample.get("market_regime_name") or "unknown",
        "volatility_bucket": sample.get("volatility_bucket") or segments.get("volatility_bucket") or "unknown",
        "liquidity_bucket": sample.get("liquidity_bucket") or segments.get("liquidity_bucket") or "unknown",
        "probability_bucket": segments.get("probability_bucket") or "unknown",
        "ml_probability_bucket": segments.get("ml_probability_bucket") or "unknown",
        "rr_bucket": segments.get("rr_bucket") or "unknown",
        "audit_confidence": segments.get("audit_confidence") or "unknown",
        "news_effect": segments.get("news_effect") or "none",
        "macro_effect": segments.get("macro_effect") or "none",
        "action": segments.get("action") or "unknown",
        "blocked_by": segments.get("blocked_by") or ["none"],
        "target_probability_pct": probability,
        "ml_probability_pct": ml_probability,
        "risk_reward_ratio": _to_float(sample.get("risk_reward_ratio")),
        "global_event_adjustment_pct": _to_float(sample.get("global_event_adjustment_pct")) or 0.0,
        "news_adjustment_pct": _to_float(sample.get("news_adjustment_pct") or sample.get("ticker_news_adjustment_pct")) or 0.0,
    }


def _feature_value(sample: dict[str, Any], field: str) -> Any:
    features = sample.get("features")
    if not isinstance(features, dict):
        features = _sample_features(sample)
    return features.get(field)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    return [value]


def _compare(value: Any, op: str, expected: Any) -> bool:
    if op == "exists":
        return not _is_missing(value)
    if op == "not_exists":
        return _is_missing(value)
    if _is_missing(value):
        return False

    if op in {">=", ">", "<=", "<"}:
        actual_number = _to_float(value)
        expected_number = _to_float(expected)
        if actual_number is None or expected_number is None:
            return False
        if op == ">=":
            return actual_number >= expected_number
        if op == ">":
            return actual_number > expected_number
        if op == "<=":
            return actual_number <= expected_number
        return actual_number < expected_number

    actual_values = {str(item) for item in _as_list(value)}
    if op == "==":
        return str(expected) in actual_values
    if op == "!=":
        return str(expected) not in actual_values
    expected_values = {str(item) for item in _as_list(expected)}
    if op == "in":
        return bool(actual_values & expected_values)
    if op == "not_in":
        return not bool(actual_values & expected_values)
    return False


def sample_matches_rule(sample: dict[str, Any], rule: dict[str, Any]) -> bool:
    conditions = rule.get("conditions") or []
    if not isinstance(conditions, list) or not conditions:
        return True
    logic = str(rule.get("logic") or "all")
    matches = [
        _compare(_feature_value(sample, str(condition.get("field") or "")), str(condition.get("op") or "=="), condition.get("value"))
        for condition in conditions
        if isinstance(condition, dict)
    ]
    if not matches:
        return True
    if logic != "all":
        return all(matches)
    return all(matches)


def _condition(field: str, op: str, value: Any = None) -> dict[str, Any]:
    item = {"field": field, "op": op}
    if op not in {"exists", "not_exists"}:
        item["value"] = value
    return item


def _rule(rule_id: str, description: str, conditions: list[dict[str, Any]], family: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "description": description,
        "policy_id": POLICY_ID,
        "conditions": conditions,
        "logic": "all",
        "family": family,
    }


def generate_composite_rules(max_rules: int = 120) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []

    for probability in [45, 50, 55, 60]:
        for rr in [0.8, 1.0, 1.2, 1.5]:
            rules.append(
                _rule(
                    f"prob{probability}_rr{str(rr).replace('.', '_')}",
                    f"probability>={probability} + RR>={rr}",
                    [_condition("target_probability_pct", ">=", probability), _condition("risk_reward_ratio", ">=", rr)],
                    "probability_rr",
                )
            )

    for probability in [45, 50, 55]:
        rules.append(
            _rule(
                f"prob{probability}_no_riskoff",
                f"probability>={probability} + market_regime!=risk_off",
                [_condition("target_probability_pct", ">=", probability), _condition("market_regime", "!=", "risk_off")],
                "probability_regime",
            )
        )
        rules.append(
            _rule(
                f"prob{probability}_riskon_neutral",
                f"probability>={probability} + market_regime in risk_on/neutral",
                [_condition("target_probability_pct", ">=", probability), _condition("market_regime", "in", ["risk_on", "neutral"])],
                "probability_regime",
            )
        )

    for probability in [45, 50, 55]:
        rules.append(
            _rule(
                f"prob{probability}_no_extreme_vol",
                f"probability>={probability} + volatility!=extreme",
                [_condition("target_probability_pct", ">=", probability), _condition("volatility_bucket", "not_in", ["extreme"])],
                "probability_vol_liq",
            )
        )
        rules.append(
            _rule(
                f"prob{probability}_liquidity_not_low",
                f"probability>={probability} + liquidity_bucket!=low",
                [_condition("target_probability_pct", ">=", probability), _condition("liquidity_bucket", "!=", "low")],
                "probability_vol_liq",
            )
        )
        rules.append(
            _rule(
                f"prob{probability}_no_extreme_vol_liq_not_low",
                f"probability>={probability} + volatility!=extreme + liquidity_bucket!=low",
                [
                    _condition("target_probability_pct", ">=", probability),
                    _condition("volatility_bucket", "not_in", ["extreme"]),
                    _condition("liquidity_bucket", "!=", "low"),
                ],
                "probability_vol_liq",
            )
        )

    for probability in [45, 50, 55]:
        for ml_probability in [15, 20, 25, 30]:
            rules.append(
                _rule(
                    f"prob{probability}_ml{ml_probability}",
                    f"probability>={probability} + ML probability>={ml_probability}",
                    [
                        _condition("target_probability_pct", ">=", probability),
                        _condition("ml_probability_pct", ">=", ml_probability),
                    ],
                    "ml_probability",
                )
            )

    for probability in [45, 50, 55]:
        rules.append(
            _rule(
                f"prob{probability}_audit_medium_high",
                f"probability>={probability} + audit_confidence in medium/high",
                [
                    _condition("target_probability_pct", ">=", probability),
                    _condition("audit_confidence", "in", ["medium", "high", "Средняя", "Высокая"]),
                ],
                "audit_confidence",
            )
        )

    for rr in [1.0, 1.2]:
        rules.append(
            _rule(
                f"rr{str(rr).replace('.', '_')}_no_high_extreme_vol",
                f"RR>={rr} + volatility not high/extreme",
                [_condition("risk_reward_ratio", ">=", rr), _condition("volatility_bucket", "not_in", ["high", "extreme"])],
                "rr_volatility",
            )
        )

    for ml_probability in [20, 25]:
        for rr in [1.0, 1.2]:
            rules.append(
                _rule(
                    f"no_riskoff_ml{ml_probability}_rr{str(rr).replace('.', '_')}",
                    f"market_regime!=risk_off + ML probability>={ml_probability} + RR>={rr}",
                    [
                        _condition("market_regime", "!=", "risk_off"),
                        _condition("ml_probability_pct", ">=", ml_probability),
                        _condition("risk_reward_ratio", ">=", rr),
                    ],
                    "regime_ml_rr",
                )
            )

    for probability in [45, 50]:
        rules.append(
            _rule(
                f"prob{probability}_no_news_macro_penalty",
                f"probability>={probability} + no news/macro penalty or veto",
                [
                    _condition("target_probability_pct", ">=", probability),
                    _condition("macro_effect", "not_in", ["penalty", "veto"]),
                    _condition("news_effect", "not_in", ["penalty", "veto"]),
                ],
                "news_macro",
            )
        )

    rules.append(
        _rule(
            "conservative_prob55_rr12_audit_no_riskoff",
            "probability>=55 + RR>=1.2 + audit_confidence!=low + market_regime!=risk_off",
            [
                _condition("target_probability_pct", ">=", 55),
                _condition("risk_reward_ratio", ">=", 1.2),
                _condition("audit_confidence", "!=", "low"),
                _condition("market_regime", "!=", "risk_off"),
            ],
            "conservative_high_quality",
        )
    )
    rules.append(
        _rule(
            "aggressive_prob45_rr08_liq_no_extreme",
            "probability>=45 + RR>=0.8 + liquidity_bucket!=low + volatility_bucket!=extreme",
            [
                _condition("target_probability_pct", ">=", 45),
                _condition("risk_reward_ratio", ">=", 0.8),
                _condition("liquidity_bucket", "!=", "low"),
                _condition("volatility_bucket", "!=", "extreme"),
            ],
            "aggressive_coverage",
        )
    )

    return rules[: max(0, max_rules)]


def score_composite_rule_result(row: dict[str, Any], *, min_trades: int) -> float:
    selected_avg = _to_float(row.get("selected_avg_trade_return_pct")) or 0.0
    selected_pf = _to_float(row.get("selected_profit_factor")) or 0.0
    selected_win = _to_float(row.get("selected_win_rate_pct")) or 0.0
    baseline_win = _to_float(row.get("baseline_win_rate_pct")) or 0.0
    selected_stop = _to_float(row.get("selected_stop_hit_rate_pct")) or 0.0
    baseline_stop = _to_float(row.get("baseline_stop_hit_rate_pct")) or 0.0
    avg_delta = _to_float(row.get("avg_trade_return_delta_pct")) or 0.0
    pf_delta = _to_float(row.get("profit_factor_delta")) or 0.0
    selected_samples = int(row.get("selected_samples") or 0)
    coverage = _to_float(row.get("coverage_pct")) or 0.0

    score = 0.0
    score += selected_avg * 25.0
    score += max(0.0, selected_pf - 1.0) * 35.0
    score += max(0.0, selected_win - baseline_win) * 0.5
    score += max(0.0, baseline_stop - selected_stop) * 0.8
    score += avg_delta * 15.0
    score += pf_delta * 20.0
    if selected_samples < min_trades:
        score -= 40.0
    if coverage < 5:
        score -= 30.0
    elif coverage < 10:
        score -= 20.0
    elif coverage < 20:
        score -= 10.0
    if selected_samples < 100:
        score -= 10.0
    if selected_pf < 1.02 and selected_avg <= 0:
        score = min(score, 10.0)
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _quality_label(row: dict[str, Any], *, min_trades: int) -> str:
    selected_samples = int(row.get("selected_samples") or 0)
    coverage = _to_float(row.get("coverage_pct")) or 0.0
    selected_pf = _to_float(row.get("selected_profit_factor")) or 0.0
    selected_avg = _to_float(row.get("selected_avg_trade_return_pct")) or 0.0
    score = _to_float(row.get("score")) or 0.0
    if selected_samples < min_trades or coverage < 5:
        return "unstable"
    if selected_pf >= 1.08 and selected_avg > 0 and score >= 25:
        return "good"
    if selected_pf >= 1.02 and selected_avg >= 0 and score >= 10:
        return "medium"
    return "weak"


def evaluate_composite_rule(
    samples: list[dict[str, Any]],
    rule: dict[str, Any],
    *,
    baseline_metrics: dict[str, Any],
    min_trades: int,
) -> dict[str, Any]:
    selected = [sample for sample in samples if sample_matches_rule(sample, rule)]
    metrics = _metrics(selected)
    baseline_samples = len(samples)
    row = {
        "rank": None,
        **rule,
        "baseline_samples": baseline_samples,
        "selected_samples": len(selected),
        "coverage_pct": _round(len(selected) / baseline_samples * 100, 2) if baseline_samples else 0.0,
        "baseline_avg_trade_return_pct": baseline_metrics.get("avg_trade_return_pct"),
        "selected_avg_trade_return_pct": metrics.get("avg_trade_return_pct"),
        "avg_trade_return_delta_pct": _delta(metrics.get("avg_trade_return_pct"), baseline_metrics.get("avg_trade_return_pct")),
        "baseline_profit_factor": baseline_metrics.get("profit_factor"),
        "selected_profit_factor": metrics.get("profit_factor"),
        "profit_factor_delta": _delta(metrics.get("profit_factor"), baseline_metrics.get("profit_factor")),
        "baseline_win_rate_pct": baseline_metrics.get("win_rate_pct"),
        "selected_win_rate_pct": metrics.get("win_rate_pct"),
        "win_rate_delta_pct": _delta(metrics.get("win_rate_pct"), baseline_metrics.get("win_rate_pct")),
        "baseline_stop_hit_rate_pct": baseline_metrics.get("stop_hit_rate_pct"),
        "selected_stop_hit_rate_pct": metrics.get("stop_hit_rate_pct"),
        "stop_hit_delta_pct": _delta(metrics.get("stop_hit_rate_pct"), baseline_metrics.get("stop_hit_rate_pct")),
        "selected_target_hit_rate_pct": metrics.get("target_hit_rate_pct"),
        "selected_timeout_rate_pct": metrics.get("timeout_rate_pct"),
        "selected_expectancy_pct": metrics.get("expectancy_pct"),
        "selected_payoff_ratio": metrics.get("payoff_ratio"),
        "selected_avg_win_pct": metrics.get("avg_win_pct"),
        "selected_avg_loss_pct": metrics.get("avg_loss_pct"),
        "warnings": [],
    }
    if row["selected_samples"] < min_trades:
        row["warnings"].append("selected_samples below min_trades; unstable estimate")
    if row["coverage_pct"] < 10:
        row["warnings"].append("coverage below 10%; overfitting risk is high")
    row["score"] = score_composite_rule_result(row, min_trades=min_trades)
    row["quality_label"] = _quality_label(row, min_trades=min_trades)
    return row


def _recommendation(best: dict[str, Any] | None, *, samples: int, min_trades: int) -> str:
    if samples < min_trades:
        return "needs_more_data"
    if not best:
        return "no_material_rule"
    selected_pf = _to_float(best.get("selected_profit_factor")) or 0.0
    selected_avg = _to_float(best.get("selected_avg_trade_return_pct")) or 0.0
    coverage = _to_float(best.get("coverage_pct")) or 0.0
    if best.get("quality_label") == "good" and selected_pf >= 1.08 and selected_avg > 0.05 and coverage >= 10:
        return "promising"
    if (_to_float(best.get("score")) or 0.0) <= 10:
        return "no_material_rule"
    return "recalibrate_needed"


def _rule_family_counts(rules: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(rule.get("family") or "unknown") for rule in rules))


def build_composite_rule_calibration(
    db: Session,
    max_tickers: int = 100,
    max_samples: int = 3000,
    max_rules: int = 120,
    horizon: int = 30,
    min_history: int = 80,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_trades: int = 50,
    use_best_adaptive_policy: bool = True,
) -> dict[str, Any]:
    base_samples, tickers_used = _build_proxy_samples(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=max(horizon, 30 if use_best_adaptive_policy else horizon),
        target_pct=0.05,
        stop_pct=0.03,
        min_history=min_history,
        use_market_regime_filter=False,
        commission_bps=0.0,
        slippage_bps=0.0,
    )
    samples, policy_warnings, policy = _apply_trade_policy(
        base_samples,
        horizon=horizon,
        target_pct=0.05,
        stop_pct=0.03,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        use_best_adaptive_policy=use_best_adaptive_policy,
    )
    for sample in samples:
        sample["features"] = _sample_features(sample)

    baseline_metrics = _metrics(samples)
    generated_rules = generate_composite_rules(max_rules=10_000)
    rules = generated_rules[:max_rules]
    warnings = list(policy_warnings)
    if len(generated_rules) > max_rules:
        warnings.append(f"Rule grid truncated from {len(generated_rules)} to {max_rules} rules for runtime protection.")
    if len(samples) < min_trades:
        warnings.append("Sample count is below min_trades; composite calibration is unstable.")

    results = [
        evaluate_composite_rule(samples, rule, baseline_metrics=baseline_metrics, min_trades=min_trades)
        for rule in rules
    ]
    quality_rank = {"good": 3, "medium": 2, "weak": 1, "unstable": 0}
    results.sort(
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label")), 0),
            _to_float(row.get("score")) or -999,
            _to_float(row.get("selected_profit_factor")) or -999,
            _to_float(row.get("selected_avg_trade_return_pct")) or -999,
            _to_float(row.get("coverage_pct")) or -999,
        ),
        reverse=True,
    )
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    best = results[0] if results else None
    policy_id = POLICY_ID if use_best_adaptive_policy else "fixed_pct"
    summary = {
        "samples": len(samples),
        "tickers_used": len(tickers_used),
        "baseline_policy": policy if use_best_adaptive_policy else {"policy_type": "fixed_pct", "target_pct": 0.05, "stop_pct": 0.03, "horizon": horizon, "min_rr": 0.0},
        "baseline_policy_id": policy_id,
        "baseline_metrics": baseline_metrics,
        "rules_tested": len(results),
        "best_rule_id": (best or {}).get("rule_id"),
        "best_score": (best or {}).get("score"),
        "best_quality_label": (best or {}).get("quality_label"),
        "recommendation": _recommendation(best, samples=len(samples), min_trades=min_trades),
        "warnings": warnings,
    }
    return {
        "ok": True,
        "mode": "composite_rule_calibration",
        "summary": summary,
        "best_rules": results[:10],
        "results": results,
        "rule_families": _rule_family_counts(rules),
        "limitations": [
            "Composite rule calibration is a research layer and does not change production signal logic.",
            "Historical samples are proxy candle-only and do not replay full live news/global/ML context.",
            "Daily candles do not provide intraday high/low order; same-day target and stop is treated conservatively.",
            "Commission and slippage are simplified bps inputs.",
            "Composite rules can overfit this sample and need walk-forward validation before production.",
            "Current instrument universe can introduce survivorship bias.",
        ],
        "parameters": {
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "max_rules": max_rules,
            "horizon": horizon,
            "min_history": min_history,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "min_trades": min_trades,
            "use_best_adaptive_policy": use_best_adaptive_policy,
        },
    }
