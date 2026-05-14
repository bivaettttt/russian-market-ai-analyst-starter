from __future__ import annotations

from typing import Any

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.models import Candle, SignalSnapshot
from app.services.signal_model_registry import normalize_signal_model_version
from app.services.signals_history import signal_snapshot_to_dict
from app.services.ticker_data import candle_to_dict, enrich_candles_with_changes


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None

        return float(value)
    except Exception:
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _to_float(value)

    if number is None:
        return None

    return round(number, digits)


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None

    return round((current - previous) / previous * 100, 2)


def _get_future_candles(
    db: Session,
    ticker: str,
    trade_date: str | None,
    limit: int = 60,
) -> list[dict[str, Any]]:
    query = select(Candle).where(Candle.ticker == ticker)

    if trade_date:
        query = query.where(Candle.trade_date > trade_date)

    rows = db.scalars(
        query
        .order_by(asc(Candle.trade_date))
        .limit(limit)
    ).all()

    candles = [candle_to_dict(row) for row in rows]
    return enrich_candles_with_changes(candles)


def evaluate_buy_signal(
    signal: dict[str, Any],
    future_candles: list[dict[str, Any]],
    model_version: str | None = None,
) -> dict[str, Any]:
    normalized_model_version = normalize_signal_model_version(model_version) if model_version else None
    snapshot_price = _to_float(signal.get("price"))
    entry_price = _to_float(signal.get("entry_price"))
    target_price = _to_float(signal.get("target_price"))
    stop_loss = _to_float(signal.get("stop_loss"))

    if not future_candles:
        return {
            "status": "pending",
            "label": "Нет будущих свечей",
            "result_pct": None,
            "days_to_result": None,
            "result_date": None,
            "details": "После даты сигнала пока нет свечей для проверки.",
        }

    if entry_price is None:
        entry_price = snapshot_price

    entry_candle_index = None
    entry_date = None

    for index, candle in enumerate(future_candles):
        high = _to_float(candle.get("high"))

        if high is not None and entry_price is not None and high >= entry_price:
            entry_candle_index = index
            entry_date = candle.get("trade_date")
            break

    if entry_candle_index is None:
        last_close = _to_float(future_candles[-1].get("close"))

        return {
            "status": "not_triggered",
            "label": "Вход не сработал",
            "entry_date": None,
            "result_pct": _pct_change(last_close, snapshot_price),
            "days_to_result": len(future_candles),
            "result_date": future_candles[-1].get("trade_date"),
            "details": "Цена пока не достигла условия входа.",
        }

    for offset, candle in enumerate(future_candles[entry_candle_index:], start=1):
        high = _to_float(candle.get("high"))
        low = _to_float(candle.get("low"))

        target_hit = target_price is not None and high is not None and high >= target_price
        stop_hit = stop_loss is not None and low is not None and low <= stop_loss

        if target_hit and stop_hit:
            # В дневной свече нельзя точно понять порядок внутри дня.
            return {
                "status": "ambiguous",
                "label": "Цель и стоп в одной свече",
                "entry_date": entry_date,
                "result_pct": _pct_change(target_price, entry_price),
                "days_to_result": offset,
                "result_date": candle.get("trade_date"),
                "details": "В одной свече были достигнуты и цель, и стоп. Нужны intraday-данные для точного порядка.",
            }

        if target_hit:
            return {
                "status": "success",
                "label": "Цель достигнута",
                "entry_date": entry_date,
                "result_pct": _pct_change(target_price, entry_price),
                "days_to_result": offset,
                "result_date": candle.get("trade_date"),
                "details": "После входа цена достигла цели.",
            }

        if stop_hit:
            return {
                "status": "failed",
                "label": "Стоп достигнут",
                "entry_date": entry_date,
                "result_pct": _pct_change(stop_loss, entry_price),
                "days_to_result": offset,
                "result_date": candle.get("trade_date"),
                "details": "После входа цена достигла стоп-уровня.",
            }

    last_close = _to_float(future_candles[-1].get("close"))

    return {
        "status": "open",
        "label": "Сценарий открыт",
        "entry_date": entry_date,
        "result_pct": _pct_change(last_close, entry_price),
        "days_to_result": len(future_candles) - entry_candle_index,
        "result_date": future_candles[-1].get("trade_date"),
        "details": "Вход был, но цель или стоп пока не достигнуты.",
    }


def evaluate_risk_signal(
    signal: dict[str, Any],
    future_candles: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot_price = _to_float(signal.get("price"))
    target_price = _to_float(signal.get("target_price"))
    stop_loss = _to_float(signal.get("stop_loss"))

    if not future_candles:
        return {
            "status": "pending",
            "label": "Нет будущих свечей",
            "result_pct": None,
            "days_to_result": None,
            "result_date": None,
            "details": "После даты сигнала пока нет свечей для проверки.",
        }

    for index, candle in enumerate(future_candles, start=1):
        high = _to_float(candle.get("high"))
        low = _to_float(candle.get("low"))

        target_hit = target_price is not None and low is not None and low <= target_price
        stop_hit = stop_loss is not None and high is not None and high >= stop_loss

        if target_hit and stop_hit:
            return {
                "status": "ambiguous",
                "label": "Цель и стоп в одной свече",
                "result_pct": _pct_change(target_price, snapshot_price),
                "days_to_result": index,
                "result_date": candle.get("trade_date"),
                "details": "В одной свече были достигнуты и цель снижения, и уровень отмены.",
            }

        if target_hit:
            return {
                "status": "success",
                "label": "Риск снижения подтвердился",
                "result_pct": _pct_change(target_price, snapshot_price),
                "days_to_result": index,
                "result_date": candle.get("trade_date"),
                "details": "Цена снизилась до целевого уровня риска.",
            }

        if stop_hit:
            return {
                "status": "failed",
                "label": "Сценарий снижения отменён",
                "result_pct": _pct_change(stop_loss, snapshot_price),
                "days_to_result": index,
                "result_date": candle.get("trade_date"),
                "details": "Цена ушла выше уровня отмены сценария.",
            }

    last_close = _to_float(future_candles[-1].get("close"))

    return {
        "status": "open",
        "label": "Сценарий открыт",
        "result_pct": _pct_change(last_close, snapshot_price),
        "days_to_result": len(future_candles),
        "result_date": future_candles[-1].get("trade_date"),
        "details": "Цель снижения или уровень отмены пока не достигнуты.",
    }


def evaluate_neutral_signal(
    signal: dict[str, Any],
    future_candles: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot_price = _to_float(signal.get("price"))

    if not future_candles:
        return {
            "status": "pending",
            "label": "Нет будущих свечей",
            "result_pct": None,
            "days_to_result": None,
            "result_date": None,
            "details": "Нейтральный сигнал пока нечем проверять.",
        }

    last_close = _to_float(future_candles[-1].get("close"))

    return {
        "status": "neutral",
        "label": "Нейтральный сигнал",
        "result_pct": _pct_change(last_close, snapshot_price),
        "days_to_result": len(future_candles),
        "result_date": future_candles[-1].get("trade_date"),
        "details": "Для нейтральных сигналов успех/провал не фиксируется.",
    }


def evaluate_signal_snapshot(
    db: Session,
    row: SignalSnapshot,
    future_limit: int = 60,
) -> dict[str, Any]:
    item = signal_snapshot_to_dict(row)

    future_candles = _get_future_candles(
        db=db,
        ticker=row.ticker,
        trade_date=row.trade_date,
        limit=future_limit,
    )

    action = row.action

    if action in {"buy_watch", "watch_buy"}:
        evaluation = evaluate_buy_signal(item, future_candles)
    elif action == "risk_sell_watch":
        evaluation = evaluate_risk_signal(item, future_candles)
    else:
        evaluation = evaluate_neutral_signal(item, future_candles)

    return {
        **item,
        "future_candles_count": len(future_candles),
        "evaluation": evaluation,
    }



def _extract_model_version_from_any(row):
    if isinstance(row, dict):
        return (
            row.get("model_version")
            or ((row.get("signal") or {}).get("model_version"))
            or ((row.get("snapshot") or {}).get("model_version"))
        )

    return getattr(row, "model_version", None)

def list_signal_evaluations(
    db: Session,
    limit: int = 100,
    ticker: str | None = None,
    action: str | None = None,
    model_version: str | None = None,
    future_limit: int = 60,
) -> dict[str, Any]:
    normalized_model_version = normalize_signal_model_version(model_version) if model_version else None
    SignalSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    query = select(SignalSnapshot)

    if ticker:
        query = query.where(SignalSnapshot.ticker == ticker.upper().strip())

    if action:
        query = query.where(SignalSnapshot.action == action)

    if normalized_model_version:
        query = query.where(SignalSnapshot.model_version == normalized_model_version)

    rows = db.scalars(
        query
        .order_by(desc(SignalSnapshot.created_at), desc(SignalSnapshot.id))
        .limit(limit)
    ).all()

    items = [
        evaluate_signal_snapshot(
            db=db,
            row=row,
            future_limit=future_limit,
        )
        for row in rows
    ]

    evaluable = [
        item for item in items
        if (item.get("evaluation") or {}).get("status") in {"success", "failed", "ambiguous"}
    ]

    success_count = sum(1 for item in evaluable if (item.get("evaluation") or {}).get("status") == "success")
    failed_count = sum(1 for item in evaluable if (item.get("evaluation") or {}).get("status") == "failed")

    accuracy_pct = None
    if success_count + failed_count > 0:
        accuracy_pct = round(success_count / (success_count + failed_count) * 100, 2)

    summary = {
        "total": len(items),
        "success": success_count,
        "failed": failed_count,
        "ambiguous": sum(1 for item in items if (item.get("evaluation") or {}).get("status") == "ambiguous"),
        "open": sum(1 for item in items if (item.get("evaluation") or {}).get("status") == "open"),
        "pending": sum(1 for item in items if (item.get("evaluation") or {}).get("status") == "pending"),
        "not_triggered": sum(1 for item in items if (item.get("evaluation") or {}).get("status") == "not_triggered"),
        "neutral": sum(1 for item in items if (item.get("evaluation") or {}).get("status") == "neutral"),
        "accuracy_pct": accuracy_pct,
    }


    return {
        "model_version": normalized_model_version,
        "summary": summary,
        "rows": items,
    }
