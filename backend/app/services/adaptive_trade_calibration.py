from __future__ import annotations

from itertools import product
from statistics import mean, median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument
from app.services.consumer_signals import _round, _to_float


DEFAULT_TRADE_POLICY: dict[str, Any] = {
    "policy_type": "fixed_pct",
    "target_pct": 0.05,
    "stop_pct": 0.03,
    "horizon": 20,
    "min_rr": 1.0,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous * 100


def _rate(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return _round(part / total * 100, 2)


def _avg(values: list[float]) -> float | None:
    return _round(mean(values), 2) if values else None


def _candle_to_dict(candle: Candle) -> dict[str, Any]:
    return {
        "ticker": candle.ticker,
        "trade_date": candle.trade_date.isoformat() if candle.trade_date else None,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "value": candle.value,
    }


def normalize_trade_policy(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(DEFAULT_TRADE_POLICY)
    if isinstance(policy, dict):
        raw.update({key: value for key, value in policy.items() if value is not None})

    policy_type = str(raw.get("policy_type") or "fixed_pct")
    if policy_type not in {"fixed_pct", "atr_multiple", "volatility_scaled", "conservative_liquid", "high_volatility_wide_stop"}:
        policy_type = "fixed_pct"

    normalized = {
        "policy_type": policy_type,
        "horizon": int(_clamp(_to_float(raw.get("horizon")) or 20, 5, 90)),
        "min_rr": _round(_clamp(_to_float(raw.get("min_rr")) or 1.0, 0.1, 5.0), 3),
    }

    for key, default, low, high in [
        ("target_pct", 0.05, 0.005, 0.25),
        ("stop_pct", 0.03, 0.005, 0.20),
        ("target_atr_mult", 2.0, 0.2, 8.0),
        ("stop_atr_mult", 1.2, 0.2, 8.0),
        ("target_vol_mult", 1.5, 0.2, 5.0),
        ("stop_vol_mult", 0.9, 0.2, 5.0),
        ("min_target_pct", 0.025, 0.005, 0.25),
        ("max_target_pct", 0.08, 0.005, 0.25),
        ("min_stop_pct", 0.015, 0.005, 0.20),
        ("max_stop_pct", 0.05, 0.005, 0.20),
    ]:
        normalized[key] = _round(_clamp(_to_float(raw.get(key)) or default, low, high), 4)

    for key in ["liquidity_bucket", "volatility_bucket", "sector_bucket"]:
        if raw.get(key):
            normalized[key] = str(raw.get(key))

    if normalized["max_target_pct"] < normalized["min_target_pct"]:
        normalized["max_target_pct"] = normalized["min_target_pct"]
    if normalized["max_stop_pct"] < normalized["min_stop_pct"]:
        normalized["max_stop_pct"] = normalized["min_stop_pct"]

    return normalized


def _atr_pct(candles: list[dict[str, Any]], close: float, period: int = 14) -> float | None:
    if close <= 0 or len(candles) < period + 1:
        return None
    ranges: list[float] = []
    window = candles[-(period + 1) :]
    for previous, current in zip(window[:-1], window[1:]):
        prev_close = _to_float(previous.get("close"))
        high = _to_float(current.get("high"))
        low = _to_float(current.get("low"))
        if prev_close is None or high is None or low is None:
            continue
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    if not ranges:
        return None
    return mean(ranges) / close * 100


def _volatility_pct(candles: list[dict[str, Any]], period: int = 20) -> float | None:
    closes = [_to_float(row.get("close")) for row in candles if _to_float(row.get("close")) is not None]
    if len(closes) < period + 1:
        return None
    returns = []
    for previous, current in zip(closes[-(period + 1) : -1], closes[-period:]):
        if previous:
            returns.append((current - previous) / previous * 100)
    if len(returns) < 2:
        return None
    avg = mean(returns)
    variance = sum((item - avg) ** 2 for item in returns) / (len(returns) - 1)
    return variance ** 0.5


def _bucket_volatility(volatility_pct: float | None) -> str:
    if volatility_pct is None:
        return "unknown"
    if volatility_pct < 2:
        return "low"
    if volatility_pct < 4:
        return "medium"
    if volatility_pct < 7:
        return "high"
    return "extreme"


def _bucket_liquidity(candles: list[dict[str, Any]]) -> str:
    values = [_to_float(row.get("value")) for row in candles[-20:] if _to_float(row.get("value")) is not None]
    if not values:
        return "unknown"
    avg_value = mean(values)
    if avg_value >= 500_000_000:
        return "high"
    if avg_value >= 50_000_000:
        return "medium"
    return "low"


def compute_trade_setup(
    *,
    close: float,
    candles: list[dict[str, Any]],
    policy: dict[str, Any],
    instrument: dict[str, Any] | None = None,
    market_regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_trade_policy(policy)
    warnings: list[str] = []
    atr_pct = _atr_pct(candles, close)
    volatility_pct = _volatility_pct(candles)
    liquidity_bucket = _bucket_liquidity(candles)
    volatility_bucket = _bucket_volatility(volatility_pct)
    sector_bucket = str((instrument or {}).get("sector") or "unknown")
    regime = str((market_regime or {}).get("regime") or "unknown")

    policy_type = normalized["policy_type"]
    target_pct = _to_float(normalized.get("target_pct")) or 0.05
    stop_pct = _to_float(normalized.get("stop_pct")) or 0.03
    reason = "Fixed percentage target/stop."

    if policy_type == "atr_multiple":
        if atr_pct is None:
            warnings.append("atr_unavailable_used_fixed_fallback")
        else:
            target_pct = atr_pct / 100 * float(normalized["target_atr_mult"])
            stop_pct = atr_pct / 100 * float(normalized["stop_atr_mult"])
            reason = "ATR multiple target/stop based on recent true range."
    elif policy_type == "volatility_scaled":
        if volatility_pct is None:
            warnings.append("volatility_unavailable_used_fixed_fallback")
        else:
            target_pct = _clamp(
                volatility_pct / 100 * float(normalized["target_vol_mult"]),
                float(normalized["min_target_pct"]),
                float(normalized["max_target_pct"]),
            )
            stop_pct = _clamp(
                volatility_pct / 100 * float(normalized["stop_vol_mult"]),
                float(normalized["min_stop_pct"]),
                float(normalized["max_stop_pct"]),
            )
            reason = "Volatility-scaled target/stop with min/max clamps."
    elif policy_type == "conservative_liquid":
        if liquidity_bucket != "high":
            warnings.append("liquidity_bucket_not_high")
        reason = "Conservative liquid bucket fixed target/stop."
    elif policy_type == "high_volatility_wide_stop":
        if volatility_bucket not in {"high", "extreme"}:
            warnings.append("volatility_bucket_not_high")
        reason = "Wide stop policy for high volatility bucket."

    if regime == "risk_off":
        target_pct *= 0.9
        stop_pct *= 0.9
        reason += " Risk-off regime trims target and stop modestly for evaluation."
    elif regime == "risk_on":
        target_pct *= 1.05
        reason += " Risk-on regime allows a slightly wider target for evaluation."

    target_pct = _clamp(target_pct, 0.005, 0.25)
    stop_pct = _clamp(stop_pct, 0.005, 0.20)
    risk_reward_ratio = target_pct / stop_pct if stop_pct > 0 else None

    return {
        "ok": True,
        "policy_type": policy_type,
        "entry_price": _round(close, 4),
        "target_price": _round(close * (1 + target_pct), 4),
        "stop_price": _round(close * (1 - stop_pct), 4),
        "target_pct": _round(target_pct * 100, 2),
        "stop_pct": _round(stop_pct * 100, 2),
        "target_pct_decimal": _round(target_pct, 5),
        "stop_pct_decimal": _round(stop_pct, 5),
        "horizon": int(normalized["horizon"]),
        "risk_reward_ratio": _round(risk_reward_ratio, 2),
        "atr_pct": _round(atr_pct, 2),
        "volatility_pct": _round(volatility_pct, 2),
        "liquidity_bucket": liquidity_bucket,
        "volatility_bucket": volatility_bucket,
        "sector_bucket": sector_bucket,
        "regime": regime,
        "warnings": warnings,
        "reason": reason,
    }


def simulate_trade_outcome(
    *,
    entry_price: float,
    target_price: float,
    stop_price: float,
    future_candles: list[dict[str, Any]],
    conservative_same_candle: bool = True,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict[str, Any]:
    warnings: list[str] = []
    entry = _to_float(entry_price)
    target = _to_float(target_price)
    stop = _to_float(stop_price)
    cost_pct = max(0.0, (_to_float(commission_bps) or 0.0) + (_to_float(slippage_bps) or 0.0)) / 100.0
    if entry is None or entry <= 0 or target is None or stop is None:
        return {
            "outcome": "no_data",
            "success": None,
            "days_to_outcome": None,
            "exit_price": None,
            "trade_return_pct": None,
            "gross_trade_return_pct": None,
            "cost_pct": _round(cost_pct, 4),
            "target_return_pct": None,
            "stop_return_pct": None,
            "forward_return_pct": None,
            "mfe_pct": None,
            "mae_pct": None,
            "same_candle_conflict": False,
            "warnings": ["invalid_trade_prices"],
        }
    target_return_pct = (target / entry - 1) * 100
    stop_return_pct = (stop / entry - 1) * 100
    if not future_candles:
        return {
            "outcome": "no_data",
            "success": None,
            "days_to_outcome": None,
            "exit_price": None,
            "trade_return_pct": None,
            "gross_trade_return_pct": None,
            "cost_pct": _round(cost_pct, 4),
            "target_return_pct": _round(target_return_pct, 2),
            "stop_return_pct": _round(stop_return_pct, 2),
            "forward_return_pct": None,
            "mfe_pct": None,
            "mae_pct": None,
            "same_candle_conflict": False,
            "warnings": ["no_future_candles"],
        }

    max_high = entry
    min_low = entry
    outcome = "timeout"
    gross_trade_return_pct = None
    exit_price = None
    days_to_outcome = len(future_candles)
    same_candle_conflict = False

    for day, candle in enumerate(future_candles, start=1):
        high = _to_float(candle.get("high")) or entry
        low = _to_float(candle.get("low")) or entry
        max_high = max(max_high, high)
        min_low = min(min_low, low)
        hit_target = high >= target
        hit_stop = low <= stop
        if hit_target and hit_stop:
            same_candle_conflict = True
            outcome = "stop_hit" if conservative_same_candle else "target_hit"
            days_to_outcome = day
            gross_trade_return_pct = stop_return_pct if conservative_same_candle else target_return_pct
            exit_price = stop if conservative_same_candle else target
            break
        if hit_stop:
            outcome = "stop_hit"
            days_to_outcome = day
            gross_trade_return_pct = stop_return_pct
            exit_price = stop
            break
        if hit_target:
            outcome = "target_hit"
            days_to_outcome = day
            gross_trade_return_pct = target_return_pct
            exit_price = target
            break

    last_close = _to_float(future_candles[-1].get("close"))
    forward_return_pct = _pct_change(last_close, entry)
    if outcome == "timeout":
        exit_price = last_close
        gross_trade_return_pct = forward_return_pct

    trade_return_pct = (
        gross_trade_return_pct - cost_pct
        if gross_trade_return_pct is not None
        else None
    )
    return {
        "outcome": outcome,
        "success": bool(trade_return_pct is not None and trade_return_pct > 0),
        "days_to_outcome": days_to_outcome,
        "exit_price": _round(exit_price, 4),
        "trade_return_pct": _round(trade_return_pct, 2),
        "gross_trade_return_pct": _round(gross_trade_return_pct, 2),
        "cost_pct": _round(cost_pct, 4),
        "target_return_pct": _round(target_return_pct, 2),
        "stop_return_pct": _round(stop_return_pct, 2),
        "forward_return_pct": _round(forward_return_pct, 2),
        "mfe_pct": _round(_pct_change(max_high, entry), 2),
        "mae_pct": _round(_pct_change(min_low, entry), 2),
        "same_candle_conflict": same_candle_conflict,
        "warnings": warnings,
    }


def aggregate_trade_pnl_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [_to_float(row.get("trade_return_pct")) for row in rows]
    returns = [value for value in returns if value is not None]
    trades = len(returns)
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    target_hits = sum(1 for row in rows if row.get("outcome") == "target_hit")
    stop_hits = sum(1 for row in rows if row.get("outcome") == "stop_hit")
    timeouts = sum(1 for row in rows if row.get("outcome") == "timeout")
    gross_gains = sum(wins)
    gross_losses = abs(sum(losses))
    avg_win = _avg(wins)
    avg_loss = _avg(losses)
    profit_factor = gross_gains / gross_losses if gross_losses > 0 and wins else None
    payoff_ratio = (
        avg_win / abs(avg_loss)
        if avg_win is not None and avg_loss is not None and avg_loss < 0
        else None
    )
    return {
        "trades": trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": _rate(len(wins), trades),
        "loss_rate_pct": _rate(len(losses), trades),
        "avg_trade_return_pct": _avg(returns),
        "median_trade_return_pct": _round(median(returns), 2) if returns else None,
        "total_trade_return_pct": _round(sum(returns), 2) if returns else None,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "profit_factor": _round(profit_factor, 3),
        "expectancy_pct": _avg(returns),
        "payoff_ratio": _round(payoff_ratio, 3),
        "max_trade_loss_pct": _round(min(returns), 2) if returns else None,
        "target_hit_rate_pct": _rate(target_hits, len(rows)),
        "stop_hit_rate_pct": _rate(stop_hits, len(rows)),
        "timeout_rate_pct": _rate(timeouts, len(rows)),
    }


def _generate_trade_policies(max_policies: int) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    policies: list[dict[str, Any]] = [
        {"policy_type": "fixed_pct", "target_pct": 0.03, "stop_pct": 0.02, "horizon": 15, "min_rr": rr}
        for rr in [0.8, 1.0, 1.2, 1.5]
    ] + [
        {"policy_type": "fixed_pct", "target_pct": 0.04, "stop_pct": 0.025, "horizon": 20, "min_rr": rr}
        for rr in [0.8, 1.0, 1.2, 1.5]
    ] + [
        {"policy_type": "fixed_pct", "target_pct": 0.05, "stop_pct": 0.03, "horizon": 20, "min_rr": rr}
        for rr in [0.8, 1.0, 1.2, 1.5]
    ] + [
        {"policy_type": "fixed_pct", "target_pct": 0.06, "stop_pct": 0.04, "horizon": 30, "min_rr": rr}
        for rr in [0.8, 1.0, 1.2, 1.5]
    ]

    for target_mult, stop_mult, horizon, rr in product([1.5, 2.0, 2.5, 3.0], [0.9, 1.1, 1.3, 1.6], [15, 20, 30], [0.8, 1.0, 1.2, 1.5]):
        policies.append({"policy_type": "atr_multiple", "target_atr_mult": target_mult, "stop_atr_mult": stop_mult, "horizon": horizon, "min_rr": rr})
    for target_mult, stop_mult, horizon, rr in product([1.2, 1.5, 1.8], [0.8, 1.0, 1.2], [15, 20, 30], [0.8, 1.0, 1.2, 1.5]):
        policies.append({"policy_type": "volatility_scaled", "target_vol_mult": target_mult, "stop_vol_mult": stop_mult, "horizon": horizon, "min_rr": rr})
    policies.extend(
        [
            {"policy_type": "conservative_liquid", "target_pct": 0.035, "stop_pct": 0.025, "horizon": 15, "min_rr": 1.2, "liquidity_bucket": "high"},
            {"policy_type": "high_volatility_wide_stop", "target_pct": 0.07, "stop_pct": 0.045, "horizon": 30, "min_rr": 1.3, "volatility_bucket": "high"},
        ]
    )

    total = len(policies)
    if total > max_policies:
        warnings.append(f"Policy grid truncated from {total} to {max_policies} policies for runtime protection.")
        baseline = DEFAULT_TRADE_POLICY
        remaining_slots = max(0, max_policies - 1)
        step = total / remaining_slots if remaining_slots else total
        sampled = [policies[min(total - 1, int(index * step))] for index in range(remaining_slots)]
        policies = [baseline, *sampled]
    return [normalize_trade_policy(policy) for policy in policies], warnings


def _policy_id(policy: dict[str, Any]) -> str:
    policy_type = str(policy.get("policy_type"))
    horizon = int(policy.get("horizon") or 0)
    min_rr = str(float(policy.get("min_rr") or 0)).replace(".", "_")
    if policy_type == "atr_multiple":
        return f"atr_t{policy.get('target_atr_mult')}_s{policy.get('stop_atr_mult')}_h{horizon}_rr{min_rr}".replace(".", "_")
    if policy_type == "volatility_scaled":
        return f"vol_t{policy.get('target_vol_mult')}_s{policy.get('stop_vol_mult')}_h{horizon}_rr{min_rr}".replace(".", "_")
    return f"{policy_type}_t{int(round(float(policy.get('target_pct') or 0) * 1000))}_s{int(round(float(policy.get('stop_pct') or 0) * 1000))}_h{horizon}_rr{min_rr}"


def score_trade_policy_metrics(metrics: dict[str, Any], *, min_samples_per_policy: int) -> float:
    samples = int(metrics.get("samples") or 0)
    coverage = _to_float(metrics.get("coverage_pct")) or 0.0
    target_hit = _to_float(metrics.get("target_hit_rate_pct")) or 0.0
    stop_hit = _to_float(metrics.get("stop_hit_rate_pct")) or 0.0
    avg_trade_return = _to_float(metrics.get("avg_trade_return_pct")) or 0.0
    win_rate = _to_float(metrics.get("win_rate_pct")) or 0.0
    profit_factor = _to_float(metrics.get("profit_factor"))
    avg_loss = abs(_to_float(metrics.get("avg_loss_pct")) or 0.0)

    score = 0.0
    score += avg_trade_return * 8.0
    score += win_rate * 0.4
    if profit_factor is not None:
        score += min(profit_factor, 3.0) * 5.0
    score -= stop_hit * 0.4
    score += target_hit * 0.4
    score -= avg_loss * 1.0
    if samples < min_samples_per_policy:
        score -= 30.0
    if coverage < 5.0:
        score -= 15.0
    if samples >= 100:
        score += 5.0
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _quality_label(score: float, samples: int, min_samples_per_policy: int) -> str:
    if samples < min_samples_per_policy:
        return "unstable"
    if score >= 25:
        return "good"
    if score >= 10:
        return "medium"
    return "weak"


def _evaluate_policy(
    *,
    base_samples: list[dict[str, Any]],
    policy: dict[str, Any],
    min_samples_per_policy: int,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    rejected_by_min_rr = 0
    setup_warnings: set[str] = set()
    for sample in base_samples:
        setup = compute_trade_setup(
            close=float(sample["close"]),
            candles=sample["history"],
            policy=policy,
            instrument=sample.get("instrument"),
            market_regime=sample.get("market_regime"),
        )
        rr = _to_float(setup.get("risk_reward_ratio"))
        if rr is None or rr < float(policy.get("min_rr") or 0):
            rejected_by_min_rr += 1
            continue
        for warning in setup.get("warnings") or []:
            setup_warnings.add(str(warning))
        outcome = simulate_trade_outcome(
            entry_price=float(sample["close"]),
            target_price=float(setup["target_price"]),
            stop_price=float(setup["stop_price"]),
            future_candles=sample["future"][: int(setup.get("horizon") or 20)],
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        )
        selected.append({"setup": setup, "outcome": outcome})

    samples = len(selected)
    target_hits = sum(1 for item in selected if item["outcome"].get("outcome") == "target_hit")
    stop_hits = sum(1 for item in selected if item["outcome"].get("outcome") == "stop_hit")
    timeouts = sum(1 for item in selected if item["outcome"].get("outcome") == "timeout")
    returns = [_to_float(item["outcome"].get("forward_return_pct")) for item in selected]
    returns = [value for value in returns if value is not None]
    mfe = [_to_float(item["outcome"].get("mfe_pct")) for item in selected]
    mfe = [value for value in mfe if value is not None]
    mae = [_to_float(item["outcome"].get("mae_pct")) for item in selected]
    mae = [value for value in mae if value is not None]
    targets = [_to_float(item["setup"].get("target_pct")) for item in selected]
    targets = [value for value in targets if value is not None]
    stops = [_to_float(item["setup"].get("stop_pct")) for item in selected]
    stops = [value for value in stops if value is not None]
    rrs = [_to_float(item["setup"].get("risk_reward_ratio")) for item in selected]
    rrs = [value for value in rrs if value is not None]
    pnl_metrics = aggregate_trade_pnl_metrics(
        [
            {
                "outcome": item["outcome"].get("outcome"),
                "trade_return_pct": item["outcome"].get("trade_return_pct"),
            }
            for item in selected
        ]
    )

    metrics = {
        "rank": None,
        "policy_id": _policy_id(policy),
        "policy": policy,
        "samples": samples,
        "coverage_pct": _rate(samples, len(base_samples)) or 0.0,
        "target_hit_rate_pct": _rate(target_hits, samples),
        "stop_hit_rate_pct": _rate(stop_hits, samples),
        "timeout_rate_pct": _rate(timeouts, samples),
        "avg_forward_return_pct": _avg(returns),
        "median_forward_return_pct": _round(median(returns), 2) if returns else None,
        "avg_mfe_pct": _avg(mfe),
        "avg_mae_pct": _avg(mae),
        "avg_target_pct": _avg(targets),
        "avg_stop_pct": _avg(stops),
        "avg_rr": _avg(rrs),
        "rejected_by_min_rr": rejected_by_min_rr,
        "avg_trade_return_pct": pnl_metrics.get("avg_trade_return_pct"),
        "median_trade_return_pct": pnl_metrics.get("median_trade_return_pct"),
        "total_trade_return_pct": pnl_metrics.get("total_trade_return_pct"),
        "win_rate_pct": pnl_metrics.get("win_rate_pct"),
        "loss_rate_pct": pnl_metrics.get("loss_rate_pct"),
        "profit_factor": pnl_metrics.get("profit_factor"),
        "expectancy_pct": pnl_metrics.get("expectancy_pct"),
        "payoff_ratio": pnl_metrics.get("payoff_ratio"),
        "avg_win_pct": pnl_metrics.get("avg_win_pct"),
        "avg_loss_pct": pnl_metrics.get("avg_loss_pct"),
        "max_trade_loss_pct": pnl_metrics.get("max_trade_loss_pct"),
        "target_trade_return_pct": _avg(targets),
        "stop_trade_return_pct": _round(-(_avg(stops) or 0.0), 2) if stops else None,
        "warnings": sorted(setup_warnings),
    }
    score = score_trade_policy_metrics(metrics, min_samples_per_policy=min_samples_per_policy)
    metrics["score"] = score
    metrics["quality_label"] = _quality_label(score, samples, min_samples_per_policy)
    if samples < min_samples_per_policy:
        metrics["warnings"].append("samples below min_samples_per_policy; estimate is unstable")
    return metrics


def _build_base_samples(
    *,
    db: Session,
    max_tickers: int,
    max_samples: int,
    min_history: int,
) -> tuple[list[dict[str, Any]], set[str]]:
    instruments = db.scalars(
        select(Instrument)
        .where(Instrument.is_signal_eligible.is_(True))
        .where(Instrument.asset_type.in_(["stock", "share", "equity", "unknown"]))
        .order_by(Instrument.ticker.asc())
        .limit(max_tickers)
    ).all()
    if not instruments:
        instruments = db.scalars(
            select(Instrument)
            .where(Instrument.asset_type.in_(["stock", "share", "equity", "unknown"]))
            .order_by(Instrument.ticker.asc())
            .limit(max_tickers)
        ).all()

    max_horizon = 90
    per_ticker_cap = max(1, max_samples // max(1, len(instruments)))
    samples: list[dict[str, Any]] = []
    tickers_used: set[str] = set()

    for instrument in instruments:
        if len(samples) >= max_samples:
            break
        candles = [
            _candle_to_dict(row)
            for row in db.scalars(
                select(Candle)
                .where(Candle.ticker == instrument.ticker)
                .order_by(Candle.trade_date.asc())
            ).all()
            if row.close is not None
        ]
        if len(candles) < min_history + max_horizon + 1:
            continue
        max_index = len(candles) - max_horizon - 1
        indexes = list(range(min_history - 1, max_index + 1))
        if not indexes:
            continue
        step = max(1, len(indexes) // per_ticker_cap)
        for index in indexes[::step][:per_ticker_cap]:
            if len(samples) >= max_samples:
                break
            close = _to_float(candles[index].get("close"))
            if close is None or close <= 0:
                continue
            history = candles[: index + 1]
            future = candles[index + 1 : index + 1 + max_horizon]
            ret20 = _pct_change(close, _to_float(candles[index - 20].get("close")) if index >= 20 else None)
            regime = "risk_off" if ret20 is not None and ret20 < -5 else "risk_on" if ret20 is not None and ret20 > 5 else "neutral"
            samples.append(
                {
                    "ticker": instrument.ticker,
                    "date": candles[index].get("trade_date"),
                    "close": close,
                    "history": history,
                    "current": candles[index],
                    "future": future,
                    "instrument": {"ticker": instrument.ticker, "sector": instrument.sector, "asset_type": instrument.asset_type},
                    "market_regime": {"regime": regime},
                }
            )
            tickers_used.add(instrument.ticker)
    return samples, tickers_used


def _delta(left: Any, right: Any) -> float | None:
    left_value = _to_float(left)
    right_value = _to_float(right)
    if left_value is None or right_value is None:
        return None
    return _round(left_value - right_value, 2)


def _recommendation(best: dict[str, Any] | None, baseline: dict[str, Any] | None, min_samples: int) -> str:
    if not best or int(best.get("samples") or 0) < min_samples:
        return "insufficient_data"
    if baseline and best.get("policy_id") == baseline.get("policy_id"):
        return "keep_current"
    stop_delta = _delta(best.get("stop_hit_rate_pct"), (baseline or {}).get("stop_hit_rate_pct"))
    trade_delta = _delta(best.get("avg_trade_return_pct"), (baseline or {}).get("avg_trade_return_pct"))
    win_delta = _delta(best.get("win_rate_pct"), (baseline or {}).get("win_rate_pct"))
    profit_factor_delta = _delta(best.get("profit_factor"), (baseline or {}).get("profit_factor"))
    score = _to_float(best.get("score")) or 0.0
    if (
        score >= 25
        and stop_delta is not None
        and stop_delta <= -2.0
        and (trade_delta or 0) > 0
        and ((win_delta or 0) >= 0 or (profit_factor_delta or 0) > 0)
    ):
        return "promising"
    if baseline and (_to_float(baseline.get("score")) or -999) >= score:
        return "keep_current"
    return "recalibrate_needed"


def build_adaptive_trade_calibration(
    db: Session,
    max_tickers: int = 80,
    max_samples: int = 2000,
    max_policies: int = 80,
    min_samples_per_policy: int = 30,
    min_history: int = 80,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict[str, Any]:
    base_samples, tickers_used = _build_base_samples(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
    )
    policies, warnings = _generate_trade_policies(max_policies=max_policies)
    if len(base_samples) < min_samples_per_policy:
        warnings.append("Base sample count is below min_samples_per_policy; calibration is unstable.")
    if not base_samples:
        warnings.append("No historical samples were built. Check /signals/data-coverage to diagnose instrument and candle coverage.")

    results = [
        _evaluate_policy(
            base_samples=base_samples,
            policy=policy,
            min_samples_per_policy=min_samples_per_policy,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        )
        for policy in policies
    ]
    results.sort(
        key=lambda row: (
            _to_float(row.get("score")) or -999,
            _to_float(row.get("avg_forward_return_pct")) or -999,
            -(_to_float(row.get("stop_hit_rate_pct")) or 999),
        ),
        reverse=True,
    )
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank

    baseline_id = _policy_id(normalize_trade_policy(DEFAULT_TRADE_POLICY))
    baseline = next((row for row in results if row.get("policy_id") == baseline_id), None)
    best = results[0] if results else None
    improvement = {
        "target_hit_delta_pct": _delta((best or {}).get("target_hit_rate_pct"), (baseline or {}).get("target_hit_rate_pct")),
        "stop_hit_delta_pct": _delta((best or {}).get("stop_hit_rate_pct"), (baseline or {}).get("stop_hit_rate_pct")),
        "avg_return_delta_pct": _delta((best or {}).get("avg_forward_return_pct"), (baseline or {}).get("avg_forward_return_pct")),
        "avg_trade_return_delta_pct": _delta((best or {}).get("avg_trade_return_pct"), (baseline or {}).get("avg_trade_return_pct")),
        "win_rate_delta_pct": _delta((best or {}).get("win_rate_pct"), (baseline or {}).get("win_rate_pct")),
        "profit_factor_delta": _delta((best or {}).get("profit_factor"), (baseline or {}).get("profit_factor")),
        "expectancy_delta_pct": _delta((best or {}).get("expectancy_pct"), (baseline or {}).get("expectancy_pct")),
        "coverage_delta_pct": _delta((best or {}).get("coverage_pct"), (baseline or {}).get("coverage_pct")),
    }
    recommendation = _recommendation(best, baseline, min_samples_per_policy)

    return {
        "ok": True,
        "mode": "adaptive_trade_calibration",
        "summary": {
            "policies_tested": len(results),
            "best_policy_id": (best or {}).get("policy_id"),
            "best_score": (best or {}).get("score"),
            "best_quality_label": (best or {}).get("quality_label"),
            "baseline_policy": normalize_trade_policy(DEFAULT_TRADE_POLICY),
            "baseline_metrics": baseline,
            "best_policy_metrics": best,
            "improvement_vs_baseline": improvement,
            "recommendation": recommendation,
            "samples": len(base_samples),
            "tickers_used": len(tickers_used),
            "warnings": warnings,
        },
        "best_policies": results[:10],
        "results": results,
        "limitations": [
            "Adaptive trade calibration is a research layer and does not change production consumer signal logic.",
            "Historical evaluation is proxy candle-only and does not replay ticker news, global events or ML probability.",
            "No commissions, taxes, spreads or slippage are included.",
            "Daily candles do not provide intraday high/low order; if target and stop are both touched in one candle, stop_hit is assumed.",
            "Current instrument universe can introduce survivorship bias.",
            "Best policy can be overfit to this sample and must be validated with walk-forward or paper trading before production use.",
            *(
                ["No historical samples were built. Check /signals/data-coverage to diagnose instrument and candle coverage."]
                if not base_samples
                else []
            ),
        ],
        "parameters": {
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "max_policies": max_policies,
            "min_samples_per_policy": min_samples_per_policy,
            "min_history": min_history,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
        },
    }
