from app.services.event_aware_setup_research import decay_event_score, event_confirmation_for_long


def test_event_score_decay():
    assert decay_event_score(50, 0, 10) == 50
    assert decay_event_score(50, 5, 10) == 25
    assert decay_event_score(50, 20, 10) == 0


def test_event_confirmation_positive_conflict_none():
    assert event_confirmation_for_long({"direction": "positive", "effective_score": 20}) == "confirmed"
    assert event_confirmation_for_long({"direction": "negative", "effective_score": -20}) == "conflict"
    assert event_confirmation_for_long({"direction": "mixed", "effective_score": 5}) == "neutral"
    assert event_confirmation_for_long(None) == "none"
