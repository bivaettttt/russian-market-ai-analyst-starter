from app.services.moex_data_bootstrap import (
    bootstrap_market_data,
    bootstrap_moex_candles,
    bootstrap_moex_universe,
    build_date_range,
    normalize_tickers,
    parse_moex_history_rows,
    parse_moex_security_rows,
)


def test_bootstrap_functions_are_callable():
    assert callable(bootstrap_moex_universe)
    assert callable(bootstrap_moex_candles)
    assert callable(bootstrap_market_data)


def test_normalize_tickers():
    assert normalize_tickers(None) is None
    assert normalize_tickers("sber, GAZP, sber,,lkoh") == ["SBER", "GAZP", "LKOH"]
    assert normalize_tickers(["moex", "MOEX", ""]) == ["MOEX"]


def test_build_date_range_explicit_dates():
    assert build_date_range(days=30, from_date="2024-01-01", till_date="2024-01-31") == (
        "2024-01-01",
        "2024-01-31",
    )
    assert build_date_range(days=30, from_date="2024-02-01", till_date="2024-01-01") == (
        "2024-01-01",
        "2024-02-01",
    )


def test_parse_moex_security_rows():
    payload = {
        "securities": {
            "columns": ["SECID", "SHORTNAME", "SECNAME", "BOARDID", "LOTSIZE"],
            "data": [["SBER", "Сбер", "Сбербанк", "TQBR", 10]],
        }
    }
    rows = parse_moex_security_rows(payload, default_board="TQBR", market="shares")
    assert rows == [
        {
            "ticker": "SBER",
            "name": "Сбербанк",
            "short_name": "Сбер",
            "board": "TQBR",
            "market": "shares",
            "lot_size": 10,
        }
    ]


def test_parse_moex_history_rows():
    payload = {
        "candles": {
            "columns": ["begin", "open", "high", "low", "close", "volume", "value"],
            "data": [["2024-01-03 00:00:00", 100, 105, 99, 104, 1000, 104000]],
        }
    }
    rows = parse_moex_history_rows(payload, ticker="sber", board="TQBR")
    assert rows == [
        {
            "ticker": "SBER",
            "board": "TQBR",
            "trade_date": "2024-01-03",
            "open": 100,
            "high": 105,
            "low": 99,
            "close": 104,
            "volume": 1000,
            "value": 104000,
        }
    ]
