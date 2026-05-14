from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import SignalSnapshot
from app.services.signal_model_registry import (
    PRODUCTION_SIGNAL_MODEL_VERSION,
    normalize_signal_model_version,
)
from app.services.signals_data import list_market_signals

SIGNAL_MODEL_VERSION = PRODUCTION_SIGNAL_MODEL_VERSION


def _ensure_table(db: Session) -> None:
    SignalSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )


def _json_dump(value: Any) -> str:
    return json.dumps(
        value if value is not None else {},
        ensure_ascii=False,
    )


def _json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except Exception:
        return default


def signal_snapshot_to_dict(row: SignalSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "ticker": row.ticker,
        "model_version": getattr(row, "model_version", None) or SIGNAL_MODEL_VERSION,
        "trade_date": row.trade_date,
        "price": row.price,
        "change_pct": row.change_pct,
        "action": row.action,
        "label": row.label,
        "entry_price": row.entry_price,
        "target_price": row.target_price,
        "stop_loss": row.stop_loss,
        "confidence_pct": row.confidence_pct,
        "risk_level": row.risk_level,
        "horizon": row.horizon,
        "reasons": _json_load(row.reasons_json, []),
        "technical": _json_load(row.technical_json, {}),
        "signal": _json_load(row.signal_json, {}),
        "ticker_url": f"/tickers/{row.ticker}",
    }


def create_signal_snapshots(
    db: Session,
    limit: int = 100,
    candles_limit: int = 120,
    action: str | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    _ensure_table(db)

    data = list_market_signals(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        action=action,
        model_version=normalize_signal_model_version(model_version),
    )

    rows = data.get("rows") or []
    saved: list[SignalSnapshot] = []

    for item in rows:
        signal = item.get("signal") or {}
        technical = item.get("technical") or {}

        if not signal.get("ok"):
            continue

        row = SignalSnapshot(
            ticker=item.get("ticker"),
            model_version=(
                item.get("model_version")
                or (item.get("signal") or {}).get("model_version")
                or normalize_signal_model_version(model_version)
            ),
            trade_date=item.get("trade_date"),
            price=item.get("price"),
            change_pct=item.get("change_pct"),
            action=signal.get("action") or "unknown",
            label=signal.get("label"),
            entry_price=signal.get("entry_price"),
            target_price=signal.get("target_price"),
            stop_loss=signal.get("stop_loss"),
            confidence_pct=signal.get("confidence_pct"),
            risk_level=signal.get("risk_level"),
            horizon=signal.get("horizon"),
            reasons_json=_json_dump(signal.get("reasons") or []),
            technical_json=_json_dump(technical),
            signal_json=_json_dump(signal),
        )

        db.add(row)
        saved.append(row)

    db.commit()

    for row in saved:
        db.refresh(row)

    return {
        "ok": True,
        "saved_count": len(saved),
        "source_total": len(rows),
        "action_filter": action,
        "saved": [signal_snapshot_to_dict(row) for row in saved],
    }


def list_signal_snapshots(
    db: Session,
    limit: int = 100,
    ticker: str | None = None,
    action: str | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    normalized_model_version = normalize_signal_model_version(model_version) if model_version else None
    _ensure_table(db)

    query = select(SignalSnapshot)

    if ticker:
        query = query.where(SignalSnapshot.ticker == ticker.upper().strip())

    if normalized_model_version:
        query = query.where(SignalSnapshot.model_version == normalized_model_version)

    if action:
        query = query.where(SignalSnapshot.action == action)

    rows = db.scalars(
        query
        .order_by(desc(SignalSnapshot.created_at), desc(SignalSnapshot.id))
        .limit(limit)
    ).all()

    items = [signal_snapshot_to_dict(row) for row in rows]

    summary = {
        "total": len(items),
        "buy_watch": sum(1 for row in items if row.get("action") == "buy_watch"),
        "watch_buy": sum(1 for row in items if row.get("action") == "watch_buy"),
        "hold_watch": sum(1 for row in items if row.get("action") == "hold_watch"),
        "risk_sell_watch": sum(1 for row in items if row.get("action") == "risk_sell_watch"),
    }

    return {
        "summary": summary,
        "rows": items,
    }
