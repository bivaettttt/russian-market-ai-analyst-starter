import asyncio

from app.services.event_classifier import EventClassifier


def test_fallback_dividend(monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("ollama unavailable")

    from app.services import event_classifier

    monkeypatch.setattr(event_classifier.OllamaClient, "generate_json", broken)
    result = asyncio.run(EventClassifier().analyze("Сбер рекомендовал дивиденды выше ожиданий рынка"))
    assert result.event_type == "dividends"
    assert "SBER" in result.affected_assets
