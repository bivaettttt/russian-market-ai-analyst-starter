from __future__ import annotations

import argparse
import asyncio

from app.db import SessionLocal
from app.services.market_universe import update_candles_for_universe


async def run(days: int, max_tickers: int, board: str | None, pause_seconds: float) -> None:
    db = SessionLocal()
    try:
        result = await update_candles_for_universe(
            db=db,
            days=days,
            max_tickers=max_tickers,
            board=board,
            pause_seconds=pause_seconds,
        )
        print(result)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=420)
    parser.add_argument("--max-tickers", type=int, default=50)
    parser.add_argument("--board", default=None)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    args = parser.parse_args()
    asyncio.run(run(args.days, args.max_tickers, args.board, args.pause_seconds))


if __name__ == "__main__":
    main()
