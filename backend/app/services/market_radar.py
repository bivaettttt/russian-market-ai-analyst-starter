from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Candle


@dataclass
class TickerMove:
    ticker: str
    board: str
    trade_date: date
    close: float
    previous_close: float
    change_abs: float
    change_pct: float
    volume: float | None
    value: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "board": self.board,
            "trade_date": self.trade_date.isoformat(),
            "close": self.close,
            "previous_close": self.previous_close,
            "change_abs": round(self.change_abs, 4),
            "change_pct": round(self.change_pct, 2),
            "volume": self.volume,
            "value": self.value,
        }


def build_market_radar(db: Session, limit: int = 10) -> dict[str, Any]:
    tickers = db.scalars(select(Candle.ticker).distinct().order_by(Candle.ticker)).all()

    raw_moves: list[TickerMove] = []
    skipped: list[str] = []

    for ticker in tickers:
        candles = db.scalars(
            select(Candle)
            .where(Candle.ticker == ticker)
            .order_by(desc(Candle.trade_date))
            .limit(2)
        ).all()

        if len(candles) < 2:
            skipped.append(ticker)
            continue

        latest, previous = candles[0], candles[1]

        if latest.close is None or previous.close in (None, 0):
            skipped.append(ticker)
            continue

        change_abs = latest.close - previous.close
        change_pct = (change_abs / previous.close) * 100

        raw_moves.append(
            TickerMove(
                ticker=ticker,
                board=latest.board,
                trade_date=latest.trade_date,
                close=latest.close,
                previous_close=previous.close,
                change_abs=change_abs,
                change_pct=change_pct,
                volume=latest.volume,
                value=latest.value,
            )
        )

    if not raw_moves:
        return {
            "market": "MOEX / Russian equities",
            "tickers_analyzed": 0,
            "tickers_skipped": skipped,
            "latest_date": None,
            "stale_tickers": [],
            "breadth": {"up": 0, "down": 0, "flat": 0},
            "top_gainers": [],
            "top_losers": [],
            "weakest_movers": [],
            "most_traded_by_value": [],
            "summary": "Недостаточно данных для рыночного радара.",
        }

    market_latest_date = max(item.trade_date for item in raw_moves)

    moves = [item for item in raw_moves if item.trade_date == market_latest_date]
    stale = [item for item in raw_moves if item.trade_date != market_latest_date]

    gainers = sorted(
        [item for item in moves if item.change_pct > 0],
        key=lambda item: item.change_pct,
        reverse=True,
    )

    losers = sorted(
        [item for item in moves if item.change_pct < 0],
        key=lambda item: item.change_pct,
    )

    weakest_movers = sorted(moves, key=lambda item: item.change_pct)
    most_traded = sorted(moves, key=lambda item: item.value or 0, reverse=True)

    up_count = sum(1 for item in moves if item.change_pct > 0)
    down_count = sum(1 for item in moves if item.change_pct < 0)
    flat_count = sum(1 for item in moves if item.change_pct == 0)

    return {
        "market": "MOEX / Russian equities",
        "tickers_analyzed": len(moves),
        "tickers_skipped": skipped,
        "latest_date": market_latest_date.isoformat(),
        "stale_tickers": [
            {
                "ticker": item.ticker,
                "last_trade_date": item.trade_date.isoformat(),
                "reason": "ticker_latest_date_is_older_than_market_latest_date",
            }
            for item in stale
        ],
        "breadth": {
            "up": up_count,
            "down": down_count,
            "flat": flat_count,
        },
        "top_gainers": [item.as_dict() for item in gainers[:limit]],
        "top_losers": [item.as_dict() for item in losers[:limit]],
        "weakest_movers": [item.as_dict() for item in weakest_movers[:limit]],
        "most_traded_by_value": [item.as_dict() for item in most_traded[:limit]],
        "summary": build_plain_summary(
            gainers=gainers,
            losers=losers,
            weakest_movers=weakest_movers,
            most_traded=most_traded,
            up_count=up_count,
            down_count=down_count,
            flat_count=flat_count,
            stale_count=len(stale),
        ),
    }


def build_plain_summary(
    gainers: list[TickerMove],
    losers: list[TickerMove],
    weakest_movers: list[TickerMove],
    most_traded: list[TickerMove],
    up_count: int,
    down_count: int,
    flat_count: int,
    stale_count: int,
) -> str:
    parts = [
        f"Рыночная ширина: растут {up_count}, снижаются {down_count}, без изменений {flat_count}."
    ]

    if gainers:
        leader = gainers[0]
        parts.append(f"Лидер роста: {leader.ticker} ({leader.change_pct:.2f}%).")

    if losers:
        laggard = losers[0]
        parts.append(f"Лидер снижения: {laggard.ticker} ({laggard.change_pct:.2f}%).")
    elif weakest_movers:
        weakest = weakest_movers[0]
        parts.append(
            f"Снижающихся бумаг нет. Самая слабая динамика: {weakest.ticker} ({weakest.change_pct:.2f}%)."
        )

    if most_traded:
        volume_leader = most_traded[0]
        value_bln = (volume_leader.value or 0) / 1_000_000_000
        parts.append(f"Максимальный оборот: {volume_leader.ticker} ({value_bln:.2f} млрд руб.).")

    if stale_count:
        parts.append(f"Исключено устаревших тикеров: {stale_count}.")

    return " ".join(parts)
