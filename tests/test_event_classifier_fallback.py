import pytest

from app.services.event_classifier import EventClassifier


@pytest.mark.asyncio
async def test_fallback_dividend(monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("ollama unavailable")

    from app.services import event_classifier

    monkeypatch.setattr(event_classifier.OllamaClient, "generate_json", broken)
    result = await EventClassifier().analyze("Сбер рекомендовал дивиденды выше ожиданий рынка")
    assert result.event_type == "dividends"
    assert "SBER" in result.affected_assets
