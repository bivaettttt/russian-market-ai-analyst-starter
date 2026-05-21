from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics, simulate_trade_outcome
from app.services.consumer_signal_backtest_audit import _build_proxy_samples
from app.services.consumer_signals import _round, _to_float


DIMENSIONS = [
    "action",
    "ticker",
    "sector",
    "asset_type",
    "market_regime",
    "volatility_bucket",
    "liquidity_bucket",
    "probability_bucket",
    "ml_probability_bucket",
    "rr_bucket",
    "audit_confidence",
    "audit_final_verdict",
    "blocked_by",
    "news_effect",
    "macro_effect",
    "global_event_tags",
    "trade_policy_type",
]


def bucket_probability(value: float | None) -> str:
    number = _to_float(value)
    if number is None:
        return "unknown"
    if number < 40:
        return "<40"
    if number < 50:
        return "40-50"
    if number < 60:
        return "50-60"
    if number < 70:
        return "60-70"
    return ">=70"


def bucket_ml_probability(value: float | None) -> str:
    number = _to_float(value)
    if number is None:
        return "unknown"
    if number < 15:
        return "<15"
    if number < 25:
        return "15-25"
    if number < 35:
        return "25-35"
    return ">=35"


def bucket_rr(value: float | None) -> str:
    number = _to_float(value)
    if number is None:
        return "unknown"
    if number < 0.8:
        return "<0.8"
    if number < 1.0:
        return "0.8-1.0"
    if number < 1.2:
        return "1.0-1.2"
    if number < 1.5:
        return "1.2-1.5"
    return ">=1.5"


def bucket_volatility(value: float | None) -> str:
    number = _to_float(value)
    if number is None:
        return "unknown"
    if number < 1.4:
        return "low"
    if number < 2.4:
        return "medium"
    if number < 3.5:
        return "high"
    return "extreme"


def bucket_liquidity(value: float | None) -> str:
    number = _to_float(value)
    if number is None:
        return "unknown"
    if number < 0.7:
        return "low"
    if number < 1.3:
        return "medium"
    return "high"


def quality_label_for_bucket(metrics: dict[str, Any], min_bucket_samples: int) -> str:
    samples = int(metrics.get("samples") or 0)
    avg_trade_return = _to_float(metrics.get("avg_trade_return_pct"))
    profit_factor = _to_float(metrics.get("profit_factor"))
    if samples < min_bucket_samples:
        return "unstable"
    if avg_trade_return is not None and profit_factor is not None and avg_trade_return > 0 and profit_factor > 1.05:
        return "positive"
    if avg_trade_return is not None and profit_factor is not None and avg_trade_return < 0 and profit_factor < 0.95:
        return "negative"
    return "neutral"


def extract_sample_segments(sample: dict[str, Any]) -> dict[str, str | list[str]]:
    market_regime = sample.get("market_regime")
    if isinstance(market_regime, dict):
        market_regime_name = str(market_regime.get("regime") or sample.get("market_regime_name") or "unknown")
    else:
        market_regime_name = str(sample.get("market_regime_name") or sample.get("market_regime") or "unknown")

    blocked_by = sample.get("blocked_by") or ["none"]
    if not isinstance(blocked_by, list):
        blocked_by = [str(blocked_by)]
    blocked_by = [str(item or "unknown") for item in blocked_by] or ["none"]

    tags = sample.get("global_event_tags") or sample.get("global_news_tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = [str(item or "unknown") for item in tags] or ["none"]

    return {
        "action": str(sample.get("action") or "unknown"),
        "ticker": str(sample.get("ticker") or "unknown"),
        "sector": str(sample.get("sector") or "unknown"),
        "asset_type": str(sample.get("asset_type") or "unknown"),
        "market_regime": market_regime_name,
        "volatility_bucket": bucket_volatility(_to_float(sample.get("volatility_20d_pct") or sample.get("volatility_pct"))),
        "liquidity_bucket": bucket_liquidity(_to_float(sample.get("volume_ratio") or sample.get("liquidity_score"))),
        "probability_bucket": bucket_probability(_to_float(sample.get("probability_pct"))),
        "ml_probability_bucket": bucket_ml_probability(_to_float(sample.get("ml_probability_pct") or sample.get("proxy_ml_probability_pct"))),
        "rr_bucket": bucket_rr(_to_float(sample.get("risk_reward_ratio"))),
        "audit_confidence": str(sample.get("audit_confidence_level") or sample.get("audit_confidence") or "unknown"),
        "audit_final_verdict": str(sample.get("audit_final_verdict") or sample.get("recommendation") or "unknown"),
        "blocked_by": blocked_by,
        "news_effect": str(sample.get("news_effect") or "none"),
        "macro_effect": str(sample.get("macro_effect") or sample.get("global_event_effect") or "none"),
        "global_event_tags": tags,
        "trade_policy_type": str(sample.get("trade_policy_type") or sample.get("policy_type") or "fixed_pct"),
    }


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


def _add_sample(bucket: dict[str, Any], sample: dict[str, Any]) -> None:
    bucket["samples"] += 1
    if sample.get("outcome") == "target_hit":
        bucket["target_hits"] += 1
    elif sample.get("outcome") == "stop_hit":
        bucket["stop_hits"] += 1
    elif sample.get("outcome") == "timeout":
        bucket["timeouts"] += 1

    for key, target in [
        ("forward_return_pct", "forward_returns"),
        ("mfe_pct", "mfe_values"),
        ("mae_pct", "mae_values"),
    ]:
        value = _to_float(sample.get(key))
        if value is not None:
            bucket[target].append(value)
    if sample.get("trade_return_pct") is not None:
        bucket["trade_rows"].append(
            {
                "outcome": sample.get("outcome"),
                "trade_return_pct": sample.get("trade_return_pct"),
            }
        )


def _avg(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return _round(sum(clean) / len(clean), 2)


def _rate(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return _round(part / total * 100, 2)


def build_bucket_row(
    *,
    dimension: str,
    bucket: str,
    raw_bucket: dict[str, Any],
    total_samples: int,
    min_bucket_samples: int,
) -> dict[str, Any]:
    samples = int(raw_bucket.get("samples") or 0)
    pnl = aggregate_trade_pnl_metrics(raw_bucket.get("trade_rows") or [])
    row = {
        "dimension": dimension,
        "bucket": str(bucket),
        "samples": samples,
        "coverage_pct": _rate(samples, total_samples) or 0.0,
        "target_hit_rate_pct": _rate(int(raw_bucket.get("target_hits") or 0), samples),
        "stop_hit_rate_pct": _rate(int(raw_bucket.get("stop_hits") or 0), samples),
        "timeout_rate_pct": _rate(int(raw_bucket.get("timeouts") or 0), samples),
        "avg_forward_return_pct": _avg(raw_bucket.get("forward_returns") or []),
        "avg_mfe_pct": _avg(raw_bucket.get("mfe_values") or []),
        "avg_mae_pct": _avg(raw_bucket.get("mae_values") or []),
        **pnl,
    }
    row["quality_label"] = quality_label_for_bucket(row, min_bucket_samples)
    row["diagnostic"] = _diagnostic(row, min_bucket_samples)
    return row


def _diagnostic(row: dict[str, Any], min_bucket_samples: int) -> str:
    samples = int(row.get("samples") or 0)
    if samples < min_bucket_samples:
        return f"Unstable estimate: only {samples} samples, below min_bucket_samples={min_bucket_samples}."
    label = row.get("quality_label")
    avg_trade = row.get("avg_trade_return_pct")
    profit_factor = row.get("profit_factor")
    stop_hit = row.get("stop_hit_rate_pct")
    if label == "positive":
        return f"Positive expectancy pocket: avg trade {avg_trade}%, profit factor {profit_factor}."
    if label == "negative":
        return f"Negative expectancy pocket: avg trade {avg_trade}%, profit factor {profit_factor}, stop-hit {stop_hit}%."
    return "Mixed/neutral bucket; no strong filter or boost recommendation."


def _example(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": sample.get("ticker"),
        "date": sample.get("date"),
        "action": sample.get("action"),
        "sector": sample.get("sector"),
        "asset_type": sample.get("asset_type"),
        "market_regime": sample.get("market_regime_name"),
        "probability_pct": sample.get("probability_pct"),
        "risk_reward_ratio": sample.get("risk_reward_ratio"),
        "outcome": sample.get("outcome"),
        "trade_return_pct": sample.get("trade_return_pct"),
        "forward_return_pct": sample.get("forward_return_pct"),
        "mfe_pct": sample.get("mfe_pct"),
        "mae_pct": sample.get("mae_pct"),
    }


def _recommend_filter(row: dict[str, Any]) -> dict[str, Any]:
    avg_trade = _to_float(row.get("avg_trade_return_pct")) or 0.0
    samples = int(row.get("samples") or 0)
    return {
        "rule": f"exclude {row.get('dimension')}={row.get('bucket')}",
        "dimension": row.get("dimension"),
        "bucket": row.get("bucket"),
        "reason": row.get("diagnostic"),
        "samples": samples,
        "avg_trade_return_pct": row.get("avg_trade_return_pct"),
        "profit_factor": row.get("profit_factor"),
        "estimated_removed_loss_pct": _round(abs(min(avg_trade, 0.0)) * samples, 2),
    }


def _recommend_boost(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule": f"prefer {row.get('dimension')}={row.get('bucket')}",
        "dimension": row.get("dimension"),
        "bucket": row.get("bucket"),
        "reason": row.get("diagnostic"),
        "samples": row.get("samples"),
        "avg_trade_return_pct": row.get("avg_trade_return_pct"),
        "profit_factor": row.get("profit_factor"),
    }


def _with_trade_outcomes(
    samples: list[dict[str, Any]],
    *,
    horizon: int,
    target_pct: float,
    stop_pct: float,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    enriched: list[dict[str, Any]] = []
    for sample in samples:
        close = _to_float(sample.get("close"))
        future = sample.get("future") if isinstance(sample.get("future"), list) else None
        if close is None or close <= 0 or not future:
            warnings.append("Some samples had no close/future candles and reused proxy outcome fields.")
            enriched.append(sample)
            continue
        outcome = simulate_trade_outcome(
            entry_price=close,
            target_price=close * (1 + target_pct),
            stop_price=close * (1 - stop_pct),
            future_candles=future[:horizon],
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        )
        enriched.append(
            {
                **sample,
                "outcome": outcome.get("outcome"),
                "success": outcome.get("success"),
                "days_to_outcome": outcome.get("days_to_outcome"),
                "forward_return_pct": outcome.get("forward_return_pct"),
                "trade_return_pct": outcome.get("trade_return_pct"),
                "gross_trade_return_pct": outcome.get("gross_trade_return_pct"),
                "cost_pct": outcome.get("cost_pct"),
                "target_return_pct": outcome.get("target_return_pct"),
                "stop_return_pct": outcome.get("stop_return_pct"),
                "mfe_pct": outcome.get("mfe_pct"),
                "mae_pct": outcome.get("mae_pct"),
            }
        )
    return enriched, sorted(set(warnings))


def build_expectancy_breakdown(
    db: Session,
    max_tickers: int = 100,
    max_samples: int = 3000,
    horizon: int = 20,
    target_pct: float = 0.05,
    stop_pct: float = 0.03,
    min_history: int = 80,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    min_bucket_samples: int = 20,
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
        commission_bps=0.0,
        slippage_bps=0.0,
    )
    samples, outcome_warnings = _with_trade_outcomes(
        samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )

    total_samples = len(samples)
    raw_dimensions: dict[str, dict[str, dict[str, Any]]] = {
        dimension: defaultdict(_empty_bucket) for dimension in DIMENSIONS
    }
    summary_bucket = _empty_bucket()
    for sample in samples:
        _add_sample(summary_bucket, sample)
        segments = extract_sample_segments(sample)
        for dimension in DIMENSIONS:
            value = segments.get(dimension, "unknown")
            buckets = value if isinstance(value, list) else [value]
            for bucket in buckets:
                _add_sample(raw_dimensions[dimension][str(bucket or "unknown")], sample)

    summary_metrics = build_bucket_row(
        dimension="summary",
        bucket="all",
        raw_bucket=summary_bucket,
        total_samples=total_samples,
        min_bucket_samples=1,
    )
    summary = {
        "samples": total_samples,
        "tickers_used": len(tickers_used),
        "horizon": horizon,
        "target_pct": target_pct,
        "stop_pct": stop_pct,
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "avg_trade_return_pct": summary_metrics.get("avg_trade_return_pct"),
        "win_rate_pct": summary_metrics.get("win_rate_pct"),
        "profit_factor": summary_metrics.get("profit_factor"),
        "expectancy_pct": summary_metrics.get("expectancy_pct"),
        "target_hit_rate_pct": summary_metrics.get("target_hit_rate_pct"),
        "stop_hit_rate_pct": summary_metrics.get("stop_hit_rate_pct"),
        "timeout_rate_pct": summary_metrics.get("timeout_rate_pct"),
    }

    dimensions: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []
    for dimension, bucket_map in raw_dimensions.items():
        rows = [
            build_bucket_row(
                dimension=dimension,
                bucket=bucket,
                raw_bucket=raw_bucket,
                total_samples=total_samples,
                min_bucket_samples=min_bucket_samples,
            )
            for bucket, raw_bucket in bucket_map.items()
        ]
        rows.sort(
            key=lambda row: (
                row.get("quality_label") == "positive",
                _to_float(row.get("avg_trade_return_pct")) or -999,
                _to_float(row.get("profit_factor")) or -999,
                int(row.get("samples") or 0),
            ),
            reverse=True,
        )
        dimensions[dimension] = rows
        all_rows.extend(rows)

    positive_pockets = sorted(
        [row for row in all_rows if row.get("quality_label") == "positive"],
        key=lambda row: (_to_float(row.get("avg_trade_return_pct")) or -999, _to_float(row.get("profit_factor")) or -999, int(row.get("samples") or 0)),
        reverse=True,
    )[:30]
    negative_pockets = sorted(
        [row for row in all_rows if row.get("quality_label") == "negative"],
        key=lambda row: (_to_float(row.get("avg_trade_return_pct")) or 999, _to_float(row.get("profit_factor")) or 999, -int(row.get("samples") or 0)),
    )[:30]

    limitations = [
        "Expectancy breakdown is a research diagnostic layer and does not change production consumer signal logic.",
        "Historical evaluation is proxy candle-only and does not replay real saved consumer signal snapshots.",
        "Ticker news and global macro/geopolitical events are not replayed historically; related buckets are usually none/unknown.",
        "Daily candles do not provide intraday high/low order; if target and stop are both touched in one candle, stop_hit is assumed.",
        "Costs are simplified bps inputs and do not include taxes, borrow, market impact or partial fills.",
        "Current instrument universe can introduce survivorship bias.",
        "Small buckets are marked unstable and should not be used as strong recommendations.",
    ]
    if total_samples < min_bucket_samples:
        limitations.append("Total sample count is below min_bucket_samples; all bucket diagnostics are unstable.")
    if total_samples == 0:
        limitations.append("No historical samples were built. Check /signals/data-coverage to diagnose instrument and candle coverage.")
    limitations.extend(outcome_warnings)

    top_positive_examples = sorted(samples, key=lambda item: _to_float(item.get("trade_return_pct")) or -999, reverse=True)[:10]
    top_negative_examples = sorted(samples, key=lambda item: _to_float(item.get("trade_return_pct")) or 999)[:10]

    return {
        "ok": True,
        "mode": "expectancy_breakdown",
        "summary": summary,
        "dimensions": dimensions,
        "positive_pockets": positive_pockets,
        "negative_pockets": negative_pockets,
        "candidate_filters": [_recommend_filter(row) for row in negative_pockets[:15]],
        "candidate_boosts": [_recommend_boost(row) for row in positive_pockets[:15]],
        "examples": {
            "top_positive": [_example(item) for item in top_positive_examples],
            "top_negative": [_example(item) for item in top_negative_examples],
        },
        "limitations": limitations,
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
        },
    }
