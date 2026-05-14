from __future__ import annotations

import argparse
import asyncio
from datetime import date

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Candle
from app.services.moex_client import MoexClient


async def ingest(ticker: str, from_date: date, to_date: date, board: str = "TQBR") -> int:
    rows = await MoexClient().get_daily_candles(ticker, from_date, to_date, board=board)
    db = SessionLocal()
    try:
        saved = 0
        for row in rows:
            trade_date = date.fromisoformat(row["trade_date"])
            existing = db.scalar(
                select(Candle).where(
                    Candle.ticker == row["ticker"],
                    Candle.board == row["board"],
                    Candle.trade_date == trade_date,
                )
            )
            if existing:
                existing.open = row.get("open")
                existing.high = row.get("high")
                existing.low = row.get("low")
                existing.close = row.get("close")
                existing.volume = row.get("volume")
                existing.value = row.get("value")
            else:
                db.add(
                    Candle(
                        ticker=row["ticker"],
                        board=row["board"],
                        trade_date=trade_date,
                        open=row.get("open"),
                        high=row.get("high"),
                        low=row.get("low"),
                        close=row.get("close"),
                        volume=row.get("volume"),
                        value=row.get("value"),
                    )
                )
            saved += 1
        db.commit()
        return saved
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--board", default="TQBR")
    args = parser.parse_args()
    saved = asyncio.run(
        ingest(
            ticker=args.ticker,
            from_date=date.fromisoformat(args.from_date),
            to_date=date.fromisoformat(args.to_date),
            board=args.board,
        )
    )
    print(f"Saved {saved} candles for {args.ticker.upper()}")


if __name__ == "__main__":
    main()
