from app.services.ml_v2_research_gate import load_ml_v2_research_model, score_ml_v2_research_gate


def test_load_ml_v2_research_model_missing_artifact(tmp_path):
    missing_path = tmp_path / "missing_ml_v2.joblib"

    result = load_ml_v2_research_model(model_path=str(missing_path))

    assert result["ok"] is False
    assert result["status"] == "not_available"
    assert "train_ml_v2" in result["reason"]


def test_score_ml_v2_research_gate_missing_artifact(tmp_path):
    missing_path = tmp_path / "missing_ml_v2.joblib"

    result = score_ml_v2_research_gate(
        candles=[],
        instrument={"ticker": "SBER", "asset_type": "stock"},
        market_regime={"regime": "neutral"},
        threshold_pct=55.0,
        model_path=str(missing_path),
    )

    assert result["ok"] is False
    assert result["status"] == "not_available"
    assert result["probability_pct"] is None
    assert result["gate_passed"] is None
