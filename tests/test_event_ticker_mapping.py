from app.services.event_ticker_mapping import (
    classify_event_family,
    map_event_to_market_impact,
    normalize_event_tags,
)


def test_rate_cut_maps_to_rates_positive():
    mapped = map_event_to_market_impact({"title": "ЦБ снизил ключевую ставку", "text": "Смягчение ДКП поддерживает рынок"})
    assert mapped["event_family"] == "rates"
    assert mapped["direction"] == "positive"
    assert mapped["score"] > 0


def test_sanctions_relief_positive_and_new_sanctions_negative():
    relief = classify_event_family({"title": "Снятие санкций с банков"})
    sanctions = classify_event_family({"title": "Новые санкции против РФ и банков"})
    assert relief["event_family"] == "sanctions"
    assert relief["direction"] == "positive"
    assert sanctions["event_family"] == "sanctions"
    assert sanctions["direction"] == "negative"


def test_oil_price_up_positive_for_oil_gas():
    mapped = map_event_to_market_impact({"title": "Brent вырос, oil price up after supply shock"}, instrument={"sector": "oil_gas"})
    assert mapped["event_family"] == "oil_gas"
    assert mapped["direction"] == "positive"
    assert mapped["score"] > 0


def test_rub_weakness_positive_exporters():
    mapped = map_event_to_market_impact({"title": "Ослабление рубля поддержит exporters"}, instrument={"sector": "exporters"})
    assert mapped["event_family"] == "fx"
    assert mapped["direction"] == "positive"
    assert mapped["score"] > 0


def test_dividend_cut_negative():
    mapped = classify_event_family({"title": "Совет директоров сообщил: дивиденды отменены"})
    assert mapped["event_family"] == "dividend"
    assert mapped["direction"] == "negative"
    assert mapped["score"] < 0


def test_normalize_tags_uses_title_text_only():
    tags = normalize_event_tags({"title": "Компания объявила buyback", "text": ""})
    assert "buyback" in tags
