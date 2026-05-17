from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.config import get_settings


class MoexClient:
    """Small MOEX ISS client for the first MVP."""

    def __init__(self, base_url: str | None = None, timeout: float = 20.0):
        self.settings = get_settings()
        self.base_url = (base_url or self.settings.moex_base_url).rstrip("/")
        self.timeout = timeout

    async def get_daily_candles(
        self,
        ticker: str,
        from_date: date | str,
        to_date: date | str,
        board: str = "TQBR",
        market: str = "shares",
        engine: str = "stock",
    ) -> list[dict[str, Any]]:
        """Fetch daily candles from MOEX ISS and return normalized rows."""
        ticker = ticker.upper().strip()
        url = f"{self.base_url}/engines/{engine}/markets/{market}/boards/{board}/securities/{ticker}/candles.json"
        params: dict[str, Any] = {
            "from": str(from_date),
            "till": str(to_date),
            "interval": 24,
            "iss.meta": "off",
        }

        rows: list[dict[str, Any]] = []
        start = 0
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                response = await client.get(url, params={**params, "start": start})
                response.raise_for_status()
                payload = response.json()
                block = payload.get("candles", {})
                columns = block.get("columns", [])
                data = block.get("data", [])
                if not data:
                    break

                for item in data:
                    raw = dict(zip(columns, item, strict=False))
                    rows.append(
                        {
                            "ticker": ticker,
                            "board": board,
                            "trade_date": str(raw.get("begin", ""))[:10],
                            "open": raw.get("open"),
                            "high": raw.get("high"),
                            "low": raw.get("low"),
                            "close": raw.get("close"),
                            "volume": raw.get("volume"),
                            "value": raw.get("value"),
                        }
                    )

                # MOEX ISS paginates via start. Stop when the page is shorter than common page size.
                if len(data) < 100:
                    break
                start += len(data)

        return rows

    async def get_board_securities(self, board: str = "TQBR") -> list[dict[str, Any]]:
        """Fetch securities listed on a board."""
        url = f"{self.base_url}/engines/stock/markets/shares/boards/{board}/securities.json"
        params = {"iss.meta": "off"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        block = payload.get("securities", {})
        columns = block.get("columns", [])
        data = block.get("data", [])
        result: list[dict[str, Any]] = []
        for item in data:
            raw = dict(zip(columns, item, strict=False))
            result.append(
                {
                    "ticker": raw.get("SECID"),
                    "short_name": raw.get("SHORTNAME"),
                    "name": raw.get("SECNAME"),
                    "isin": raw.get("ISIN"),
                    "board": board,
                    "lot_size": raw.get("LOTSIZE"),
                }
            )
        return result

    async def get_all_share_securities(
        self,
        market: str = "shares",
        engine: str = "stock",
    ) -> list[dict[str, Any]]:
        """Fetch a broad MOEX shares universe across market boards.

        MOEX returns many rows because the same SECID may be traded on several boards.
        The universe service later chooses the preferred board per ticker.
        """
        url = f"{self.base_url}/engines/{engine}/markets/{market}/securities.json"
        params: dict[str, Any] = {"iss.meta": "off"}

        result: list[dict[str, Any]] = []
        start = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                response = await client.get(url, params={**params, "start": start})
                response.raise_for_status()
                payload = response.json()

                block = payload.get("securities", {})
                columns = block.get("columns", [])
                data = block.get("data", [])

                if not data:
                    break

                for item in data:
                    raw = dict(zip(columns, item, strict=False))
                    board = raw.get("BOARDID") or raw.get("BOARDID_LIST") or raw.get("PRIMARY_BOARDID") or ""
                    result.append(
                        {
                            "ticker": raw.get("SECID"),
                            "short_name": raw.get("SHORTNAME"),
                            "name": raw.get("SECNAME") or raw.get("NAME"),
                            "isin": raw.get("ISIN"),
                            "board": board or "TQBR",
                            "lot_size": raw.get("LOTSIZE") or raw.get("LOTVALUE") or 1,
                        }
                    )

                if len(data) < 100:
                    break
                start += len(data)

        return result

