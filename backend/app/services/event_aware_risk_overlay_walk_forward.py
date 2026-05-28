from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.event_aware_risk_overlay import DEFAULT_STABLE_RULE_METRICS, score_event_risk_overlay
from app.services.event_aware_rule_search import generate_event_aware_rules, sample_matches_event_rule
from app.services.event_aware_setup_research import build_event_aware_samples
from app.services.event_aware_walk_forward import create_walk_forward_folds
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 3) -> float | None:
    number = _to_float(value)
    return round(number, digits) if number is not None else None


def _clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except Exception:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except Exception:
                return None
    return None


def _period(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [_as_date(row.get("date")) for row in rows if _as_date(row.get("date")) is not None]
    return {
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "samples": len(rows),
    }


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return round(gains, 3) if gains > 0 else None
    return round(gains / losses, 3)


def generate_event_risk_overlay_configs(max_configs: int = 60) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = [
        {
            "config_id": "disabled",
            "moderate_threshold": 999,
            "elevated_threshold": 999,
            "high_threshold": 999,
            "extreme_threshold": 999,
            "moderate_multiplier": 1.0,
            "elevated_multiplier": 1.0,
            "high_multiplier": 1.0,
            "extreme_multiplier": 1.0,
            "winner_miss_penalty": 1.0,
            "min_multiplier": 1.0,
            "disabled": True,
        }
    ]
    for moderate_threshold in [15, 20]:
        for elevated_threshold in [35, 40]:
            for high_threshold in [55, 60]:
                for moderate_multiplier in [0.80, 0.75]:
                    for elevated_multiplier in [0.60, 0.50]:
                        for high_multiplier in [0.40, 0.35]:
                            for extreme_multiplier in [0.25, 0.10]:
                                for winner_miss_penalty in [0.50, 0.75, 1.00]:
                                    config = {
                                        "config_id": (
                                            f"t{moderate_threshold}_{elevated_threshold}_{high_threshold}"
                                            f"_m{int(moderate_multiplier * 100):02d}"
                                            f"_e{int(elevated_multiplier * 100):02d}"
                                            f"_h{int(high_multiplier * 100):02d}"
                                            f"_x{int(extreme_multiplier * 100):02d}"
                                            f"_w{int(winner_miss_penalty * 100):02d}"
                                        ),
                                        "moderate_threshold": moderate_threshold,
                                        "elevated_threshold": elevated_threshold,
                                        "high_threshold": high_threshold,
                                        "extreme_threshold": 80,
                                        "moderate_multiplier": moderate_multiplier,
                                        "elevated_multiplier": elevated_multiplier,
                                        "high_multiplier": high_multiplier,
                                        "extreme_multiplier": extreme_multiplier,
                                        "winner_miss_penalty": winner_miss_penalty,
                                        "min_multiplier": min(0.25, extreme_multiplier),
                                        "disabled": False,
                                    }
                                    configs.append(config)
                                    if len(configs) >= max(1, max_configs):
                                        return configs[:max_configs]
    return configs[:max_configs]


def _matched_stable_rules(sample: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for rule in rules:
        if sample_matches_event_rule(sample, rule):
            row = dict(rule)
            row.update(DEFAULT_STABLE_RULE_METRICS.get(str(rule.get("rule_id")), {}))
            matched.append(row)
    return matched


def _score_sample(sample: dict[str, Any], *, rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    matched = _matched_stable_rules(sample, rules or generate_event_aware_rules(max_rules=120))
    return score_event_risk_overlay(
        matched_rules=matched,
        event_context={
            "event_family": sample.get("event_family"),
            "event_direction": sample.get("event_direction"),
            "event_confirmation": sample.get("event_confirmation"),
            "event_scope": sample.get("event_scope"),
            "event_score": sample.get("event_score"),
        },
        market_regime={"regime": sample.get("market_regime")} if sample.get("market_regime") else None,
    )


def _risk_level_for_config(score: float, config: dict[str, Any]) -> str:
    if bool(config.get("disabled")):
        return "low"
    if score >= (_to_float(config.get("extreme_threshold")) or 80):
        return "extreme"
    if score >= (_to_float(config.get("high_threshold")) or 60):
        return "high"
    if score >= (_to_float(config.get("elevated_threshold")) or 40):
        return "elevated"
    if score >= (_to_float(config.get("moderate_threshold")) or 20):
        return "moderate"
    return "low"


def _multiplier_for_level(level: str, config: dict[str, Any]) -> float:
    if bool(config.get("disabled")):
        return 1.0
    key = {
        "moderate": "moderate_multiplier",
        "elevated": "elevated_multiplier",
        "high": "high_multiplier",
        "extreme": "extreme_multiplier",
    }.get(level)
    if not key:
        return 1.0
    multiplier = _to_float(config.get(key))
    min_multiplier = _to_float(config.get("min_multiplier"))
    if multiplier is None:
        multiplier = 1.0
    if min_multiplier is not None:
        multiplier = max(min_multiplier, multiplier)
    return _clamp(multiplier, 0.0, 1.0)


def apply_overlay_config_to_sample(
    sample: dict[str, Any],
    *,
    config: dict[str, Any],
) -> dict[str, Any]:
    row = dict(sample)
    baseline_return = _to_float(row.get("long_trade_return_pct"))
    if baseline_return is None:
        baseline_return = _to_float(row.get("trade_return_pct")) or 0.0
    risk_score = _to_float(row.get("event_risk_score"))
    reasons = list(row.get("event_risk_reasons") or [])
    if risk_score is None:
        scored = _score_sample(row)
        risk_score = _to_float(scored.get("risk_score")) or 0.0
        reasons = list(scored.get("risk_reasons") or reasons)
    if not bool(config.get("disabled")):
        risk_score *= _to_float(config.get("winner_miss_penalty")) or 1.0
    risk_score = _clamp(risk_score, 0.0, 100.0)
    level = _risk_level_for_config(risk_score, config)
    multiplier = _multiplier_for_level(level, config)
    weighted_return = baseline_return * multiplier
    exposure_cut = 1.0 - multiplier
    row.update(
        {
            "event_risk_score": _round(risk_score, 1),
            "event_risk_level": level,
            "position_multiplier": _round(multiplier, 3),
            "weighted_return_pct": _round(weighted_return, 6),
            "baseline_return_pct": _round(baseline_return, 6),
            "exposure_reduction_pct": _round(exposure_cut * 100, 3),
            "avoided_loss_exposure_pct": _round(max(0.0, -baseline_return) * exposure_cut, 6),
            "missed_upside_exposure_pct": _round(max(0.0, baseline_return) * exposure_cut, 6),
            "weighted_stop_hit_exposure": _round(multiplier if row.get("outcome") == "stop_hit" else 0.0, 6),
            "risk_reasons": reasons[:12],
            "overlay_config_id": config.get("config_id"),
        }
    )
    return row


def calculate_overlay_weighted_metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "samples": 0,
            "baseline_avg_return_pct": None,
            "overlay_weighted_avg_return_pct": None,
            "weighted_return_delta_pct": None,
            "baseline_profit_factor": None,
            "overlay_weighted_profit_factor": None,
            "weighted_profit_factor_delta": None,
            "baseline_win_rate_pct": None,
            "overlay_weighted_win_rate_pct": None,
            "baseline_stop_hit_rate_pct": None,
            "weighted_stop_hit_exposure_pct": None,
            "stop_hit_exposure_delta_pct": None,
            "avg_position_multiplier": None,
            "exposure_reduction_pct": None,
            "avoided_loss_exposure_pct": None,
            "missed_upside_exposure_pct": None,
            "risk_adjusted_improvement_score": None,
            "risk_level_counts": {},
        }
    baseline_returns = [(_to_float(row.get("baseline_return_pct")) or 0.0) for row in samples]
    weighted_returns = [(_to_float(row.get("weighted_return_pct")) or 0.0) for row in samples]
    multipliers = [(_to_float(row.get("position_multiplier")) or 0.0) for row in samples]
    baseline_avg = mean(baseline_returns)
    weighted_avg = mean(weighted_returns)
    baseline_pf = _profit_factor(baseline_returns)
    weighted_pf = _profit_factor(weighted_returns)
    stop_count = sum(1 for row in samples if row.get("outcome") == "stop_hit")
    baseline_stop = stop_count / len(samples) * 100
    total_exposure = sum(multipliers)
    weighted_stop = (
        sum((_to_float(row.get("position_multiplier")) or 0.0) for row in samples if row.get("outcome") == "stop_hit")
        / total_exposure
        * 100
        if total_exposure
        else None
    )
    avg_multiplier = mean(multipliers)
    avoided_loss = mean([_to_float(row.get("avoided_loss_exposure_pct")) or 0.0 for row in samples])
    missed_upside = mean([_to_float(row.get("missed_upside_exposure_pct")) or 0.0 for row in samples])
    pf_delta = (_to_float(weighted_pf) or 0.0) - (_to_float(baseline_pf) or 0.0)
    return_delta = weighted_avg - baseline_avg
    stop_delta = (weighted_stop - baseline_stop) if weighted_stop is not None else 0.0
    exposure_reduction = (1.0 - avg_multiplier) * 100
    score = (
        return_delta * 25
        + pf_delta * 30
        + max(0.0, exposure_reduction) * 0.1
        + avoided_loss * 10
        - missed_upside * 10
        + max(0.0, -stop_delta) * 0.8
    )
    if avg_multiplier < 0.25:
        score -= 15
    return {
        "samples": len(samples),
        "baseline_avg_return_pct": _round(baseline_avg, 3),
        "overlay_weighted_avg_return_pct": _round(weighted_avg, 3),
        "weighted_return_delta_pct": _round(return_delta, 3),
        "baseline_profit_factor": baseline_pf,
        "overlay_weighted_profit_factor": weighted_pf,
        "weighted_profit_factor_delta": _round(pf_delta, 3),
        "baseline_win_rate_pct": _round(sum(1 for value in baseline_returns if value > 0) / len(samples) * 100, 2),
        "overlay_weighted_win_rate_pct": _round(sum(1 for value in weighted_returns if value > 0) / len(samples) * 100, 2),
        "baseline_stop_hit_rate_pct": _round(baseline_stop, 2),
        "weighted_stop_hit_exposure_pct": _round(weighted_stop, 2),
        "stop_hit_exposure_delta_pct": _round(stop_delta, 2),
        "avg_position_multiplier": _round(avg_multiplier, 3),
        "exposure_reduction_pct": _round(exposure_reduction, 2),
        "avoided_loss_exposure_pct": _round(avoided_loss, 3),
        "missed_upside_exposure_pct": _round(missed_upside, 3),
        "risk_adjusted_improvement_score": _round(_clamp(score), 3),
        "risk_level_counts": dict(Counter(str(row.get("event_risk_level") or "unknown") for row in samples)),
    }


def select_best_overlay_config(
    train_samples: list[dict[str, Any]],
    configs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]]:
    evaluated: list[dict[str, Any]] = []
    warnings: list[str] = []
    disabled = next((config for config in configs if config.get("config_id") == "disabled"), configs[0])
    for config in configs:
        rows = [apply_overlay_config_to_sample(row, config=config) for row in train_samples]
        metrics = calculate_overlay_weighted_metrics(rows)
        evaluated.append({"config": config, "metrics": metrics})
    beneficial = [
        row
        for row in evaluated
        if row["config"].get("config_id") != "disabled"
        and (_to_float(row["metrics"].get("weighted_return_delta_pct")) or 0.0) >= 0
        and (_to_float(row["metrics"].get("weighted_profit_factor_delta")) or 0.0) >= 0
        and (_to_float(row["metrics"].get("avg_position_multiplier")) or 0.0) >= 0.3
    ]
    if not beneficial:
        warnings.append("No beneficial overlay config on train; selected disabled baseline config.")
        metrics = next((row["metrics"] for row in evaluated if row["config"].get("config_id") == "disabled"), {})
        return disabled, metrics, _rank_config_metrics(evaluated), warnings
    best = max(
        beneficial,
        key=lambda row: (
            _to_float(row["metrics"].get("risk_adjusted_improvement_score")) or -999,
            _to_float(row["metrics"].get("weighted_return_delta_pct")) or -999,
            _to_float(row["metrics"].get("weighted_profit_factor_delta")) or -999,
            _to_float(row["metrics"].get("avg_position_multiplier")) or -999,
        ),
    )
    return best["config"], best["metrics"], _rank_config_metrics(evaluated), warnings


def _rank_config_metrics(evaluated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "config_id": row["config"].get("config_id"),
            "risk_adjusted_improvement_score": row["metrics"].get("risk_adjusted_improvement_score"),
            "weighted_return_delta_pct": row["metrics"].get("weighted_return_delta_pct"),
            "weighted_profit_factor_delta": row["metrics"].get("weighted_profit_factor_delta"),
            "avg_position_multiplier": row["metrics"].get("avg_position_multiplier"),
        }
        for row in evaluated
    ]
    return sorted(
        rows,
        key=lambda row: (
            _to_float(row.get("risk_adjusted_improvement_score")) or -999,
            _to_float(row.get("weighted_return_delta_pct")) or -999,
        ),
        reverse=True,
    )[:10]


def overlay_fold_quality(metrics: dict[str, Any], selected_config: dict[str, Any]) -> str:
    if selected_config.get("config_id") == "disabled":
        return "disabled"
    improved = [
        (_to_float(metrics.get("weighted_return_delta_pct")) or 0.0) > 0,
        (_to_float(metrics.get("weighted_profit_factor_delta")) or 0.0) > 0,
        (_to_float(metrics.get("stop_hit_exposure_delta_pct")) or 0.0) <= 0,
    ]
    if all(improved):
        return "good"
    if sum(1 for item in improved if item) >= 2:
        return "medium"
    if not improved[0] and not improved[1]:
        return "bad"
    return "weak"


def recommendation_from_overlay_summary(summary: dict[str, Any]) -> str:
    samples = int(summary.get("event_samples") or summary.get("samples") or 0)
    completed = int(summary.get("folds_completed") or 0)
    requested = max(1, int(summary.get("folds_requested") or 4))
    needed = 3 if requested >= 4 else max(1, requested - 1)
    if samples < 100 or completed < 2:
        return "needs_more_data"
    positive_return = int(summary.get("positive_return_delta_folds") or 0)
    positive_pf = int(summary.get("positive_pf_delta_folds") or 0)
    avg_return = _to_float(summary.get("avg_weighted_return_delta_pct")) or 0.0
    avg_pf = _to_float(summary.get("avg_weighted_profit_factor_delta")) or 0.0
    avg_multiplier = _to_float(summary.get("avg_position_multiplier")) or 0.0
    if positive_return >= needed and positive_pf >= needed and avg_return > 0 and avg_pf > 0 and avg_multiplier >= 0.3:
        return "promising_soft_overlay"
    if (positive_return >= 1 or positive_pf >= 1 or avg_return > 0 or avg_pf > 0) and avg_multiplier >= 0.25:
        return "research_only"
    return "reject"


def _config_frequency(folds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fold in folds:
        config_id = str((fold.get("selected_config") or {}).get("config_id") or "unknown")
        groups[config_id].append(fold)
    rows: list[dict[str, Any]] = []
    for config_id, items in groups.items():
        train_scores = [
            _to_float((fold.get("train_best_metrics") or {}).get("risk_adjusted_improvement_score"))
            for fold in items
            if _to_float((fold.get("train_best_metrics") or {}).get("risk_adjusted_improvement_score")) is not None
        ]
        test_return = [
            _to_float((fold.get("test_metrics") or {}).get("weighted_return_delta_pct"))
            for fold in items
            if _to_float((fold.get("test_metrics") or {}).get("weighted_return_delta_pct")) is not None
        ]
        test_pf = [
            _to_float((fold.get("test_metrics") or {}).get("weighted_profit_factor_delta"))
            for fold in items
            if _to_float((fold.get("test_metrics") or {}).get("weighted_profit_factor_delta")) is not None
        ]
        rows.append(
            {
                "config_id": config_id,
                "selected_folds": len(items),
                "avg_train_score": _round(mean(train_scores), 3) if train_scores else None,
                "avg_test_return_delta_pct": _round(mean(test_return), 3) if test_return else None,
                "avg_test_pf_delta": _round(mean(test_pf), 3) if test_pf else None,
            }
        )
    return sorted(rows, key=lambda row: (int(row.get("selected_folds") or 0), _to_float(row.get("avg_test_return_delta_pct")) or -999), reverse=True)


def _mean_metric(folds: list[dict[str, Any]], metric: str) -> float | None:
    values = [
        _to_float((fold.get("test_metrics") or {}).get(metric))
        for fold in folds
        if _to_float((fold.get("test_metrics") or {}).get(metric)) is not None
    ]
    return _round(mean(values), 3) if values else None


def build_event_risk_overlay_walk_forward(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    max_events: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    event_lookback_days: int = 7,
    event_decay_days: int = 14,
    folds: int = 4,
    train_ratio: float = 0.6,
    min_train_samples: int = 100,
    min_test_samples: int = 50,
    max_configs: int = 60,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    include_global_events: bool = True,
    include_ticker_events: bool = True,
) -> dict[str, Any]:
    sample_data = build_event_aware_samples(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )
    warnings = list(sample_data.get("warnings") or [])
    if not sample_data.get("ok"):
        return {
            "ok": False,
            "mode": "event_risk_overlay_walk_forward",
            "summary": {"recommendation": "needs_more_data", "warnings": warnings},
            "folds": [],
            "config_frequency": [],
            "warnings": warnings,
            "limitations": [],
        }
    samples = [row for row in sample_data.get("samples") or [] if row.get("event_family")]
    rules = generate_event_aware_rules(max_rules=120)
    scored_samples = []
    for sample in samples:
        scored = _score_sample(sample, rules=rules)
        row = dict(sample)
        row["event_risk_score"] = scored.get("risk_score")
        row["event_risk_reasons"] = scored.get("risk_reasons") or []
        scored_samples.append(row)
    configs = generate_event_risk_overlay_configs(max_configs=max_configs)
    fold_specs = create_walk_forward_folds(
        scored_samples,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    if not fold_specs:
        warnings.append("Insufficient event samples for overlay walk-forward folds.")
    fold_results: list[dict[str, Any]] = []
    for spec in fold_specs:
        train_rows = list(spec.get("train_rows") or [])
        test_rows = list(spec.get("test_rows") or [])
        selected_config, train_metrics, ranked_configs, fold_warnings = select_best_overlay_config(train_rows, configs)
        test_applied = [apply_overlay_config_to_sample(row, config=selected_config) for row in test_rows]
        test_metrics = calculate_overlay_weighted_metrics(test_applied)
        fold_results.append(
            {
                "fold": spec.get("fold"),
                "train_period": _period(train_rows),
                "test_period": _period(test_rows),
                "selected_config": selected_config,
                "train_best_metrics": train_metrics,
                "train_top_configs": ranked_configs,
                "test_metrics": test_metrics,
                "quality_label": overlay_fold_quality(test_metrics, selected_config),
                "warnings": fold_warnings,
            }
        )
    completed = len(fold_results)
    positive_return = sum(1 for fold in fold_results if (_to_float((fold.get("test_metrics") or {}).get("weighted_return_delta_pct")) or 0.0) > 0)
    positive_pf = sum(1 for fold in fold_results if (_to_float((fold.get("test_metrics") or {}).get("weighted_profit_factor_delta")) or 0.0) > 0)
    positive_score = sum(1 for fold in fold_results if (_to_float((fold.get("test_metrics") or {}).get("risk_adjusted_improvement_score")) or 0.0) > 0)
    disabled = sum(1 for fold in fold_results if (fold.get("selected_config") or {}).get("config_id") == "disabled")
    summary = {
        "samples": len(sample_data.get("samples") or []),
        "event_samples": len(scored_samples),
        "folds_requested": folds,
        "folds_completed": completed,
        "avg_weighted_return_delta_pct": _mean_metric(fold_results, "weighted_return_delta_pct"),
        "avg_weighted_profit_factor_delta": _mean_metric(fold_results, "weighted_profit_factor_delta"),
        "avg_stop_hit_exposure_delta_pct": _mean_metric(fold_results, "stop_hit_exposure_delta_pct"),
        "avg_exposure_reduction_pct": _mean_metric(fold_results, "exposure_reduction_pct"),
        "avg_position_multiplier": _mean_metric(fold_results, "avg_position_multiplier"),
        "positive_return_delta_folds": positive_return,
        "positive_pf_delta_folds": positive_pf,
        "positive_risk_adjusted_folds": positive_score,
        "disabled_folds": disabled,
        "best_config_id": (_config_frequency(fold_results)[0].get("config_id") if fold_results else None),
        "warnings": warnings,
    }
    summary["recommendation"] = recommendation_from_overlay_summary(summary)
    return {
        "ok": True,
        "mode": "event_risk_overlay_walk_forward",
        "summary": summary,
        "folds": fold_results,
        "config_frequency": _config_frequency(fold_results),
        "warnings": warnings,
        "limitations": [
            "Train folds choose only deterministic overlay parameters; production consumer behavior remains unchanged.",
            "This validates soft exposure weighting, not a hard trade block or short-selling engine.",
            "Curated event history and daily-candle outcome labels remain research approximations.",
            "Paper trading is required before making the overlay a default risk control.",
        ],
    }
