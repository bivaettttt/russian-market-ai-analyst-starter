from app.services.consumer_signals import _build_signal_audit


def test_signal_audit_contract_minimal_payload():
    audit = _build_signal_audit(
        technical={
            "trend": "up",
            "momentum": "positive",
            "volatility_20d_pct": 1.5,
            "recent_high": 110,
            "recent_low": 95,
        },
        signal={
            "action": "watch_buy",
            "target_price": 110,
            "risk_level": "Средний",
        },
        probability_assessment={
            "probability_pct": 55,
            "reliability_level": "Средняя",
            "reliability_score": 60,
        },
        position_sizing={
            "allowed": False,
            "max_position_pct": 0,
            "risk_per_trade_pct": 0,
            "risk_reward_ratio": 1.0,
            "target_distance_pct": 5,
            "stop_distance_pct": 5,
            "risk_flags": [],
        },
        news_assessment={
            "has_events": False,
            "news_effect": "none",
            "risk_flags": [],
        },
        global_news_assessment={
            "has_global_events": False,
            "adjustment_pct": 0.0,
            "tags": [],
            "macro_regime_flags": [],
        },
        ml_probability_result=None,
        decision_gate={
            "action": "watch",
            "recommendation": "Наблюдать",
            "decision": "Нейтральный сигнал",
            "decision_level": "neutral",
        },
        scenario_direction="long",
        scenario_reason="test long scenario",
        source_signal_action="watch_buy",
        source_target_price=110,
        rule_probability_pct=55,
        ml_probability_pct=None,
        ml_weight=0.0,
        ml_adjustment_pct=None,
        ml_regime_multiplier=None,
        ml_regime_reason=None,
        target_probability_pct=55,
        ticker_news_adjustment_pct=0.0,
        global_event_adjustment_pct=0.0,
        market_regime={
            "regime": "neutral",
            "regime_score": 0,
            "long_allowed": True,
            "position_multiplier": 0.9,
            "min_rr_multiplier": 1.1,
            "min_ml_probability_addon": 4,
            "warnings": [],
        },
        market_regime_adjustment_pct=0.0,
    )

    assert audit["final_verdict"] in {"buy", "consider_buy", "watch", "avoid", "downside_risk"}
    assert isinstance(audit["overall_score"], int)
    assert audit["confidence_level"] in {"low", "medium", "high"}
    assert "layer_scores" in audit
    assert "market_regime" in audit["layer_scores"]
    assert audit["human_explanation"]
