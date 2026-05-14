from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PortfolioPosition


DEFAULT_POSITIONS = [
    {"ticker": "SBER", "quantity": 10},
    {"ticker": "LKOH", "quantity": 1},
    {"ticker": "GAZP", "quantity": 50},
    {"ticker": "PLZL", "quantity": 1},
]


def normalize_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for item in positions:
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue

        try:
            quantity = float(item.get("quantity", 0))
        except Exception:
            quantity = 0

        if quantity <= 0:
            continue

        result.append({"ticker": ticker, "quantity": quantity})

    return result


def get_portfolio_positions(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(PortfolioPosition).order_by(PortfolioPosition.ticker)
    ).all()

    if not rows:
        return DEFAULT_POSITIONS

    return [
        {
            "ticker": row.ticker,
            "quantity": row.quantity,
        }
        for row in rows
    ]


def save_portfolio_positions(
    db: Session,
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    clean = normalize_positions(positions)

    # Простая логика: полностью заменяем портфель.
    old_rows = db.scalars(select(PortfolioPosition)).all()
    for row in old_rows:
        db.delete(row)

    db.flush()

    for item in clean:
        db.add(
            PortfolioPosition(
                ticker=item["ticker"],
                quantity=item["quantity"],
            )
        )

    db.commit()

    return get_portfolio_positions(db)
