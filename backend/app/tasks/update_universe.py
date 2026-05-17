from __future__ import annotations

import argparse
import asyncio

from app.db import SessionLocal
from app.services.market_universe import update_moex_universe


async def run(boards: str, include_all_market: bool) -> None:
    db = SessionLocal()
    try:
        board_list = [item.strip().upper() for item in boards.split(",") if item.strip()]
        result = await update_moex_universe(
            db=db,
            boards=board_list or ["TQBR"],
            include_all_market=include_all_market,
        )
        print(result)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boards", default="TQBR,TQTF,TQIF,TQPI")
    parser.add_argument("--no-all-market", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(boards=args.boards, include_all_market=not args.no_all_market))


if __name__ == "__main__":
    main()
