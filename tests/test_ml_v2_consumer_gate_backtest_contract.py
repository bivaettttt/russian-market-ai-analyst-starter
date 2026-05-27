from app.services.ml_v2_consumer_gate_backtest import build_ml_v2_consumer_gate_backtest


def test_build_ml_v2_consumer_gate_backtest_importable():
    assert callable(build_ml_v2_consumer_gate_backtest)
