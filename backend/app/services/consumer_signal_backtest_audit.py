from __future__ import annotations

from itertools import product
from math import sqrt
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument
from app.services.consumer_signals import (
    _build_position_sizing,
    _build_signal_audit,
    _calculate_target_probability,
    _consumer_signal_decision_gate,
    _round,
    _to_float,
)


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous * 100


def _safe_avg(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return _round(sum(clean) / len(clean), 2)


def _rate(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return _round(part / total * 100, 2)


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


def _build_proxy_technical(history: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [_to_float(row.get("close")) for row in history if _to_float(row.get("close")) is not None]
    highs = [_to_float(row.get("high")) for row in history[-20:] if _to_float(row.get("high")) is not None]
    lows = [_to_float(row.get("low")) for row in history[-20:] if _to_float(row.get("low")) is not None]
    volumes = [_to_float(row.get("volume")) for row in history if _to_float(row.get("volume")) is not None]

    price = closes[-1] if closes else None
    sma_20 = mean(closes[-20:]) if len(closes) >= 20 else None
    sma_50 = mean(closes[-50:]) if len(closes) >= 50 else None
    return_5d = _pct_change(price, closes[-6]) if len(closes) >= 6 else None
    return_20d = _pct_change(price, closes[-21]) if len(closes) >= 21 else None

    volatility_20d_pct = None
    if len(closes) >= 21:
        returns = []
        for prev, cur in zip(closes[-21:-1], closes[-20:]):
            if prev:
                returns.append((cur - prev) / prev * 100)
        if len(returns) >= 2:
            avg = mean(returns)
            variance = sum((item - avg) ** 2 for item in returns) / (len(returns) - 1)
            volatility_20d_pct = sqrt(variance)

    volume_ratio = None
    if len(volumes) >= 21 and mean(volumes[-21:-1]) > 0:
        volume_ratio = volumes[-1] / mean(volumes[-21:-1])

    trend = "neutral"
    if price is not None and sma_20 is not None and sma_50 is not None:
        if price > sma_20 > sma_50:
            trend = "up"
        elif price < sma_20 < sma_50:
            trend = "down"

    momentum = "neutral"
    if return_5d is not None and return_20d is not None:
        if return_5d > 1 and return_20d > 2:
            momentum = "positive"
        elif return_5d < -1 and return_20d < -3:
            momentum = "negative"

    return {
        "trend": trend,
        "momentum": momentum,
        "sma_20": _round(sma_20),
        "sma_50": _round(sma_50),
        "return_5d_pct": _round(return_5d, 2),
        "return_20d_pct": _round(return_20d, 2),
        "volatility_20d_pct": _round(volatility_20d_pct, 2),
        "volume_ratio": _round(volume_ratio, 2),
        "recent_high": _round(max(highs) if highs else None),
        "recent_low": _round(min(lows) if lows else None),
    }


def _build_proxy_signal(
    *,
    price: float,
    technical: dict[str, Any],
    target_pct: float,
    stop_pct: float,
) -> tuple[dict[str, Any], float]:
    return_20d = _to_float(technical.get("return_20d_pct")) or 0.0
    return_5d = _to_float(technical.get("return_5d_pct")) or 0.0
    volatility = _to_float(technical.get("volatility_20d_pct")) or 1.8
    trend = str(technical.get("trend") or "neutral")
    momentum = str(technical.get("momentum") or "neutral")

    confidence = 48.0
    quality = 50.0
    action = "hold_watch"
    target_price = price * (1 + target_pct)

    if trend == "up":
        confidence += 8
        quality += 10
    elif trend == "down":
        confidence -= 10
        quality -= 12

    if momentum == "positive":
        confidence += 5
        quality += 6
    elif momentum == "negative":
        confidence -= 7
        quality -= 8

    if return_20d > 8:
        confidence -= 3
        quality -= 4
    elif return_20d < -8:
        confidence -= 4
        quality -= 4

    if volatility > 3.5:
        confidence -= 6
        quality -= 8
    elif volatility < 1.4:
        confidence += 3
        quality += 3

    if trend == "down" and return_20d < -4:
        action = "risk_sell_watch"
        target_price = price * (1 - target_pct)
    elif confidence >= 58 and quality >= 58:
        action = "buy_watch"
    elif confidence >= 52:
        action = "watch_buy"

    risk_reward_ratio = target_pct / stop_pct if stop_pct > 0 else None
    signal = {
        "action": action,
        "signal_type": "proxy_historical",
        "target_price": _round(target_price),
        "stop_loss": _round(price * (1 - stop_pct)),
        "confidence_pct": _round(max(5, min(95, confidence)), 1),
        "quality_score": _round(max(0, min(100, quality)), 1),
        "risk_reward_ratio": _round(risk_reward_ratio, 2),
        "risk_level": "Высокий" if volatility >= 3.5 else "Средний" if volatility >= 2.4 else "Низкий",
        "horizon": "proxy historical",
    }
    return signal, target_price


def _evaluate_outcome(
    *,
    current: dict[str, Any],
    future: list[dict[str, Any]],
    horizon: int,
    target_pct: float,
    stop_pct: float,
) -> dict[str, Any]:
    close = _to_float(current.get("close"))
    if close is None or close <= 0 or not future:
        return {
            "outcome": "not_available",
            "success": False,
            "days_to_outcome": None,
            "max_favorable_excursion_pct": None,
            "max_adverse_excursion_pct": None,
            "forward_return_pct": None,
        }

    target_price = close * (1 + target_pct)
    stop_price = close * (1 - stop_pct)
    max_high = close
    min_low = close
    outcome = "timeout"
    success = False
    days_to_outcome = min(horizon, len(future))

    for day, candle in enumerate(future[:horizon], start=1):
        high = _to_float(candle.get("high")) or close
        low = _to_float(candle.get("low")) or close
        max_high = max(max_high, high)
        min_low = min(min_low, low)

        hit_target = high >= target_price
        hit_stop = low <= stop_price
        if hit_target and hit_stop:
            outcome = "stop_hit"
            success = False
            days_to_outcome = day
            break
        if hit_stop:
            outcome = "stop_hit"
            success = False
            days_to_outcome = day
            break
        if hit_target:
            outcome = "target_hit"
            success = True
            days_to_outcome = day
            break

    last_close = _to_float(future[min(len(future), horizon) - 1].get("close")) if future else None
    forward_return_pct = _pct_change(last_close, close)

    if outcome == "timeout":
        success = bool(forward_return_pct is not None and forward_return_pct > 0)

    return {
        "outcome": outcome,
        "success": success,
        "days_to_outcome": days_to_outcome,
        "max_favorable_excursion_pct": _round(_pct_change(max_high, close), 2),
        "max_adverse_excursion_pct": _round(_pct_change(min_low, close), 2),
        "forward_return_pct": _round(forward_return_pct, 2),
    }


def _empty_bucket() -> dict[str, Any]:
    return {
        "samples": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "timeouts": 0,
        "successes": 0,
        "forward_returns": [],
        "mfe_values": [],
        "mae_values": [],
    }


def _add_to_bucket(bucket: dict[str, Any], sample: dict[str, Any]) -> None:
    bucket["samples"] += 1
    if sample.get("outcome") == "target_hit":
        bucket["target_hits"] += 1
    elif sample.get("outcome") == "stop_hit":
        bucket["stop_hits"] += 1
    elif sample.get("outcome") == "timeout":
        bucket["timeouts"] += 1
    if sample.get("success"):
        bucket["successes"] += 1

    for key, target in [
        ("forward_return_pct", "forward_returns"),
        ("mfe_pct", "mfe_values"),
        ("mae_pct", "mae_values"),
    ]:
        value = _to_float(sample.get(key))
        if value is not None:
            bucket[target].append(value)


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    samples = int(bucket.get("samples") or 0)
    return {
        "samples": samples,
        "target_hit_rate_pct": _rate(int(bucket.get("target_hits") or 0), samples),
        "stop_hit_rate_pct": _rate(int(bucket.get("stop_hits") or 0), samples),
        "timeout_rate_pct": _rate(int(bucket.get("timeouts") or 0), samples),
        "positive_rate_pct": _rate(int(bucket.get("successes") or 0), samples),
        "avg_forward_return_pct": _safe_avg(bucket.get("forward_returns") or []),
        "avg_mfe_pct": _safe_avg(bucket.get("mfe_values") or []),
        "avg_mae_pct": _safe_avg(bucket.get("mae_values") or []),
    }


def _example(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": sample.get("ticker"),
        "date": sample.get("date"),
        "action": sample.get("action"),
        "probability_pct": sample.get("probability_pct"),
        "audit_score": sample.get("audit_score"),
        "blocked_by": sample.get("blocked_by") or [],
        "outcome": sample.get("outcome"),
        "forward_return_pct": sample.get("forward_return_pct"),
        "mfe_pct": sample.get("mfe_pct"),
        "mae_pct": sample.get("mae_pct"),
    }


def _build_proxy_samples(
    *,
    db: Session,
    max_tickers: int,
    max_samples: int,
    horizon: int,
    target_pct: float,
    stop_pct: float,
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

    samples: list[dict[str, Any]] = []
    tickers_used: set[str] = set()
    per_ticker_cap = max(1, max_samples // max(1, len(instruments)))

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
        if len(candles) < min_history + horizon + 1:
            continue

        max_index = len(candles) - horizon - 1
        candidate_indexes = list(range(min_history - 1, max_index + 1))
        if not candidate_indexes:
            continue

        step = max(1, len(candidate_indexes) // per_ticker_cap)
        selected_indexes = candidate_indexes[::step][:per_ticker_cap]

        for index in selected_indexes:
            if len(samples) >= max_samples:
                break

            history = candles[: index + 1]
            current = candles[index]
            future = candles[index + 1 : index + 1 + horizon]
            price = _to_float(current.get("close"))
            if price is None or price <= 0:
                continue

            technical = _build_proxy_technical(history)
            signal, target_price = _build_proxy_signal(
                price=price,
                technical=technical,
                target_pct=target_pct,
                stop_pct=stop_pct,
            )
            rule_probability = _calculate_target_probability(
                signal=signal,
                technical=technical,
                price=price,
                target_price=target_price,
                events=[],
            )
            probability = _round(rule_probability, 0)
            reliability_level = "Высокая" if (probability or 0) >= 62 else "Средняя" if (probability or 0) >= 45 else "Низкая"
            reliability_score = _round(max(0, min(100, (probability or 0) + 10)), 0)

            target_distance_pct = _pct_change(target_price, price)
            stop_distance_pct = stop_pct * 100
            risk_reward_ratio = (
                target_distance_pct / stop_distance_pct
                if target_distance_pct is not None and target_distance_pct > 0 and stop_distance_pct > 0
                else None
            )
            scenario_direction = "downside" if signal.get("action") == "risk_sell_watch" else "long" if target_distance_pct and target_distance_pct > 0 else "neutral"
            scenario_reason = (
                "Proxy candle-only model detected downside trend."
                if scenario_direction == "downside"
                else "Proxy candle-only model uses an upside target."
            )

            decision_gate = _consumer_signal_decision_gate(
                probability=probability,
                reliability_level=reliability_level,
                risk_level=signal.get("risk_level"),
                ml_adjustment_pct=None,
                ml_probability_pct=None,
                risk_reward_ratio=risk_reward_ratio,
                target_distance_pct=target_distance_pct,
                scenario_direction=scenario_direction,
            )
            position_sizing = _build_position_sizing(
                action=decision_gate.get("action"),
                price=price,
                target_price=target_price,
                stop_loss=signal.get("stop_loss"),
                probability=probability,
                risk_level=signal.get("risk_level"),
                reliability_level=reliability_level,
                reliability_score=reliability_score,
                ml_probability=None,
                ml_regime_multiplier=None,
                volatility_pct=_to_float(technical.get("volatility_20d_pct")),
            )
            if target_distance_pct is not None and position_sizing.get("target_distance_pct") is None:
                position_sizing["target_distance_pct"] = _round(target_distance_pct, 2)
            if position_sizing.get("stop_distance_pct") is None:
                position_sizing["stop_distance_pct"] = _round(stop_distance_pct, 2)
            if risk_reward_ratio is not None and position_sizing.get("risk_reward_ratio") is None:
                position_sizing["risk_reward_ratio"] = _round(risk_reward_ratio, 2)

            probability_assessment = {
                "probability_pct": probability,
                "base_probability_pct": probability,
                "reliability_level": reliability_level,
                "reliability_score": reliability_score,
                "internal": {
                    "proxy_historical": True,
                    "news_adjustment_pct": 0.0,
                    "ticker_news_adjustment_pct": 0.0,
                    "global_event_adjustment_pct": 0.0,
                },
            }
            news_assessment = {
                "has_events": False,
                "news_effect": "none",
                "adjustment_pct": 0.0,
                "ticker_news_adjustment_pct": 0.0,
                "risk_flags": [],
                "summary": "Proxy historical audit does not replay ticker news.",
            }
            global_news_assessment = {
                "has_global_events": False,
                "adjustment_pct": 0.0,
                "tags": [],
                "macro_regime_flags": [],
                "reason": "Proxy historical audit does not replay global macro/geopolitical events.",
                "events": [],
            }
            audit = _build_signal_audit(
                technical=technical,
                signal=signal,
                probability_assessment=probability_assessment,
                position_sizing=position_sizing,
                news_assessment=news_assessment,
                global_news_assessment=global_news_assessment,
                ml_probability_result=None,
                decision_gate=decision_gate,
                scenario_direction=scenario_direction,
                scenario_reason=scenario_reason,
                source_signal_action=signal.get("action"),
                source_target_price=_to_float(signal.get("target_price")),
                rule_probability_pct=rule_probability,
                ml_probability_pct=None,
                ml_weight=0.0,
                ml_adjustment_pct=None,
                ml_regime_multiplier=None,
                ml_regime_reason=None,
                target_probability_pct=probability,
                ticker_news_adjustment_pct=0.0,
                global_event_adjustment_pct=0.0,
            )
            outcome = _evaluate_outcome(
                current=current,
                future=future,
                horizon=horizon,
                target_pct=target_pct,
                stop_pct=stop_pct,
            )
            sample = {
                "ticker": instrument.ticker,
                "date": current.get("trade_date"),
                "action": decision_gate.get("action") or signal.get("action"),
                "recommendation": decision_gate.get("recommendation"),
                "probability_pct": probability,
                "proxy_ml_probability_pct": probability,
                "risk_reward_ratio": _round(risk_reward_ratio, 2),
                "target_distance_pct": _round(target_distance_pct, 2),
                "audit_score": audit.get("overall_score"),
                "audit_confidence_level": audit.get("confidence_level"),
                "blocked_by": audit.get("blocked_by") or ["none"],
                "passed_layers": audit.get("passed_layers") or [],
                "warning_layers": audit.get("warning_layers") or [],
                "outcome": outcome.get("outcome"),
                "success": outcome.get("success"),
                "days_to_outcome": outcome.get("days_to_outcome"),
                "forward_return_pct": outcome.get("forward_return_pct"),
                "mfe_pct": outcome.get("max_favorable_excursion_pct"),
                "mae_pct": outcome.get("max_adverse_excursion_pct"),
            }
            samples.append(sample)
            tickers_used.add(instrument.ticker)

    return samples, tickers_used


def _calibration_score(metrics: dict[str, Any], *, min_signals: int) -> float:
    signals = int(metrics.get("samples") or 0)
    target_hit_rate = _to_float(metrics.get("target_hit_rate_pct")) or 0.0
    stop_hit_rate = _to_float(metrics.get("stop_hit_rate_pct")) or 0.0
    timeout_rate = _to_float(metrics.get("timeout_rate_pct")) or 0.0
    avg_return = max(_to_float(metrics.get("avg_forward_return_pct")) or 0.0, -10.0)

    score = 0.0
    score += target_hit_rate * 1.5
    score += avg_return * 4.0
    score -= stop_hit_rate * 0.8
    score -= timeout_rate * 0.2
    score += 5 if signals >= min_signals else -20
    if signals >= 50:
        score += 5

    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _quality_label(score: float, signals: int, min_signals: int) -> str:
    if signals < min_signals:
        return "unstable"
    if score >= 30:
        return "good"
    if score >= 10:
        return "medium"
    return "weak"


def build_consumer_signal_backtest_audit(
    db: Session,
    max_tickers: int = 80,
    max_samples: int = 2000,
    horizon: int = 20,
    target_pct: float = 0.05,
    stop_pct: float = 0.03,
    min_history: int = 80,
) -> dict[str, Any]:
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

    samples: list[dict[str, Any]] = []
    tickers_used: set[str] = set()
    per_ticker_cap = max(1, max_samples // max(1, len(instruments)))

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
        if len(candles) < min_history + horizon + 1:
            continue

        max_index = len(candles) - horizon - 1
        candidate_indexes = list(range(min_history - 1, max_index + 1))
        if not candidate_indexes:
            continue

        step = max(1, len(candidate_indexes) // per_ticker_cap)
        selected_indexes = candidate_indexes[::step][:per_ticker_cap]

        for index in selected_indexes:
            if len(samples) >= max_samples:
                break

            history = candles[: index + 1]
            current = candles[index]
            future = candles[index + 1 : index + 1 + horizon]
            price = _to_float(current.get("close"))
            if price is None or price <= 0:
                continue

            technical = _build_proxy_technical(history)
            signal, target_price = _build_proxy_signal(
                price=price,
                technical=technical,
                target_pct=target_pct,
                stop_pct=stop_pct,
            )
            rule_probability = _calculate_target_probability(
                signal=signal,
                technical=technical,
                price=price,
                target_price=target_price,
                events=[],
            )
            probability = _round(rule_probability, 0)
            reliability_level = "Высокая" if (probability or 0) >= 62 else "Средняя" if (probability or 0) >= 45 else "Низкая"
            reliability_score = _round(max(0, min(100, (probability or 0) + 10)), 0)

            target_distance_pct = _pct_change(target_price, price)
            stop_distance_pct = stop_pct * 100
            risk_reward_ratio = (
                target_distance_pct / stop_distance_pct
                if target_distance_pct is not None and target_distance_pct > 0 and stop_distance_pct > 0
                else None
            )
            scenario_direction = "downside" if signal.get("action") == "risk_sell_watch" else "long" if target_distance_pct and target_distance_pct > 0 else "neutral"
            scenario_reason = (
                "Proxy candle-only model detected downside trend."
                if scenario_direction == "downside"
                else "Proxy candle-only model uses an upside target."
            )

            decision_gate = _consumer_signal_decision_gate(
                probability=probability,
                reliability_level=reliability_level,
                risk_level=signal.get("risk_level"),
                ml_adjustment_pct=None,
                ml_probability_pct=None,
                risk_reward_ratio=risk_reward_ratio,
                target_distance_pct=target_distance_pct,
                scenario_direction=scenario_direction,
            )
            position_sizing = _build_position_sizing(
                action=decision_gate.get("action"),
                price=price,
                target_price=target_price,
                stop_loss=signal.get("stop_loss"),
                probability=probability,
                risk_level=signal.get("risk_level"),
                reliability_level=reliability_level,
                reliability_score=reliability_score,
                ml_probability=None,
                ml_regime_multiplier=None,
                volatility_pct=_to_float(technical.get("volatility_20d_pct")),
            )
            if target_distance_pct is not None and position_sizing.get("target_distance_pct") is None:
                position_sizing["target_distance_pct"] = _round(target_distance_pct, 2)
            if position_sizing.get("stop_distance_pct") is None:
                position_sizing["stop_distance_pct"] = _round(stop_distance_pct, 2)
            if risk_reward_ratio is not None and position_sizing.get("risk_reward_ratio") is None:
                position_sizing["risk_reward_ratio"] = _round(risk_reward_ratio, 2)

            probability_assessment = {
                "probability_pct": probability,
                "base_probability_pct": probability,
                "reliability_level": reliability_level,
                "reliability_score": reliability_score,
                "internal": {
                    "proxy_historical": True,
                    "news_adjustment_pct": 0.0,
                    "ticker_news_adjustment_pct": 0.0,
                    "global_event_adjustment_pct": 0.0,
                },
            }
            news_assessment = {
                "has_events": False,
                "news_effect": "none",
                "adjustment_pct": 0.0,
                "ticker_news_adjustment_pct": 0.0,
                "risk_flags": [],
                "summary": "Proxy historical audit does not replay ticker news.",
            }
            global_news_assessment = {
                "has_global_events": False,
                "adjustment_pct": 0.0,
                "tags": [],
                "macro_regime_flags": [],
                "reason": "Proxy historical audit does not replay global macro/geopolitical events.",
                "events": [],
            }
            audit = _build_signal_audit(
                technical=technical,
                signal=signal,
                probability_assessment=probability_assessment,
                position_sizing=position_sizing,
                news_assessment=news_assessment,
                global_news_assessment=global_news_assessment,
                ml_probability_result=None,
                decision_gate=decision_gate,
                scenario_direction=scenario_direction,
                scenario_reason=scenario_reason,
                source_signal_action=signal.get("action"),
                source_target_price=_to_float(signal.get("target_price")),
                rule_probability_pct=rule_probability,
                ml_probability_pct=None,
                ml_weight=0.0,
                ml_adjustment_pct=None,
                ml_regime_multiplier=None,
                ml_regime_reason=None,
                target_probability_pct=probability,
                ticker_news_adjustment_pct=0.0,
                global_event_adjustment_pct=0.0,
            )
            outcome = _evaluate_outcome(
                current=current,
                future=future,
                horizon=horizon,
                target_pct=target_pct,
                stop_pct=stop_pct,
            )
            sample = {
                "ticker": instrument.ticker,
                "date": current.get("trade_date"),
                "action": decision_gate.get("action") or signal.get("action"),
                "recommendation": decision_gate.get("recommendation"),
                "probability_pct": probability,
                "audit_score": audit.get("overall_score"),
                "audit_confidence_level": audit.get("confidence_level"),
                "blocked_by": audit.get("blocked_by") or ["none"],
                "passed_layers": audit.get("passed_layers") or [],
                "warning_layers": audit.get("warning_layers") or [],
                "outcome": outcome.get("outcome"),
                "success": outcome.get("success"),
                "days_to_outcome": outcome.get("days_to_outcome"),
                "forward_return_pct": outcome.get("forward_return_pct"),
                "mfe_pct": outcome.get("max_favorable_excursion_pct"),
                "mae_pct": outcome.get("max_adverse_excursion_pct"),
            }
            samples.append(sample)
            tickers_used.add(instrument.ticker)

    total_bucket = _empty_bucket()
    by_action_raw: dict[str, dict[str, Any]] = {}
    by_blocker_raw: dict[str, dict[str, Any]] = {}
    by_conf_raw: dict[str, dict[str, Any]] = {}
    by_layer_raw: dict[str, dict[str, Any]] = {}

    for sample in samples:
        _add_to_bucket(total_bucket, sample)

        action = str(sample.get("action") or "unknown")
        by_action_raw.setdefault(action, _empty_bucket())
        _add_to_bucket(by_action_raw[action], sample)

        confidence = str(sample.get("audit_confidence_level") or "unknown")
        by_conf_raw.setdefault(confidence, _empty_bucket())
        _add_to_bucket(by_conf_raw[confidence], sample)

        blockers = sample.get("blocked_by") or ["none"]
        for blocker in blockers:
            blocker_key = str(blocker or "none")
            by_blocker_raw.setdefault(blocker_key, _empty_bucket())
            _add_to_bucket(by_blocker_raw[blocker_key], sample)

        layers = sample.get("passed_layers") or []
        for layer in ["technical", "ml", "risk", "ticker_news", "global_macro", "scenario"]:
            if layer in layers:
                by_layer_raw.setdefault(layer, _empty_bucket())
                _add_to_bucket(by_layer_raw[layer], sample)

    summary_bucket = _finalize_bucket(total_bucket)
    summary = {
        "samples": len(samples),
        "tickers_used": len(tickers_used),
        "horizon": horizon,
        "target_pct": target_pct,
        "stop_pct": stop_pct,
        "positive_rate_pct": summary_bucket.get("positive_rate_pct"),
        "avg_forward_return_pct": summary_bucket.get("avg_forward_return_pct"),
        "target_hit_rate_pct": summary_bucket.get("target_hit_rate_pct"),
        "stop_hit_rate_pct": summary_bucket.get("stop_hit_rate_pct"),
        "timeout_rate_pct": summary_bucket.get("timeout_rate_pct"),
    }

    top_positive = sorted(samples, key=lambda item: _to_float(item.get("forward_return_pct")) or -999, reverse=True)[:10]
    top_negative = sorted(samples, key=lambda item: _to_float(item.get("forward_return_pct")) or 999)[:10]
    near_miss = [
        item for item in samples
        if item.get("action") not in {"buy", "consider_buy"} and item.get("outcome") == "target_hit"
    ]
    near_miss = sorted(near_miss, key=lambda item: _to_float(item.get("forward_return_pct")) or -999, reverse=True)[:10]
    false_positive_actions = {"buy", "consider_buy", "watch", "watch_bad_rr", "watch_ml_confirmed", "watch_ml_rejected"}
    false_positives = [
        item for item in samples
        if item.get("action") in false_positive_actions and (item.get("outcome") == "stop_hit" or (_to_float(item.get("forward_return_pct")) or 0) < 0)
    ]
    false_positives = sorted(false_positives, key=lambda item: _to_float(item.get("forward_return_pct")) or 999)[:10]

    return {
        "ok": True,
        "mode": "proxy_historical_consumer_audit",
        "summary": summary,
        "by_action": {key: _finalize_bucket(value) for key, value in sorted(by_action_raw.items())},
        "by_blocker": {key: _finalize_bucket(value) for key, value in sorted(by_blocker_raw.items())},
        "by_audit_confidence": {key: _finalize_bucket(value) for key, value in sorted(by_conf_raw.items())},
        "by_layer_support": {key: _finalize_bucket(value) for key, value in sorted(by_layer_raw.items())},
        "top_positive_examples": [_example(item) for item in top_positive],
        "top_negative_examples": [_example(item) for item in top_negative],
        "near_miss_examples": [_example(item) for item in near_miss],
        "worst_false_positives": [_example(item) for item in false_positives],
        "limitations": [
            "Historical audit approximates consumer decision logic using candle-only features.",
            "ML probability is not replayed historically; ml layer is marked not_available.",
            "Ticker news and global macro/geopolitical events are not replayed historically in this proxy audit.",
            "Daily candles do not provide intraday event order; if target and stop are both touched in one candle, stop_hit is assumed.",
            "No commissions, taxes, spreads or slippage are included.",
            "Current instrument universe can introduce survivorship bias.",
        ],
        "note": "Historical audit approximates consumer decision logic using candle-only features; live news/global events are evaluated separately.",
        "parameters": {
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "horizon": horizon,
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "min_history": min_history,
        },
    }


def build_consumer_threshold_sweep_audit(
    db: Session,
    max_tickers: int = 60,
    max_samples: int = 1500,
    horizons: list[int] | None = None,
    target_pcts: list[float] | None = None,
    stop_pcts: list[float] | None = None,
    min_probabilities: list[float] | None = None,
    min_ml_probabilities: list[float] | None = None,
    min_rr_values: list[float] | None = None,
    min_signals: int = 20,
    max_configs: int = 120,
) -> dict[str, Any]:
    horizons = horizons or [15, 20, 30]
    target_pcts = target_pcts or [0.03, 0.04, 0.05, 0.06]
    stop_pcts = stop_pcts or [0.02, 0.03, 0.04]
    min_probabilities = min_probabilities or [45, 50, 55, 60]
    min_ml_probabilities = min_ml_probabilities or [0, 20, 25, 30, 35]
    min_rr_values = min_rr_values or [0.8, 1.0, 1.2, 1.5]

    warnings: list[str] = []
    raw_configs = list(product(horizons, target_pcts, stop_pcts, min_probabilities, min_ml_probabilities, min_rr_values))
    total_configs = len(raw_configs)
    if total_configs > max_configs:
        warnings.append(f"Grid truncated from {total_configs} to {max_configs} configs for runtime protection.")
        raw_configs = raw_configs[:max_configs]

    sample_cache: dict[tuple[int, float, float], tuple[list[dict[str, Any]], set[str]]] = {}
    results: list[dict[str, Any]] = []
    max_base_samples = 0

    for horizon, target_pct, stop_pct, min_probability, min_ml_probability, min_rr in raw_configs:
        sample_key = (int(horizon), float(target_pct), float(stop_pct))
        if sample_key not in sample_cache:
            sample_cache[sample_key] = _build_proxy_samples(
                db=db,
                max_tickers=max_tickers,
                max_samples=max_samples,
                horizon=int(horizon),
                target_pct=float(target_pct),
                stop_pct=float(stop_pct),
                min_history=80,
            )

        base_samples, _tickers_used = sample_cache[sample_key]
        max_base_samples = max(max_base_samples, len(base_samples))
        selected = []
        for sample in base_samples:
            probability = _to_float(sample.get("probability_pct"))
            proxy_ml = _to_float(sample.get("proxy_ml_probability_pct"))
            rr = _to_float(sample.get("risk_reward_ratio"))
            target_distance = _to_float(sample.get("target_distance_pct"))

            if probability is None or probability < float(min_probability):
                continue
            if proxy_ml is None or proxy_ml < float(min_ml_probability):
                continue
            if rr is None or rr < float(min_rr):
                continue
            if target_distance is None or target_distance <= 0:
                continue

            selected.append(sample)

        bucket = _empty_bucket()
        for sample in selected:
            _add_to_bucket(bucket, sample)
        metrics = _finalize_bucket(bucket)
        signals = int(metrics.get("samples") or 0)
        coverage_pct = _rate(signals, len(base_samples)) or 0.0
        score = _calibration_score(metrics, min_signals=min_signals)
        config_warnings = []
        if signals < min_signals:
            config_warnings.append("signals below min_signals; unstable estimate")
        if float(min_ml_probability) > 0:
            config_warnings.append("min_ml_probability uses proxy probability because historical ML replay is unavailable")

        config_id = (
            f"h{int(horizon)}"
            f"_t{int(round(float(target_pct) * 100))}"
            f"_s{int(round(float(stop_pct) * 100))}"
            f"_p{int(float(min_probability))}"
            f"_ml{int(float(min_ml_probability))}"
            f"_rr{str(float(min_rr)).replace('.', '_')}"
        )
        results.append(
            {
                "rank": None,
                "config_id": config_id,
                "horizon": int(horizon),
                "target_pct": _round(float(target_pct) * 100, 2),
                "stop_pct": _round(float(stop_pct) * 100, 2),
                "min_probability": _round(float(min_probability), 2),
                "min_ml_probability": _round(float(min_ml_probability), 2),
                "min_rr": _round(float(min_rr), 2),
                "signals": signals,
                "coverage_pct": _round(coverage_pct, 2),
                "target_hit_rate_pct": metrics.get("target_hit_rate_pct"),
                "stop_hit_rate_pct": metrics.get("stop_hit_rate_pct"),
                "timeout_rate_pct": metrics.get("timeout_rate_pct"),
                "avg_forward_return_pct": metrics.get("avg_forward_return_pct"),
                "avg_mfe_pct": metrics.get("avg_mfe_pct"),
                "avg_mae_pct": metrics.get("avg_mae_pct"),
                "success_count": int(bucket.get("successes") or 0),
                "failure_count": int(bucket.get("stop_hits") or 0),
                "score": score,
                "quality_label": _quality_label(score, signals, min_signals),
                "warnings": config_warnings,
            }
        )

    results.sort(
        key=lambda row: (
            float(row.get("score") or -999),
            int(row.get("signals") or 0),
            float(row.get("avg_forward_return_pct") or -999),
        ),
        reverse=True,
    )
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank

    if max_base_samples < min_signals:
        warnings.append("Base sample count is below min_signals; sweep conclusions are unstable.")
    if not results:
        warnings.append("No configs were evaluated.")

    best = results[0] if results else {}
    return {
        "ok": True,
        "mode": "consumer_threshold_sweep_audit",
        "summary": {
            "configs_tested": len(results),
            "best_config_id": best.get("config_id"),
            "best_score": best.get("score"),
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "min_signals": min_signals,
            "base_samples": max_base_samples,
            "warnings": warnings,
        },
        "best_configs": results[:10],
        "results": results,
        "parameter_grid": {
            "horizons": horizons,
            "target_pcts": target_pcts,
            "stop_pcts": stop_pcts,
            "min_probabilities": min_probabilities,
            "min_ml_probabilities": min_ml_probabilities,
            "min_rr_values": min_rr_values,
            "max_configs": max_configs,
            "total_requested_configs": total_configs,
        },
        "limitations": [
            "Threshold sweep is a calibration/evaluation layer; it does not update production decision thresholds automatically.",
            "Historical samples use the proxy candle-only consumer audit, not full live news/global/ML replay.",
            "min_ml_probability is evaluated against proxy probability because historical ML replay is unavailable.",
            "No commissions, taxes, spreads or slippage are included.",
            "Daily candles do not provide intraday order; same-day target and stop is treated conservatively as stop_hit.",
            "Current instrument universe can introduce survivorship bias.",
        ],
    }
