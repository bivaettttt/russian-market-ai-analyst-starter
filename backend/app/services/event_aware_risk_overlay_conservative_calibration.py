from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.event_aware_risk_overlay_walk_forward import (
    _config_frequency,
    _mean_metric,
    _period,
    _round,
    _score_sample,
    _to_float,
    apply_overlay_config_to_sample,
    calculate_overlay_weighted_metrics,
    generate_event_risk_overlay_configs,
)
from app.services.event_aware_rule_search import generate_event_aware_rules
from app.services.event_aware_setup_research import build_event_aware_samples
from app.services.event_aware_walk_forward import create_walk_forward_folds
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID


def _clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _disabled_config() -> dict[str, Any]:
    return {
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
        "profile": "disabled",
        "disabled": True,
    }


def _aggressive_benchmark_config() -> dict[str, Any]:
    return {
        "config_id": "benchmark_aggressive_t15_35_55_m75_e60_h40_x10_w100",
        "moderate_threshold": 15,
        "elevated_threshold": 35,
        "high_threshold": 55,
        "extreme_threshold": 80,
        "moderate_multiplier": 0.75,
        "elevated_multiplier": 0.60,
        "high_multiplier": 0.40,
        "extreme_multiplier": 0.10,
        "winner_miss_penalty": 1.0,
        "min_multiplier": 0.10,
        "profile": "aggressive_benchmark",
        "disabled": False,
    }


def _default_soft_config() -> dict[str, Any]:
    return {
        "config_id": "benchmark_default_soft_overlay",
        "moderate_threshold": 20,
        "elevated_threshold": 40,
        "high_threshold": 60,
        "extreme_threshold": 80,
        "moderate_multiplier": 0.75,
        "elevated_multiplier": 0.50,
        "high_multiplier": 0.35,
        "extreme_multiplier": 0.25,
        "winner_miss_penalty": 1.0,
        "min_multiplier": 0.25,
        "profile": "default_soft_benchmark",
        "disabled": False,
    }


def generate_conservative_overlay_configs(max_configs: int = 100) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = [_disabled_config(), _aggressive_benchmark_config(), _default_soft_config()]
    if max_configs <= len(configs):
        return configs[: max(1, max_configs)]
    seen = {str(config.get("config_id")) for config in configs}
    for moderate_threshold in [20, 25, 30]:
        for elevated_threshold in [40, 45, 50]:
            for high_threshold in [60, 65, 70]:
                for extreme_threshold in [80, 85]:
                    for moderate_multiplier in [0.95, 0.90, 0.85]:
                        for elevated_multiplier in [0.80, 0.75, 0.70]:
                            for high_multiplier in [0.65, 0.60, 0.55]:
                                for extreme_multiplier in [0.50, 0.40]:
                                    for winner_miss_penalty in [0.50, 0.75, 1.00]:
                                        config_id = (
                                            f"cons_t{moderate_threshold}_{elevated_threshold}_{high_threshold}_{extreme_threshold}"
                                            f"_m{int(moderate_multiplier * 100):02d}"
                                            f"_e{int(elevated_multiplier * 100):02d}"
                                            f"_h{int(high_multiplier * 100):02d}"
                                            f"_x{int(extreme_multiplier * 100):02d}"
                                            f"_w{int(winner_miss_penalty * 100):02d}"
                                        )
                                        if config_id in seen:
                                            continue
                                        configs.append(
                                            {
                                                "config_id": config_id,
                                                "moderate_threshold": moderate_threshold,
                                                "elevated_threshold": elevated_threshold,
                                                "high_threshold": high_threshold,
                                                "extreme_threshold": extreme_threshold,
                                                "moderate_multiplier": moderate_multiplier,
                                                "elevated_multiplier": elevated_multiplier,
                                                "high_multiplier": high_multiplier,
                                                "extreme_multiplier": extreme_multiplier,
                                                "winner_miss_penalty": winner_miss_penalty,
                                                "min_multiplier": min(0.40, extreme_multiplier),
                                                "profile": "conservative",
                                                "disabled": False,
                                            }
                                        )
                                        seen.add(config_id)
                                        if len(configs) >= max_configs:
                                            return configs
    return configs[:max_configs]


def constraint_status(
    metrics: dict[str, Any],
    *,
    min_avg_position_multiplier: float,
    max_exposure_reduction_pct: float,
) -> dict[str, bool]:
    multiplier = _to_float(metrics.get("avg_position_multiplier")) or 0.0
    reduction = _to_float(metrics.get("exposure_reduction_pct")) or 0.0
    return {
        "passes_min_multiplier": multiplier >= min_avg_position_multiplier,
        "passes_max_exposure_reduction": reduction <= max_exposure_reduction_pct,
    }


def score_conservative_overlay_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return_delta = _to_float(metrics.get("weighted_return_delta_pct")) or 0.0
    pf_delta = _to_float(metrics.get("weighted_profit_factor_delta")) or 0.0
    stop_delta = _to_float(metrics.get("stop_hit_exposure_delta_pct")) or 0.0
    multiplier = _to_float(metrics.get("avg_position_multiplier")) or 0.0
    exposure_reduction = _to_float(metrics.get("exposure_reduction_pct")) or 0.0
    score = (
        return_delta * 25
        + pf_delta * 30
        + max(0.0, -stop_delta) * 0.8
        + min(multiplier, 1.0) * 15
        - max(0.0, exposure_reduction - 50.0) * 0.8
        - max(0.0, 0.50 - multiplier) * 60
    )
    if 20 <= exposure_reduction <= 50:
        score += 5
    if multiplier < 0.4:
        score -= 15
    if return_delta < 0:
        score -= 10
    score = _round(_clamp(score), 3) or 0.0
    if metrics.get("config_id") == "disabled":
        quality = "disabled"
    elif (
        pf_delta > 0
        and return_delta >= 0
        and stop_delta <= 0
        and multiplier >= 0.50
        and exposure_reduction <= 50
    ):
        quality = "good"
    elif pf_delta > 0 and stop_delta <= 0 and multiplier >= 0.45:
        quality = "medium"
    elif pf_delta < 0 or return_delta < 0 or exposure_reduction > 60:
        quality = "bad"
    else:
        quality = "weak"
    return {"conservative_score": score, "quality_label": quality}


def _apply_config_metrics(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    applied = [apply_overlay_config_to_sample(row, config=config) for row in rows]
    metrics = calculate_overlay_weighted_metrics(applied)
    metrics["config_id"] = config.get("config_id")
    metrics.update(score_conservative_overlay_metrics(metrics))
    return metrics


def _ranked_configs(rows: list[dict[str, Any]], configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = [_apply_config_metrics(rows, config) for config in configs]
    return sorted(
        ranked,
        key=lambda row: (
            _to_float(row.get("conservative_score")) or -999,
            _to_float(row.get("weighted_profit_factor_delta")) or -999,
            _to_float(row.get("avg_position_multiplier")) or -999,
        ),
        reverse=True,
    )


def select_conservative_config(
    train_rows: list[dict[str, Any]],
    configs: list[dict[str, Any]],
    *,
    min_avg_position_multiplier: float,
    max_exposure_reduction_pct: float,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    ranked = _ranked_configs(train_rows, configs)
    config_by_id = {str(config.get("config_id")): config for config in configs}
    candidates = []
    for metrics in ranked:
        config_id = str(metrics.get("config_id") or "")
        if config_id == "disabled":
            continue
        constraints = constraint_status(
            metrics,
            min_avg_position_multiplier=min_avg_position_multiplier,
            max_exposure_reduction_pct=max_exposure_reduction_pct,
        )
        if (
            all(constraints.values())
            and (_to_float(metrics.get("weighted_profit_factor_delta")) or 0.0) >= 0
            and (_to_float(metrics.get("stop_hit_exposure_delta_pct")) or 0.0) <= 0
        ):
            candidates.append(metrics)
    if candidates:
        best_metrics = candidates[0]
        return config_by_id[str(best_metrics.get("config_id"))], best_metrics, ranked[:10], warnings
    warnings.append("No train config passed conservative constraints with PF/stop-hit improvement; selected disabled baseline.")
    disabled = config_by_id.get("disabled") or _disabled_config()
    disabled_metrics = next((row for row in ranked if row.get("config_id") == "disabled"), _apply_config_metrics(train_rows, disabled))
    return disabled, disabled_metrics, ranked[:10], warnings


def conservative_recommendation(summary: dict[str, Any], *, min_positive_pf_folds: int) -> str:
    samples = int(summary.get("event_samples") or summary.get("samples") or 0)
    completed = int(summary.get("folds_completed") or 0)
    if samples < 100 or completed < 2:
        return "needs_more_data"
    avg_multiplier = _to_float(summary.get("avg_position_multiplier")) or 0.0
    exposure = _to_float(summary.get("avg_exposure_reduction_pct")) or 0.0
    positive_pf = int(summary.get("positive_pf_delta_folds") or 0)
    positive_return = int(summary.get("positive_return_delta_folds") or 0)
    pf_delta = _to_float(summary.get("avg_weighted_profit_factor_delta")) or 0.0
    stop_delta = _to_float(summary.get("avg_stop_hit_exposure_delta_pct")) or 0.0
    if (
        completed >= 3
        and avg_multiplier >= 0.50
        and exposure <= 50
        and positive_pf >= min_positive_pf_folds
        and pf_delta > 0
        and stop_delta < 0
        and positive_return >= 2
    ):
        return "conservative_overlay_candidate"
    if pf_delta > 0 or stop_delta < 0 or positive_pf >= 1:
        return "research_only"
    return "reject"


def _config_frequency(folds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fold in folds:
        grouped[str((fold.get("selected_config") or {}).get("config_id") or "unknown")].append(fold)
    rows = []
    for config_id, items in grouped.items():
        rows.append(
            {
                "config_id": config_id,
                "selected_folds": len(items),
                "avg_train_conservative_score": _round(mean([_to_float((item.get("train_best_metrics") or {}).get("conservative_score")) or 0.0 for item in items]), 3),
                "avg_test_return_delta_pct": _round(mean([_to_float((item.get("test_metrics") or {}).get("weighted_return_delta_pct")) or 0.0 for item in items]), 3),
                "avg_test_pf_delta": _round(mean([_to_float((item.get("test_metrics") or {}).get("weighted_profit_factor_delta")) or 0.0 for item in items]), 3),
                "avg_position_multiplier": _round(mean([_to_float((item.get("test_metrics") or {}).get("avg_position_multiplier")) or 0.0 for item in items]), 3),
            }
        )
    return sorted(rows, key=lambda row: (int(row.get("selected_folds") or 0), _to_float(row.get("avg_test_pf_delta")) or -999), reverse=True)


def _benchmark_comparison(rows: list[dict[str, Any]], selected_config_ids: list[str]) -> dict[str, Any]:
    benchmarks = [_disabled_config(), _aggressive_benchmark_config(), _default_soft_config()]
    selected = selected_config_ids[0] if selected_config_ids else None
    selected_config = None
    if selected:
        for config in generate_conservative_overlay_configs(max_configs=300):
            if config.get("config_id") == selected:
                selected_config = config
                break
    if selected_config and selected_config.get("config_id") not in {config.get("config_id") for config in benchmarks}:
        benchmarks.append(selected_config)
    result: dict[str, Any] = {}
    for config in benchmarks:
        key = str(config.get("profile") or config.get("config_id"))
        result[key] = _apply_config_metrics(rows, config)
    return result


def build_conservative_event_risk_overlay_calibration(
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
    max_configs: int = 100,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_avg_position_multiplier: float = 0.50,
    max_exposure_reduction_pct: float = 50.0,
    min_positive_pf_folds: int = 3,
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
        return {"ok": False, "mode": "conservative_event_risk_overlay_calibration", "summary": {"recommendation": "needs_more_data", "warnings": warnings}, "folds": [], "config_frequency": [], "benchmark_comparison": {}, "warnings": warnings, "limitations": []}
    samples = [row for row in sample_data.get("samples") or [] if row.get("event_family")]
    rules = generate_event_aware_rules(max_rules=120)
    scored_samples = []
    for sample in samples:
        scored = _score_sample(sample, rules=rules)
        row = dict(sample)
        row["event_risk_score"] = scored.get("risk_score")
        row["event_risk_reasons"] = scored.get("risk_reasons") or []
        scored_samples.append(row)
    configs = generate_conservative_overlay_configs(max_configs=max_configs)
    fold_specs = create_walk_forward_folds(
        scored_samples,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    if not fold_specs:
        warnings.append("Insufficient event samples for conservative overlay calibration folds.")
    fold_results: list[dict[str, Any]] = []
    for spec in fold_specs:
        train_rows = list(spec.get("train_rows") or [])
        test_rows = list(spec.get("test_rows") or [])
        selected_config, train_metrics, ranked_configs, fold_warnings = select_conservative_config(
            train_rows,
            configs,
            min_avg_position_multiplier=min_avg_position_multiplier,
            max_exposure_reduction_pct=max_exposure_reduction_pct,
        )
        test_rows_applied = [apply_overlay_config_to_sample(row, config=selected_config) for row in test_rows]
        test_metrics = calculate_overlay_weighted_metrics(test_rows_applied)
        test_metrics["config_id"] = selected_config.get("config_id")
        test_metrics.update(score_conservative_overlay_metrics(test_metrics))
        constraints = constraint_status(
            test_metrics,
            min_avg_position_multiplier=min_avg_position_multiplier,
            max_exposure_reduction_pct=max_exposure_reduction_pct,
        )
        fold_results.append(
            {
                "fold": spec.get("fold"),
                "train_period": _period(train_rows),
                "test_period": _period(test_rows),
                "selected_config": selected_config,
                "train_best_metrics": train_metrics,
                "train_top_configs": ranked_configs,
                "test_metrics": test_metrics,
                "constraint_status": constraints,
                "quality_label": test_metrics.get("quality_label"),
                "warnings": fold_warnings,
            }
        )
    positive_return = sum(1 for fold in fold_results if (_to_float((fold.get("test_metrics") or {}).get("weighted_return_delta_pct")) or 0.0) > 0)
    positive_pf = sum(1 for fold in fold_results if (_to_float((fold.get("test_metrics") or {}).get("weighted_profit_factor_delta")) or 0.0) > 0)
    positive_stop = sum(1 for fold in fold_results if (_to_float((fold.get("test_metrics") or {}).get("stop_hit_exposure_delta_pct")) or 0.0) < 0)
    constraints_ok = sum(1 for fold in fold_results if all((fold.get("constraint_status") or {}).values()))
    config_frequency = _config_frequency(fold_results)
    summary = {
        "samples": len(sample_data.get("samples") or []),
        "event_samples": len(scored_samples),
        "folds_requested": folds,
        "folds_completed": len(fold_results),
        "configs_tested": len(configs),
        "avg_weighted_return_delta_pct": _mean_metric(fold_results, "weighted_return_delta_pct"),
        "avg_weighted_profit_factor_delta": _mean_metric(fold_results, "weighted_profit_factor_delta"),
        "avg_stop_hit_exposure_delta_pct": _mean_metric(fold_results, "stop_hit_exposure_delta_pct"),
        "avg_exposure_reduction_pct": _mean_metric(fold_results, "exposure_reduction_pct"),
        "avg_position_multiplier": _mean_metric(fold_results, "avg_position_multiplier"),
        "positive_return_delta_folds": positive_return,
        "positive_pf_delta_folds": positive_pf,
        "positive_stop_hit_folds": positive_stop,
        "constraint_passing_folds": constraints_ok,
        "best_config_id": config_frequency[0].get("config_id") if config_frequency else None,
        "warnings": warnings,
    }
    summary["recommendation"] = conservative_recommendation(summary, min_positive_pf_folds=min_positive_pf_folds)
    return {
        "ok": True,
        "mode": "conservative_event_risk_overlay_calibration",
        "summary": summary,
        "folds": fold_results,
        "config_frequency": config_frequency,
        "benchmark_comparison": _benchmark_comparison(scored_samples, [str(row.get("config_id")) for row in config_frequency]),
        "warnings": warnings,
        "limitations": [
            "Conservative calibration remains research-only and opt-in.",
            "Production consumer actions and default recommendations are unchanged.",
            "Metrics are exposure-weighted proxy backtest diagnostics on curated historical events.",
            "Paper trading is required before using a calibrated overlay as a default risk control.",
        ],
    }
