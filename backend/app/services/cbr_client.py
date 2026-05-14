from __future__ import annotations

from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

import httpx


class CbrClient:
    """Minimal CBR XML client for currency rates."""

    DAILY_XML_URL = "https://www.cbr.ru/scripts/XML_daily.asp"

    async def get_daily_fx_rates(self, on_date: date | None = None) -> dict[str, Decimal]:
        params = {}
        if on_date is not None:
            params["date_req"] = on_date.strftime("%d/%m/%Y")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(self.DAILY_XML_URL, params=params)
            response.raise_for_status()

        root = ElementTree.fromstring(response.content)
        result: dict[str, Decimal] = {}
        for valute in root.findall("Valute"):
            char_code = valute.findtext("CharCode")
            nominal = Decimal(valute.findtext("Nominal") or "1")
            value_text = (valute.findtext("Value") or "0").replace(",", ".")
            value = Decimal(value_text) / nominal
            if char_code:
                result[char_code] = value
        return result
