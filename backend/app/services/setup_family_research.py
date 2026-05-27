from __future__ import annotations

from collections import defaultdict
from itertools import product
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.candidate_filter_calibration import _apply_trade_policy
from app.services.consumer_signal_backtest_audit import _build_proxy_samples
from app.services.consumer_signals import ML_V2_LONG_CANDIDATE_ACTIONS, _round, _to_float
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID
from app.services.setup_candidate_generator import SETUP_FAMILIES, classify_setup_families


def _rate(part: int, total: int) -> float | None:
    return _round(part / total * 100, 2) if total else None


def classify_setup_family_quality(*, samples: int, profit_factor: float | None, avg_trade_return_pct: float | None, min_signals: int) -> str:
    pf = _to_float(profit_factor)
    avg = _to_float(avg_trade_return_pct)
    if samples < min_signals:
        return "unstable"
    if pf is not None and avg is not None and pf >= 1.10 and avg > 0:
        return "good"
    if pf is not None and avg is not None and pf >= 1.02 and avg >= 0:
        return "medium"
    if (pf is not None and pf < 0.90) or (avg is not None and avg < 0):
        return "bad"
    return "weak"


def score_setup_config_result(row: dict[str, Any], *, min_signals: int) -> float:
    samples = int(row.get("samples") or 0)
    coverage = _to_float(row.get("coverage_pct")) or 0.0
    avg = _to_float(row.get("avg_trade_return_pct")) or 0.0
    pf = _to_float(row.get("profit_factor")) or 0.0
    win = _to_float(row.get("win_rate_pct")) or 0.0
    stop = _to_float(row.get("stop_hit_rate_pct")) or 0.0
    score = avg * 25 + max(0.0, pf - 1.0) * 35 + win * 0.2 - stop * 0.2
    if samples < min_signals:
        score -= 40
    if coverage < 5:
        score -= 20
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _build_policy_samples(
    db: Session,
    *,
    max_tickers: int,
    max_samples: int,
    min_history: int,
    horizon: int,
    policy_id: str,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[list[dict[str, Any]], set[str], list[str], dict[str, Any]]:
    use_best_policy = policy_id == DEFAULT_POLICY_ID
    warnings: list[str] = []
    if not use_best_policy:
        warnings.append(f"Unsupported policy_id={policy_id}; using fixed 5/3/horizon fallback.")
    base_samples, tickers_used = _build_proxy_samples(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=max(horizon, 30 if use_best_policy else horizon),
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
        use_best_adaptive_policy=use_best_policy,
    )
    warnings.extend(policy_warnings)
    return samples, tickers_used, warnings, policy


def _candidate_rows(
    samples: list[dict[str, Any]],
    *,
    config: dict[str, Any] | None = None,
    setup_family_filter: str | None = None,
    max_setups: int = 100,
) -> list[dict[str, Any]]:
    per_family_counts: dict[str, int] = defaultdict(int)
    candidates: list[dict[str, Any]] = []
    for sample in samples:
        history = sample.get("history") if isinstance(sample.get("history"), list) else []
        cfg = {**(config or {})}
        market_regime = sample.get("market_regime") if isinstance(sample.get("market_regime"), dict) else {}
        cfg.setdefault("market_regime", sample.get("market_regime_name") or market_regime.get("regime"))
        cfg.setdefault("market_regime_score", sample.get("market_regime_score") or market_regime.get("regime_score"))
        classified = classify_setup_families(history, config=cfg)
        if not classified.get("ok"):
            continue
        for family in classified.get("active_setup_families") or []:
            if setup_family_filter and family != setup_family_filter:
                continue
            if per_family_counts[family] >= max_setups:
                continue
            setup = (classified.get("setups") or {}).get(family) or {}
            trade_return = _to_float(sample.get("trade_return_pct"))
            if trade_return is None:
                continue
            per_family_counts[family] += 1
            candidates.append(
                {
                    "ticker": sample.get("ticker"),
                    "date": sample.get("date"),
                    "setup_family": family,
                    "setup_score": setup.get("score"),
                    "setup_confidence": setup.get("confidence"),
                    "primary_setup_family": classified.get("primary_setup_family"),
                    "entry_price": sample.get("close"),
                    "target_pct": sample.get("target_return_pct"),
                    "stop_pct": sample.get("stop_return_pct"),
                    "outcome": sample.get("outcome"),
                    "trade_return_pct": sample.get("trade_return_pct"),
                    "mfe_pct": sample.get("mfe_pct"),
                    "mae_pct": sample.get("mae_pct"),
                    "features": setup.get("features") or {},
                }
            )
    return candidates


def _metrics_for_rows(rows: list[dict[str, Any]], *, family: str, total_samples: int, min_signals: int) -> dict[str, Any]:
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )
    scores = [_to_float(row.get("setup_score")) for row in rows if _to_float(row.get("setup_score")) is not None]
    tickers = {row.get("ticker") for row in rows if row.get("ticker")}
    samples = len(rows)
    quality = classify_setup_family_quality(
        samples=samples,
        profit_factor=pnl.get("profit_factor"),
        avg_trade_return_pct=pnl.get("avg_trade_return_pct"),
        min_signals=min_signals,
    )
    return {
        "setup_family": family,
        "samples": samples,
        "tickers": len(tickers),
        "coverage_pct": _rate(samples, total_samples) or 0.0,
        "avg_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "median_trade_return_pct": pnl.get("median_trade_return_pct"),
        "profit_factor": pnl.get("profit_factor"),
        "win_rate_pct": pnl.get("win_rate_pct"),
        "target_hit_rate_pct": pnl.get("target_hit_rate_pct"),
        "stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
        "timeout_rate_pct": pnl.get("timeout_rate_pct"),
        "avg_mfe_pct": _round(mean([_to_float(row.get("mfe_pct")) for row in rows if _to_float(row.get("mfe_pct")) is not None]), 2) if rows else None,
        "avg_mae_pct": _round(mean([_to_float(row.get("mae_pct")) for row in rows if _to_float(row.get("mae_pct")) is not None]), 2) if rows else None,
        "avg_setup_score": _round(mean(scores), 2) if scores else None,
        "quality_label": quality,
        "diagnostic": _diagnostic(quality),
    }


def _diagnostic(quality: str) -> str:
    if quality == "good":
        return "Promising setup family; validate with parameter sweep and walk-forward before production."
    if quality == "medium":
        return "Potential setup family with modest edge; needs robustness checks."
    if quality == "bad":
        return "Negative expectancy setup in this proxy sample."
    if quality == "unstable":
        return "Too few samples for a stable conclusion."
    return "Enough samples but weak metrics."


def _old_consumer_baseline(samples: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in samples if str(row.get("baseline_action") or row.get("action") or "").lower() in ML_V2_LONG_CANDIDATE_ACTIONS]
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )
    return {
        "samples": len(rows),
        "avg_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "profit_factor": pnl.get("profit_factor"),
        "win_rate_pct": pnl.get("win_rate_pct"),
        "stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
    }


def build_setup_family_research(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_signals: int = 30,
    max_setups: int = 100,
) -> dict[str, Any]:
    samples, tickers_used, warnings, policy = _build_policy_samples(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    candidates = _candidate_rows(samples, max_setups=max_setups)
    by_family_raw: dict[str, list[dict[str, Any]]] = {family: [] for family in SETUP_FAMILIES}
    for row in candidates:
        by_family_raw.setdefault(str(row.get("setup_family")), []).append(row)
    by_family = [
        _metrics_for_rows(rows, family=family, total_samples=max(1, len(samples)), min_signals=min_signals)
        for family, rows in by_family_raw.items()
    ]
    quality_rank = {"good": 4, "medium": 3, "weak": 2, "bad": 1, "unstable": 0}
    by_family.sort(
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label")), 0),
            _to_float(row.get("profit_factor")) if _to_float(row.get("profit_factor")) is not None else -999,
            _to_float(row.get("avg_trade_return_pct")) if _to_float(row.get("avg_trade_return_pct")) is not None else -999,
        ),
        reverse=True,
    )
    best = by_family[0] if by_family else None
    good_or_medium = [row for row in by_family if row.get("quality_label") in {"good", "medium"}]
    if not samples:
        recommendation = "needs_more_data"
    elif good_or_medium:
        recommendation = "promising_setup_found"
    else:
        recommendation = "no_edge_found"
    examples_by_quality = sorted(candidates, key=lambda row: (_to_float(row.get("trade_return_pct")) or 0.0), reverse=True)
    summary = {
        "samples": len(candidates),
        "base_samples": len(samples),
        "tickers_used": len(tickers_used),
        "setup_families_tested": len(SETUP_FAMILIES),
        "best_setup_family": best.get("setup_family") if best else None,
        "best_quality_label": best.get("quality_label") if best else None,
        "old_consumer_baseline": _old_consumer_baseline(samples),
        "policy": policy,
        "recommendation": recommendation,
        "warnings": warnings,
    }
    return {
        "ok": bool(samples),
        "mode": "setup_family_research",
        "summary": summary,
        "by_setup_family": by_family,
        "best_setups": by_family[:10],
        "bad_setups": [row for row in by_family if row.get("quality_label") == "bad"],
        "examples": {
            "best_setup_examples": examples_by_quality[:10],
            "bad_setup_examples": list(reversed(examples_by_quality[-10:])),
        },
        "limitations": [
            "Setup definitions are transparent heuristics, not production logic.",
            "Proxy backtest on daily candles; intraday target/stop ordering is simplified.",
            "Costs are simplified commission/slippage assumptions.",
            "Local universe can contain survivorship and coverage bias.",
            "Requires walk-forward and paper trading before production use.",
        ],
    }


def _config_grid(setup_family: str | None, max_configs: int) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    families = [setup_family] if setup_family else ["breakout", "pullback", "mean_reversion", "volatility_squeeze", "trend_following"]
    for family in families:
        if family == "breakout":
            for volume, dist in product([1.0, 1.1, 1.2], [1.0, 2.0, 3.0]):
                configs.append({"setup_family": family, "config": {"breakout_volume_ratio": volume, "breakout_dist_high_pct": dist}})
        elif family == "pullback":
            for floor in [-1.0, -2.0, -3.0]:
                configs.append({"setup_family": family, "config": {"pullback_ret_5_floor": floor}})
        elif family == "mean_reversion":
            for low in [1.0, 2.0, 3.0]:
                configs.append({"setup_family": family, "config": {"mean_reversion_dist_low_pct": low}})
        elif family == "volatility_squeeze":
            for vol in [2.0, 3.0, 4.0]:
                configs.append({"setup_family": family, "config": {"volatility_squeeze_max_volatility": vol}})
        elif family == "trend_following":
            configs.append({"setup_family": family, "config": {}})
    return configs[:max_configs]


def build_setup_family_parameter_sweep(
    db: Session,
    *,
    max_tickers: int = 80,
    max_samples: int = 3000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    setup_family: str | None = None,
    max_configs: int = 60,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_signals: int = 30,
) -> dict[str, Any]:
    samples, tickers_used, warnings, policy = _build_policy_samples(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    configs = _config_grid(setup_family, max_configs)
    results: list[dict[str, Any]] = []
    for index, item in enumerate(configs, start=1):
        family = str(item["setup_family"])
        config = dict(item.get("config") or {})
        rows = _candidate_rows(samples, config=config, setup_family_filter=family, max_setups=max_samples)
        metrics = _metrics_for_rows(rows, family=family, total_samples=max(1, len(samples)), min_signals=min_signals)
        row = {
            "config_id": f"{family}_{index}",
            "setup_family": family,
            "config": config,
            "samples": metrics.get("samples"),
            "coverage_pct": metrics.get("coverage_pct"),
            "avg_trade_return_pct": metrics.get("avg_trade_return_pct"),
            "profit_factor": metrics.get("profit_factor"),
            "win_rate_pct": metrics.get("win_rate_pct"),
            "stop_hit_rate_pct": metrics.get("stop_hit_rate_pct"),
            "quality_label": metrics.get("quality_label"),
        }
        row["score"] = score_setup_config_result(row, min_signals=min_signals)
        results.append(row)
    quality_rank = {"good": 4, "medium": 3, "weak": 2, "bad": 1, "unstable": 0}
    results.sort(
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label")), 0),
            _to_float(row.get("score")) if _to_float(row.get("score")) is not None else -999,
            _to_float(row.get("profit_factor")) if _to_float(row.get("profit_factor")) is not None else -999,
        ),
        reverse=True,
    )
    best = results[0] if results else None
    return {
        "ok": bool(samples),
        "mode": "setup_family_parameter_sweep",
        "summary": {
            "base_samples": len(samples),
            "tickers_used": len(tickers_used),
            "configs_tested": len(results),
            "best_setup_family": best.get("setup_family") if best else None,
            "best_config_id": best.get("config_id") if best else None,
            "best_quality_label": best.get("quality_label") if best else None,
            "policy": policy,
            "warnings": warnings,
        },
        "best_configs": results[:10],
        "results": results,
        "limitations": [
            "Small bounded parameter grid for research only.",
            "Proxy backtest on daily candles with simplified costs.",
            "Good configs require walk-forward and paper trading validation.",
        ],
    }
