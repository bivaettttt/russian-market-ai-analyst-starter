from __future__ import annotations

from itertools import product
from typing import Any

from sqlalchemy.orm import Session

from app.services.consumer_signal_backtest_audit import (
    _build_proxy_samples,
    _by_market_regime,
    _metrics_for_samples,
    _round,
    _sample_would_be_blocked_by_regime,
    _to_float,
)
from app.services.market_regime import normalize_market_regime_formula_config


PARAMETER_GRID = {
    "risk_off_threshold": [-20, -25, -30, -35],
    "strong_risk_off_threshold": [-35, -40, -45],
    "downside_pressure_block_threshold": [55, 60, 65, 70],
    "risk_off_position_multiplier": [0.0, 0.25, 0.5],
    "neutral_position_multiplier": [0.7, 0.85, 1.0],
    "downside_weight": [0.15, 0.20, 0.25],
    "volatility_weight": [0.05, 0.10, 0.15],
}


def _rate(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return _round(part / total * 100, 2)


def _safe_delta(left: Any, right: Any) -> float | None:
    left_value = _to_float(left)
    right_value = _to_float(right)
    if left_value is None or right_value is None:
        return None
    return _round(left_value - right_value, 2)


def _formula_config_id(config: dict[str, Any]) -> str:
    return (
        f"ro{int(config['risk_off_threshold'])}"
        f"_sro{int(config['strong_risk_off_threshold'])}"
        f"_dp{int(config['downside_pressure_block_threshold'])}"
        f"_rom{str(float(config['risk_off_position_multiplier'])).replace('.', '_')}"
        f"_nm{str(float(config['neutral_position_multiplier'])).replace('.', '_')}"
        f"_dw{str(float(config['downside_weight'])).replace('.', '_')}"
        f"_vw{str(float(config['volatility_weight'])).replace('.', '_')}"
    )


def generate_regime_formula_configs(max_configs: int) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    warnings: list[str] = []
    raw_configs = list(
        product(
            PARAMETER_GRID["risk_off_threshold"],
            PARAMETER_GRID["strong_risk_off_threshold"],
            PARAMETER_GRID["downside_pressure_block_threshold"],
            PARAMETER_GRID["risk_off_position_multiplier"],
            PARAMETER_GRID["neutral_position_multiplier"],
            PARAMETER_GRID["downside_weight"],
            PARAMETER_GRID["volatility_weight"],
        )
    )
    total_requested = len(raw_configs)
    if total_requested > max_configs:
        warnings.append(f"Formula grid truncated from {total_requested} to {max_configs} configs for runtime protection.")
        step = total_requested / max_configs
        raw_configs = [raw_configs[min(total_requested - 1, int(index * step))] for index in range(max_configs)]

    configs = []
    for (
        risk_off_threshold,
        strong_risk_off_threshold,
        downside_pressure_block_threshold,
        risk_off_position_multiplier,
        neutral_position_multiplier,
        downside_weight,
        volatility_weight,
    ) in raw_configs:
        configs.append(
            normalize_market_regime_formula_config(
                {
                    "risk_off_threshold": risk_off_threshold,
                    "strong_risk_off_threshold": strong_risk_off_threshold,
                    "downside_pressure_block_threshold": downside_pressure_block_threshold,
                    "risk_off_position_multiplier": risk_off_position_multiplier,
                    "neutral_position_multiplier": neutral_position_multiplier,
                    "downside_weight": downside_weight,
                    "volatility_weight": volatility_weight,
                }
            )
        )

    return configs, {**PARAMETER_GRID, "max_configs": max_configs, "total_requested_configs": total_requested}, warnings


def _reclassify_market_regime(market_regime: dict[str, Any], formula_config: dict[str, Any]) -> dict[str, Any]:
    config = normalize_market_regime_formula_config(formula_config)
    trend_score = _to_float(market_regime.get("trend_score")) or 0.0
    breadth_score = _to_float(market_regime.get("breadth_score")) or 0.0
    downside_pressure = _to_float(market_regime.get("downside_pressure")) or 0.0
    volatility_score = _to_float(market_regime.get("volatility_score")) or 0.0
    sample_size = int(market_regime.get("sample_size") or 0)

    regime_score = max(
        -100.0,
        min(
            100.0,
            trend_score * float(config["trend_weight"])
            + breadth_score * float(config["breadth_weight"])
            - downside_pressure * float(config["downside_weight"])
            - volatility_score * float(config["volatility_weight"]),
        ),
    )
    if regime_score >= float(config["risk_on_threshold"]):
        regime = "risk_on"
    elif regime_score <= float(config["risk_off_threshold"]):
        regime = "risk_off"
    else:
        regime = "neutral"

    long_allowed = not (
        regime_score <= float(config["strong_risk_off_threshold"])
        or downside_pressure >= float(config["downside_pressure_block_threshold"])
    )
    if regime == "risk_on":
        position_multiplier = float(config["risk_on_position_multiplier"])
        min_rr_multiplier = 1.0
        min_ml_probability_addon = 0
    elif regime == "risk_off":
        position_multiplier = (
            float(config["risk_off_position_multiplier"])
            if long_allowed
            else float(config["strong_risk_off_position_multiplier"])
        )
        min_rr_multiplier = 1.4 if long_allowed else 1.5
        min_ml_probability_addon = 10 if long_allowed else 15
    else:
        position_multiplier = float(config["neutral_position_multiplier"])
        min_rr_multiplier = 1.1
        min_ml_probability_addon = 4

    reasons = [
        f"Calibration formula classified historical regime as {regime}: score {regime_score:.2f}.",
        f"Downside pressure {downside_pressure:.1f}/100, long_allowed={bool(long_allowed)}.",
    ]
    return {
        **market_regime,
        "regime": regime,
        "regime_score": _round(regime_score, 2),
        "long_allowed": bool(long_allowed),
        "position_multiplier": _round(position_multiplier, 2),
        "min_rr_multiplier": _round(min_rr_multiplier, 2),
        "min_ml_probability_addon": min_ml_probability_addon,
        "sample_size": sample_size,
        "formula_config": config,
        "reasons": reasons,
    }


def _apply_formula_to_samples(samples: list[dict[str, Any]], formula_config: dict[str, Any]) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for sample in samples:
        market_regime = _reclassify_market_regime(sample.get("market_regime") or {}, formula_config)
        updated = {
            **sample,
            "market_regime": market_regime,
            "market_regime_name": market_regime.get("regime") or "unknown",
            "market_regime_regime": market_regime.get("regime"),
            "market_regime_score": market_regime.get("regime_score"),
            "market_regime_long_allowed": bool(market_regime.get("long_allowed", True)),
            "market_regime_position_multiplier": market_regime.get("position_multiplier"),
            "market_regime_reason": "; ".join((market_regime.get("reasons") or [])[:2]),
            "market_regime_filter_blocked": False,
        }
        updated["market_regime_would_block"] = _sample_would_be_blocked_by_regime(updated)
        adjusted.append(updated)
    return adjusted


def score_regime_formula_result(row: dict[str, Any], *, min_signals_after_filter: int) -> float:
    stop_delta = _to_float(row.get("stop_hit_delta_pct")) or 0.0
    avg_return_delta = _to_float(row.get("avg_return_delta_pct")) or 0.0
    target_delta = _to_float(row.get("target_hit_delta_pct")) or 0.0
    avoided_stop_hits = int(row.get("avoided_stop_hits") or 0)
    missed_target_hits = int(row.get("missed_target_hits") or 0)
    filtered_signals = int(row.get("filtered_signals") or 0)
    coverage_after = _to_float(row.get("coverage_after_filter_pct")) or 0.0

    score = 0.0
    score += max(0.0, -stop_delta) * 2.0
    score += avg_return_delta * 5.0
    score += target_delta
    score += avoided_stop_hits * 0.2
    score -= missed_target_hits * 0.3
    if filtered_signals < min_signals_after_filter:
        score -= 30.0
    if coverage_after < 40.0:
        score -= 15.0
    if filtered_signals >= 100:
        score += 5.0
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _quality_label(score: float, filtered_signals: int, min_signals_after_filter: int) -> str:
    if filtered_signals < min_signals_after_filter:
        return "unstable"
    if score >= 25:
        return "good"
    if score >= 10:
        return "medium"
    return "weak"


def _evaluate_formula_config(
    *,
    samples: list[dict[str, Any]],
    formula_config: dict[str, Any],
    min_signals_after_filter: int,
) -> dict[str, Any]:
    adjusted_samples = _apply_formula_to_samples(samples, formula_config)
    baseline = _metrics_for_samples(adjusted_samples)
    blocked_samples = [sample for sample in adjusted_samples if _sample_would_be_blocked_by_regime(sample)]
    filtered_samples = [sample for sample in adjusted_samples if not _sample_would_be_blocked_by_regime(sample)]
    filtered = _metrics_for_samples(filtered_samples)
    by_regime = _by_market_regime(adjusted_samples)

    baseline_signals = int(baseline.get("signals") or 0)
    filtered_signals = int(filtered.get("signals") or 0)
    avoided_stop_hits = sum(1 for sample in blocked_samples if sample.get("outcome") == "stop_hit")
    missed_target_hits = sum(1 for sample in blocked_samples if sample.get("outcome") == "target_hit")
    risk_off_samples = [sample for sample in adjusted_samples if sample.get("market_regime_name") == "risk_off"]
    risk_off_metrics = _metrics_for_samples(risk_off_samples)
    ratio = avoided_stop_hits / missed_target_hits if missed_target_hits else None

    row = {
        "rank": None,
        "config_id": _formula_config_id(formula_config),
        "formula_config": normalize_market_regime_formula_config(formula_config),
        "baseline_signals": baseline_signals,
        "filtered_signals": filtered_signals,
        "signals_delta": filtered_signals - baseline_signals,
        "coverage_after_filter_pct": _rate(filtered_signals, baseline_signals),
        "baseline_target_hit_rate_pct": baseline.get("target_hit_rate_pct"),
        "filtered_target_hit_rate_pct": filtered.get("target_hit_rate_pct"),
        "target_hit_delta_pct": _safe_delta(filtered.get("target_hit_rate_pct"), baseline.get("target_hit_rate_pct")),
        "baseline_stop_hit_rate_pct": baseline.get("stop_hit_rate_pct"),
        "filtered_stop_hit_rate_pct": filtered.get("stop_hit_rate_pct"),
        "stop_hit_delta_pct": _safe_delta(filtered.get("stop_hit_rate_pct"), baseline.get("stop_hit_rate_pct")),
        "baseline_avg_forward_return_pct": baseline.get("avg_forward_return_pct"),
        "filtered_avg_forward_return_pct": filtered.get("avg_forward_return_pct"),
        "avg_return_delta_pct": _safe_delta(filtered.get("avg_forward_return_pct"), baseline.get("avg_forward_return_pct")),
        "baseline_avg_trade_return_pct": baseline.get("avg_trade_return_pct"),
        "filtered_avg_trade_return_pct": filtered.get("avg_trade_return_pct"),
        "avg_trade_return_delta_pct": _safe_delta(filtered.get("avg_trade_return_pct"), baseline.get("avg_trade_return_pct")),
        "win_rate_delta_pct": _safe_delta(filtered.get("win_rate_pct"), baseline.get("win_rate_pct")),
        "profit_factor_delta": _safe_delta(filtered.get("profit_factor"), baseline.get("profit_factor")),
        "filtered_by_risk_off": len(blocked_samples),
        "avoided_stop_hits": avoided_stop_hits,
        "missed_target_hits": missed_target_hits,
        "avoided_stop_to_missed_target_ratio": _round(ratio, 2),
        "risk_off_samples": len(risk_off_samples),
        "risk_off_stop_hit_rate_pct": risk_off_metrics.get("stop_hit_rate_pct"),
        "by_market_regime": by_regime,
        "warnings": [],
    }
    score = score_regime_formula_result(row, min_signals_after_filter=min_signals_after_filter)
    row["score"] = score
    row["quality_label"] = _quality_label(score, filtered_signals, min_signals_after_filter)
    if filtered_signals < min_signals_after_filter:
        row["warnings"].append("filtered_signals below min_signals_after_filter; estimate is unstable")
    return row


def _recommendation(best: dict[str, Any] | None, samples_count: int, min_signals_after_filter: int) -> str:
    if not best or samples_count < min_signals_after_filter:
        return "insufficient_data"
    stop_delta = _to_float(best.get("stop_hit_delta_pct")) or 0.0
    return_delta = _to_float(best.get("avg_return_delta_pct")) or 0.0
    score = _to_float(best.get("score")) or 0.0
    filtered_signals = int(best.get("filtered_signals") or 0)
    if score >= 25 and stop_delta <= -2.0 and return_delta > 0 and filtered_signals >= min_signals_after_filter:
        return "promising"
    risk_off_stop = _to_float(best.get("risk_off_stop_hit_rate_pct")) or 0.0
    if risk_off_stop >= 55 and (stop_delta >= 0 or return_delta <= 0):
        return "recalibrate_needed"
    return "keep_current"


def build_regime_formula_calibration(
    db: Session,
    max_tickers: int = 80,
    max_samples: int = 2000,
    lookback: int = 60,
    horizon: int = 20,
    target_pct: float = 0.05,
    stop_pct: float = 0.03,
    min_history: int = 80,
    max_configs: int = 80,
    min_signals_after_filter: int = 30,
) -> dict[str, Any]:
    samples, tickers_used = _build_proxy_samples(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_history=min_history,
        use_market_regime_filter=False,
        market_regime_lookback=lookback,
    )
    configs, parameter_grid, warnings = generate_regime_formula_configs(max_configs=max_configs)
    if len(samples) < min_signals_after_filter:
        warnings.append("Sample count is below min_signals_after_filter; calibration is unstable.")

    results = [
        _evaluate_formula_config(
            samples=samples,
            formula_config=config,
            min_signals_after_filter=min_signals_after_filter,
        )
        for config in configs
    ]
    results.sort(
        key=lambda row: (
            _to_float(row.get("score")) or -999.0,
            _to_float(row.get("avg_return_delta_pct")) or -999.0,
            -(_to_float(row.get("stop_hit_delta_pct")) or 999.0),
        ),
        reverse=True,
    )
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank

    best = results[0] if results else None
    baseline_summary = _metrics_for_samples(samples)
    best_filtered_summary = {
        "signals": best.get("filtered_signals"),
        "target_hit_rate_pct": best.get("filtered_target_hit_rate_pct"),
        "stop_hit_rate_pct": best.get("filtered_stop_hit_rate_pct"),
        "avg_forward_return_pct": best.get("filtered_avg_forward_return_pct"),
        "avg_trade_return_pct": best.get("filtered_avg_trade_return_pct"),
        "coverage_after_filter_pct": best.get("coverage_after_filter_pct"),
    } if best else {}
    recommendation = _recommendation(best, len(samples), min_signals_after_filter)

    return {
        "ok": True,
        "mode": "regime_formula_calibration",
        "summary": {
            "configs_tested": len(results),
            "best_config_id": best.get("config_id") if best else None,
            "best_score": best.get("score") if best else None,
            "best_quality_label": best.get("quality_label") if best else None,
            "baseline_summary": baseline_summary,
            "best_filtered_summary": best_filtered_summary,
            "recommendation": recommendation,
            "samples": len(samples),
            "tickers_used": len(tickers_used),
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "min_signals_after_filter": min_signals_after_filter,
            "warnings": warnings,
        },
        "best_configs": results[:10],
        "results": results,
        "parameter_grid": parameter_grid,
        "limitations": [
            "Regime formula calibration is a research evaluation layer; it does not change production thresholds.",
            "Historical samples use proxy candle-only consumer signals.",
            "No commissions, taxes, spreads or slippage are included.",
            "Daily candles do not provide intraday event order; if target and stop are both touched in one candle, stop_hit is assumed.",
            "Current instrument universe can introduce survivorship bias.",
            "Historical news and global macro context are approximate in this proxy calibration.",
        ],
    }
