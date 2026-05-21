from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument
from app.services.consumer_signals import _round


SUPPORTED_SIGNAL_ASSET_TYPES = {"stock", "share", "equity", "unknown"}


def classify_coverage_level(total_possible_samples: int, usable_tickers: int) -> str:
    if total_possible_samples <= 0:
        return "empty"
    if total_possible_samples < 500 or usable_tickers < 10:
        return "weak"
    if total_possible_samples < 5000 or usable_tickers < 50:
        return "medium"
    return "good"


def classify_ticker_data_status(
    *,
    is_signal_eligible: bool | None,
    asset_type: str | None,
    candle_count: int,
    valid_ohlc_count: int,
    min_history: int,
    horizon: int,
) -> str:
    if not bool(is_signal_eligible):
        return "not_signal_eligible"
    if str(asset_type or "unknown") not in SUPPORTED_SIGNAL_ASSET_TYPES:
        return "unsupported_asset_type"
    if candle_count <= 0:
        return "no_candles"
    if valid_ohlc_count <= 0:
        return "invalid_ohlc"
    if valid_ohlc_count < min_history:
        return "too_few_candles"
    if valid_ohlc_count < min_history + horizon + 1:
        return "insufficient_horizon"
    return "ok"


def _date_to_str(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _avg(values: list[int]) -> float | None:
    if not values:
        return None
    return _round(sum(values) / len(values), 2)


def _main_blocker(skip_reasons: dict[str, int]) -> str:
    candidates = {key: value for key, value in skip_reasons.items() if key != "ok"}
    if not candidates:
        return "none"
    key, value = max(candidates.items(), key=lambda item: item[1])
    return key if value > 0 else "none"


def _instrument_counts(db: Session) -> dict[str, Any]:
    total = db.scalar(select(func.count(Instrument.id))) or 0
    eligible_true = db.scalar(select(func.count(Instrument.id)).where(Instrument.is_signal_eligible.is_(True))) or 0
    eligible_false = db.scalar(select(func.count(Instrument.id)).where(Instrument.is_signal_eligible.is_(False))) or 0
    eligible_unknown = max(0, int(total) - int(eligible_true) - int(eligible_false))
    by_asset_type = {
        str(asset_type or "unknown"): int(count or 0)
        for asset_type, count in db.execute(
            select(Instrument.asset_type, func.count(Instrument.id)).group_by(Instrument.asset_type)
        ).all()
    }
    return {
        "total_instruments": int(total),
        "eligible_true": int(eligible_true),
        "eligible_false": int(eligible_false),
        "eligible_unknown": int(eligible_unknown),
        "signal_eligible_count": int(eligible_true),
        "by_asset_type": by_asset_type,
    }


def _candle_overview(db: Session) -> dict[str, Any]:
    row = db.execute(
        select(
            func.count(Candle.id),
            func.count(func.distinct(Candle.ticker)),
            func.min(Candle.trade_date),
            func.max(Candle.trade_date),
        )
    ).one()
    return {
        "total_candles": int(row[0] or 0),
        "tickers_with_candles": int(row[1] or 0),
        "first_date": _date_to_str(row[2]),
        "last_date": _date_to_str(row[3]),
    }


def _candle_stats_by_ticker(db: Session, tickers: list[str]) -> dict[str, dict[str, Any]]:
    if not tickers:
        return {}
    rows = db.execute(
        select(
            Candle.ticker,
            func.count(Candle.id).label("candle_count"),
            func.sum(case((Candle.close.is_(None), 1), else_=0)).label("missing_close_count"),
            func.sum(case(((Candle.high.is_(None)) | (Candle.low.is_(None)), 1), else_=0)).label("missing_high_low_count"),
            func.sum(
                case(
                    (
                        (Candle.open.is_not(None))
                        & (Candle.high.is_not(None))
                        & (Candle.low.is_not(None))
                        & (Candle.close.is_not(None)),
                        1,
                    ),
                    else_=0,
                )
            ).label("valid_ohlc_count"),
            func.min(Candle.trade_date).label("first_date"),
            func.max(Candle.trade_date).label("last_date"),
        )
        .where(Candle.ticker.in_(tickers))
        .group_by(Candle.ticker)
    ).all()
    return {
        str(row.ticker): {
            "candle_count": int(row.candle_count or 0),
            "valid_ohlc_count": int(row.valid_ohlc_count or 0),
            "missing_close_count": int(row.missing_close_count or 0),
            "missing_high_low_count": int(row.missing_high_low_count or 0),
            "first_date": _date_to_str(row.first_date),
            "last_date": _date_to_str(row.last_date),
        }
        for row in rows
    }


def _ticker_row(
    instrument: Instrument,
    stats: dict[str, Any],
    *,
    min_history: int,
    horizon: int,
) -> dict[str, Any]:
    candle_count = int(stats.get("candle_count") or 0)
    valid_ohlc_count = int(stats.get("valid_ohlc_count") or 0)
    skip_reason = classify_ticker_data_status(
        is_signal_eligible=instrument.is_signal_eligible,
        asset_type=instrument.asset_type,
        candle_count=candle_count,
        valid_ohlc_count=valid_ohlc_count,
        min_history=min_history,
        horizon=horizon,
    )
    return {
        "ticker": instrument.ticker,
        "name": instrument.name,
        "asset_type": instrument.asset_type or "unknown",
        "sector": instrument.sector or "unknown",
        "is_signal_eligible": bool(instrument.is_signal_eligible),
        "candle_count": candle_count,
        "valid_ohlc_count": valid_ohlc_count,
        "first_date": stats.get("first_date"),
        "last_date": stats.get("last_date"),
        "enough_for_min_history": valid_ohlc_count >= min_history,
        "enough_for_horizon": valid_ohlc_count >= min_history + horizon + 1,
        "possible_samples": max(0, valid_ohlc_count - min_history - horizon),
        "missing_close_count": int(stats.get("missing_close_count") or 0),
        "missing_high_low_count": int(stats.get("missing_high_low_count") or 0),
        "skip_reason": skip_reason,
    }


def _recommendations(
    *,
    summary: dict[str, Any],
    skip_reasons: dict[str, int],
    min_history: int,
    horizon: int,
    max_tickers: int,
    candidate_tickers_before_limit: int,
) -> list[str]:
    recommendations: list[str] = []
    usable_tickers = int(summary.get("usable_tickers") or 0)
    total_possible_samples = int(summary.get("total_possible_samples") or 0)
    if total_possible_samples <= 0:
        recommendations.append(
            f"Для текущих параметров min_history={min_history} horizon={horizon} usable_tickers={usable_tickers}; historical endpoints будут возвращать 0 samples."
        )
    if int(summary.get("total_instruments") or 0) == 0:
        recommendations.append("Загрузить или инициализировать universe инструментов перед historical validation.")
        recommendations.append("Команда: cd backend && python3 -m app.tasks.bootstrap_market_data --max-instruments 300 --max-tickers 100 --days 900")
    if int(summary.get("tickers_with_candles") or 0) == 0:
        recommendations.append("Загрузить исторические свечи; сейчас нет тикеров со свечами.")
    if skip_reasons.get("no_candles", 0) > 0:
        recommendations.append("Догрузить свечи для eligible tickers without candles.")
        recommendations.append("Команда: cd backend && python3 -m app.tasks.bootstrap_market_data --skip-universe --max-tickers 100 --days 900")
    if skip_reasons.get("too_few_candles", 0) > 0 or skip_reasons.get("insufficient_horizon", 0) > 0:
        lowered = max(10, min(60, min_history))
        recommendations.append(f"Для диагностики можно снизить min_history до {lowered} или догрузить более длинную историю свечей.")
        recommendations.append("Команда для более длинной истории: cd backend && python3 -m app.tasks.bootstrap_market_data --skip-universe --max-tickers 100 --days 1200")
    if skip_reasons.get("invalid_ohlc", 0) > 0:
        recommendations.append("Проверить импорт OHLC: есть тикеры без валидных open/high/low/close.")
    if skip_reasons.get("unsupported_asset_type", 0) > 0 or skip_reasons.get("not_signal_eligible", 0) > 0:
        recommendations.append("Проверить asset_type/is_signal_eligible mapping для инструментов, которые должны попадать в signal universe.")
    if candidate_tickers_before_limit > max_tickers:
        recommendations.append("Увеличить max_tickers, если нужно проверить весь eligible universe.")
    if not recommendations:
        recommendations.append("Покрытие данных достаточно для текущих диагностик; можно запускать expectancy/backtest с теми же min_history/horizon.")
    return recommendations


def build_data_coverage_diagnostics(
    db: Session,
    max_tickers: int = 500,
    min_history: int = 80,
    horizon: int = 20,
    candles_limit: int = 1000,
    include_examples: bool = True,
) -> dict[str, Any]:
    instrument_counts = _instrument_counts(db)
    candle_overview = _candle_overview(db)
    warnings: list[str] = []
    if instrument_counts["total_instruments"] == 0:
        warnings.append("No instruments found in database.")
    if candle_overview["total_candles"] == 0:
        warnings.append("No candles found in database.")

    instruments = db.scalars(select(Instrument).order_by(Instrument.ticker.asc()).limit(max_tickers)).all()
    supported_eligible_count = db.scalar(
        select(func.count(Instrument.id))
        .where(Instrument.is_signal_eligible.is_(True))
        .where(Instrument.asset_type.in_(sorted(SUPPORTED_SIGNAL_ASSET_TYPES)))
    ) or 0
    candidate_instruments = [
        instrument
        for instrument in instruments
        if bool(instrument.is_signal_eligible) and str(instrument.asset_type or "unknown") in SUPPORTED_SIGNAL_ASSET_TYPES
    ]

    ticker_stats = _candle_stats_by_ticker(db, [instrument.ticker for instrument in instruments])
    ticker_rows = [
        _ticker_row(
            instrument,
            ticker_stats.get(instrument.ticker, {}),
            min_history=min_history,
            horizon=horizon,
        )
        for instrument in instruments
    ]
    candidate_rows = [
        row for row in ticker_rows if row["is_signal_eligible"] and row["asset_type"] in SUPPORTED_SIGNAL_ASSET_TYPES
    ]

    skip_reasons = Counter(row["skip_reason"] for row in ticker_rows)
    for reason in [
        "no_candles",
        "too_few_candles",
        "insufficient_horizon",
        "invalid_ohlc",
        "not_signal_eligible",
        "unsupported_asset_type",
        "ok",
    ]:
        skip_reasons.setdefault(reason, 0)

    usable_rows = [row for row in candidate_rows if row["skip_reason"] == "ok"]
    usable_candle_counts = [int(row["valid_ohlc_count"] or 0) for row in usable_rows]
    total_possible_samples = sum(int(row["possible_samples"] or 0) for row in usable_rows)
    coverage_level = classify_coverage_level(total_possible_samples, len(usable_rows))

    by_asset_type: dict[str, dict[str, int]] = defaultdict(lambda: {"instruments": 0, "candidate_tickers": 0, "usable_tickers": 0})
    for row in ticker_rows:
        bucket = by_asset_type[str(row["asset_type"])]
        bucket["instruments"] += 1
        if row in candidate_rows:
            bucket["candidate_tickers"] += 1
        if row["skip_reason"] == "ok":
            bucket["usable_tickers"] += 1

    summary = {
        "total_instruments": instrument_counts["total_instruments"],
        "signal_eligible_count": instrument_counts["signal_eligible_count"],
        "tickers_with_candles": candle_overview["tickers_with_candles"],
        "candidate_tickers": len(candidate_rows),
        "candidate_tickers_before_limit": int(supported_eligible_count),
        "usable_tickers": len(usable_rows),
        "total_possible_samples": total_possible_samples,
        "avg_candles_per_usable_ticker": _avg(usable_candle_counts),
        "date_range": {
            "first_date": candle_overview["first_date"],
            "last_date": candle_overview["last_date"],
        },
        "coverage_level": coverage_level,
        "main_blocker": "empty_database" if instrument_counts["total_instruments"] == 0 else _main_blocker(dict(skip_reasons)),
    }

    top_usable = sorted(
        usable_rows,
        key=lambda row: (int(row["possible_samples"] or 0), int(row["valid_ohlc_count"] or 0)),
        reverse=True,
    )[: min(candles_limit, 50)]
    top_skipped = sorted(
        [row for row in ticker_rows if row["skip_reason"] != "ok"],
        key=lambda row: (str(row["skip_reason"]), -int(row["valid_ohlc_count"] or 0), row["ticker"]),
    )[: min(candles_limit, 100)]

    examples: dict[str, list[dict[str, Any]]] = {}
    if include_examples:
        for reason in ["no_candles", "too_few_candles", "insufficient_horizon", "invalid_ohlc", "not_signal_eligible", "unsupported_asset_type"]:
            examples[reason] = [row for row in ticker_rows if row["skip_reason"] == reason][:10]
        examples["usable"] = top_usable[:10]

    return {
        "ok": True,
        "mode": "data_coverage_diagnostics",
        "parameters": {
            "max_tickers": max_tickers,
            "min_history": min_history,
            "horizon": horizon,
            "candles_limit": candles_limit,
            "include_examples": include_examples,
            "supported_signal_asset_types": sorted(SUPPORTED_SIGNAL_ASSET_TYPES),
        },
        "summary": summary,
        "instrument_counts": {
            "total_instruments": instrument_counts["total_instruments"],
            "eligible_true": instrument_counts["eligible_true"],
            "eligible_false": instrument_counts["eligible_false"],
            "eligible_unknown": instrument_counts["eligible_unknown"],
            "signal_eligible_count": instrument_counts["signal_eligible_count"],
        },
        "candles": {
            "total_candles": candle_overview["total_candles"],
            "tickers_with_candles": candle_overview["tickers_with_candles"],
            "date_range": summary["date_range"],
        },
        "skip_reasons": dict(skip_reasons),
        "by_asset_type": dict(by_asset_type) or {
            key: {"instruments": value, "candidate_tickers": 0, "usable_tickers": 0}
            for key, value in instrument_counts["by_asset_type"].items()
        },
        "top_usable_tickers": top_usable,
        "top_skipped_tickers": top_skipped,
        "examples": examples,
        "recommendations": _recommendations(
            summary=summary,
            skip_reasons=dict(skip_reasons),
            min_history=min_history,
            horizon=horizon,
            max_tickers=max_tickers,
            candidate_tickers_before_limit=int(supported_eligible_count),
        ),
        "warnings": warnings,
    }
