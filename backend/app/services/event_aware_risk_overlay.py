from __future__ import annotations

from typing import Any

from app.services.event_aware_rule_search import (
    enrich_event_rule_sample,
    generate_event_aware_rules,
    sample_matches_event_rule,
)
from app.services.event_ticker_mapping import map_event_to_market_impact


EVENT_RISK_OVERLAY_ALLOWED_MODES = {"disabled", "diagnostic_only", "soft_adjust", "experimental_downgrade"}
CONSERVATIVE_EVENT_OVERLAY_ALLOWED_MODES = {"diagnostic_only", "soft_adjust"}
EVENT_RISK_RESEARCH_BASIS = (
    "Rule stability diagnostics found stable event-aware risk rules, but hard filtering failed due to "
    "winner_miss_rate; overlay uses soft risk adjustment."
)
CONSERVATIVE_EVENT_RISK_OVERLAY_RESEARCH_BASIS = (
    "Conservative overlay config cons_t20_40_60_80_m95_e80_h65_x40_w100 was selected by 4/4 folds "
    "in conservative calibration: avg PF delta +0.068, avg return delta +0.187%, stop-hit exposure "
    "delta -1.81 p.p., avg multiplier 0.556. Research/paper-trading only."
)
EVENT_RISK_LONG_ACTIONS = {"buy", "consider_buy", "watch_ml_confirmed", "buy_watch", "watch_buy"}

CONSERVATIVE_EVENT_RISK_OVERLAY_CONFIG: dict[str, Any] = {
    "config_id": "cons_t20_40_60_80_m95_e80_h65_x40_w100",
    "moderate_threshold": 20,
    "elevated_threshold": 40,
    "high_threshold": 60,
    "extreme_threshold": 80,
    "moderate_multiplier": 0.95,
    "elevated_multiplier": 0.80,
    "high_multiplier": 0.65,
    "extreme_multiplier": 0.40,
    "winner_miss_penalty": 1.0,
    "min_multiplier": 0.40,
    "profile": "conservative",
    "research_source": "conservative_event_risk_overlay_calibration",
}

DEFAULT_STABLE_RISK_RULE_IDS = {
    "event_score_abs_ge_15_any_setup",
    "macro_rates_any_setup",
    "risk_fx_any_setup",
    "commodity_any_setup",
    "confirmed_positive_any_setup",
    "quality_like_confirmed",
    "conflict_negative_rebound_like",
    "rebound_like_conflict",
}

DEFAULT_STABLE_RULE_METRICS: dict[str, dict[str, Any]] = {
    "event_score_abs_ge_15_any_setup": {
        "recommended_use": "stable_risk_filter",
        "stability_score": 70,
        "avg_avoid_long_benefit_pct": 2.15,
        "avg_missed_upside_pct": 1.51,
        "stop_hit_lift_vs_baseline": 5.0,
        "failure_modes": ["winner_miss_rate"],
    },
    "macro_rates_any_setup": {
        "recommended_use": "diagnostic_only",
        "stability_score": 45,
        "avg_avoid_long_benefit_pct": 1.9,
        "avg_missed_upside_pct": 1.6,
        "stop_hit_lift_vs_baseline": 2.0,
        "failure_modes": ["winner_miss_rate"],
    },
    "risk_fx_any_setup": {
        "recommended_use": "regime_specific_filter",
        "stability_score": 52,
        "avg_avoid_long_benefit_pct": 2.1,
        "avg_missed_upside_pct": 1.55,
        "stop_hit_lift_vs_baseline": 4.0,
        "failure_modes": ["winner_miss_rate"],
    },
    "commodity_any_setup": {
        "recommended_use": "stable_risk_filter",
        "stability_score": 62,
        "avg_avoid_long_benefit_pct": 2.4,
        "avg_missed_upside_pct": 1.4,
        "stop_hit_lift_vs_baseline": 4.5,
        "failure_modes": [],
    },
    "confirmed_positive_any_setup": {
        "recommended_use": "diagnostic_only",
        "stability_score": 45,
        "avg_avoid_long_benefit_pct": 2.0,
        "avg_missed_upside_pct": 1.7,
        "stop_hit_lift_vs_baseline": 1.0,
        "failure_modes": ["winner_miss_rate"],
    },
    "quality_like_confirmed": {
        "recommended_use": "stable_risk_filter",
        "stability_score": 65,
        "avg_avoid_long_benefit_pct": 2.67,
        "avg_missed_upside_pct": 1.16,
        "stop_hit_lift_vs_baseline": 14.0,
        "failure_modes": [],
    },
    "conflict_negative_rebound_like": {
        "recommended_use": "diagnostic_only",
        "stability_score": 35,
        "avg_avoid_long_benefit_pct": 1.8,
        "avg_missed_upside_pct": 1.5,
        "stop_hit_lift_vs_baseline": 2.0,
        "failure_modes": [],
    },
    "rebound_like_conflict": {
        "recommended_use": "diagnostic_only",
        "stability_score": 35,
        "avg_avoid_long_benefit_pct": 1.8,
        "avg_missed_upside_pct": 1.5,
        "stop_hit_lift_vs_baseline": 2.0,
        "failure_modes": [],
    },
}


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _to_float(value)
    return round(number, digits) if number is not None else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_event_risk_overlay_mode(mode: str | None) -> str:
    value = str(mode or "diagnostic_only").strip().lower()
    if value not in EVENT_RISK_OVERLAY_ALLOWED_MODES:
        return "diagnostic_only"
    return value


def normalize_conservative_event_overlay_mode(mode: str | None) -> str:
    value = str(mode or "soft_adjust").strip().lower()
    if value not in CONSERVATIVE_EVENT_OVERLAY_ALLOWED_MODES:
        return "soft_adjust"
    return value


def get_conservative_event_risk_overlay_config() -> dict[str, Any]:
    return dict(CONSERVATIVE_EVENT_RISK_OVERLAY_CONFIG)


def _risk_level(score: float) -> str:
    if score >= 80:
        return "extreme"
    if score >= 60:
        return "high"
    if score >= 40:
        return "elevated"
    if score >= 20:
        return "moderate"
    return "low"


def _risk_mapping(level: str, *, mode: str) -> dict[str, float]:
    mappings = {
        "low": (1.0, 0.0, 1.0),
        "moderate": (0.75, 3.0, 1.1),
        "elevated": (0.5, 5.0, 1.2),
        "high": (0.35, 8.0, 1.35),
        "extreme": (0.25, 10.0, 1.5),
    }
    multiplier, addon, rr = mappings.get(level, mappings["low"])
    if mode == "experimental_downgrade" and level == "extreme":
        multiplier = 0.0
    return {
        "position_multiplier": multiplier,
        "min_probability_addon_pct": addon,
        "min_rr_multiplier": rr,
    }


def _risk_level_for_config(score: float, config: dict[str, Any]) -> str:
    if score >= (_to_float(config.get("extreme_threshold")) or 80):
        return "extreme"
    if score >= (_to_float(config.get("high_threshold")) or 60):
        return "high"
    if score >= (_to_float(config.get("elevated_threshold")) or 40):
        return "elevated"
    if score >= (_to_float(config.get("moderate_threshold")) or 20):
        return "moderate"
    return "low"


def _risk_mapping_for_config(level: str, *, mode: str, config: dict[str, Any]) -> dict[str, float]:
    if level == "low":
        multiplier = 1.0
    else:
        multiplier = _to_float(config.get(f"{level}_multiplier")) or 1.0
        min_multiplier = _to_float(config.get("min_multiplier"))
        if min_multiplier is not None:
            multiplier = max(min_multiplier, multiplier)
    if mode == "experimental_downgrade" and level == "extreme":
        multiplier = 0.0
    return {
        "position_multiplier": _clamp(multiplier, 0.0, 1.0),
        "min_probability_addon_pct": {"low": 0.0, "moderate": 3.0, "elevated": 5.0, "high": 8.0, "extreme": 10.0}.get(level, 0.0),
        "min_rr_multiplier": {"low": 1.0, "moderate": 1.1, "elevated": 1.2, "high": 1.35, "extreme": 1.5}.get(level, 1.0),
    }


def _event_context_modifier(event_context: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not isinstance(event_context, dict):
        return 0.0, []
    score = _to_float(event_context.get("event_score")) or 0.0
    family = str(event_context.get("event_family") or "").lower()
    direction = str(event_context.get("event_direction") or "").lower()
    confirmation = str(event_context.get("event_confirmation") or "").lower()
    reasons: list[str] = []
    modifier = 0.0
    if direction == "negative" and abs(score) >= 30:
        modifier += 8
        reasons.append("negative high-score event")
    if family in {"geopolitics", "sanctions"} and direction == "negative":
        modifier += 8
        reasons.append("geopolitics/sanctions risk-off event")
    if family in {"rates", "macro", "inflation"} and direction == "negative":
        modifier += 5
        reasons.append("negative macro/rates event")
    if direction == "positive" and confirmation == "confirmed":
        modifier -= 5
        reasons.append("confirmed positive event reduces overlay risk")
    return modifier, reasons


def _market_regime_modifier(market_regime: dict[str, Any] | None) -> tuple[float, list[str]]:
    regime = str((market_regime or {}).get("regime") or "").lower()
    if "risk_off" in regime:
        return 10.0, ["market regime risk_off"]
    if "risk_on" in regime:
        return -5.0, ["market regime risk_on reduces overlay risk"]
    return 0.0, []


def _rule_contribution(rule: dict[str, Any]) -> tuple[float, list[str]]:
    use = str(rule.get("recommended_use") or "").lower()
    if use == "stable_risk_filter":
        contribution = 20.0
    elif use == "regime_specific_filter":
        contribution = 12.0
    elif use == "diagnostic_only":
        contribution = 5.0
    else:
        contribution = 4.0

    reasons = [f"{rule.get('rule_id') or 'rule'}: {use or 'fallback'}"]
    avoid = _to_float(rule.get("avg_avoid_long_benefit_pct")) or 0.0
    missed = _to_float(rule.get("avg_missed_upside_pct")) or 0.0
    stop_lift = _to_float(rule.get("stop_hit_lift_vs_baseline")) or 0.0
    downside_rate = _to_float(rule.get("downside_flag_rate_pct")) or 0.0
    stability = _to_float(rule.get("stability_score")) or 0.0

    if avoid > missed:
        contribution += 8
        reasons.append("avoid benefit exceeds missed upside")
    if stop_lift > 5:
        contribution += 8
        reasons.append("stop-hit lift above baseline")
    if downside_rate >= 60:
        contribution += 5
        reasons.append("high downside flag rate")
    if stability > 50:
        contribution += 8
        reasons.append("stability score above 50")
    elif stability >= 25:
        contribution += 5
        reasons.append("stability score 25-50")

    contribution = _clamp(contribution, 0.0, 30.0)
    failure_modes = {str(item) for item in (rule.get("failure_modes") or [])}
    if {"missed_winners_high", "winner_miss_rate"}.intersection(failure_modes):
        contribution -= 8
        reasons.append("winner miss-rate penalty")
    concentration = str(rule.get("concentration_label") or rule.get("stability_label") or "").lower()
    if concentration in {"high", "extreme"}:
        contribution -= 8
        reasons.append("concentration penalty")
    return _clamp(contribution, 0.0, 30.0), reasons


def score_event_risk_overlay(
    *,
    matched_rules: list[dict[str, Any]],
    event_context: dict[str, Any] | None = None,
    market_regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 0.0
    reasons: list[str] = []
    top_rules: list[dict[str, Any]] = []
    for rule in matched_rules or []:
        contribution, rule_reasons = _rule_contribution(rule)
        if contribution <= 0:
            continue
        score += contribution
        reasons.extend(rule_reasons[:3])
        top_rules.append(
            {
                "rule_id": rule.get("rule_id"),
                "recommended_use": rule.get("recommended_use"),
                "stability_score": rule.get("stability_score"),
                "contribution": _round(contribution, 2),
            }
        )
    modifier, modifier_reasons = _event_context_modifier(event_context)
    score += modifier
    reasons.extend(modifier_reasons)
    regime_modifier, regime_reasons = _market_regime_modifier(market_regime)
    score += regime_modifier
    reasons.extend(regime_reasons)
    score = _round(_clamp(score, 0.0, 100.0), 1) or 0.0
    return {
        "risk_score": score,
        "risk_level": _risk_level(score),
        "risk_reasons": reasons[:12],
        "top_risk_rules": sorted(top_rules, key=lambda row: row.get("contribution") or 0, reverse=True)[:5],
    }


def build_event_aware_risk_overlay(
    *,
    event_context: dict[str, Any] | None = None,
    stability_rules: list[dict[str, Any]] | None = None,
    matched_rules: list[dict[str, Any]] | None = None,
    market_regime: dict[str, Any] | None = None,
    base_probability_pct: float | None = None,
    base_risk_reward_ratio: float | None = None,
    threshold_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = normalize_event_risk_overlay_mode((threshold_config or {}).get("mode") or "diagnostic_only")
    if mode == "disabled":
        return {
            "ok": True,
            "status": "disabled",
            "mode": "disabled",
            "risk_score": 0.0,
            "risk_level": "low",
            "position_multiplier": 1.0,
            "min_probability_addon_pct": 0.0,
            "min_rr_multiplier": 1.0,
            "matched_rules_count": 0,
            "matched_rule_ids": [],
            "top_risk_rules": [],
            "risk_reasons": ["event risk overlay disabled"],
            "warning": "",
            "research_basis": EVENT_RISK_RESEARCH_BASIS,
            "limitations": [],
        }
    rules = matched_rules if matched_rules is not None else stability_rules or []
    scored = score_event_risk_overlay(matched_rules=rules, event_context=event_context, market_regime=market_regime)
    config = threshold_config or {}
    custom_config = bool(config.get("config_id") and config.get("profile"))
    score_value = _to_float(scored.get("risk_score")) or 0.0
    if custom_config:
        score_value = _clamp(score_value * (_to_float(config.get("winner_miss_penalty")) or 1.0), 0.0, 100.0)
        scored["risk_score"] = _round(score_value, 1)
        level = _risk_level_for_config(score_value, config)
        mapping = _risk_mapping_for_config(level, mode=mode, config=config)
    else:
        level = str(scored.get("risk_level") or "low")
        mapping = _risk_mapping(level, mode=mode)
    base_probability = _to_float(base_probability_pct)
    base_rr = _to_float(base_risk_reward_ratio)
    probability_addon = mapping["min_probability_addon_pct"]
    rr_multiplier = mapping["min_rr_multiplier"]
    return {
        "ok": True,
        "status": "active" if rules or event_context else "not_available",
        "mode": mode,
        "config_id": config.get("config_id"),
        "config_profile": config.get("profile"),
        "research_source": config.get("research_source"),
        "risk_score": scored["risk_score"],
        "risk_level": level,
        "position_multiplier": mapping["position_multiplier"],
        "min_probability_addon_pct": probability_addon,
        "min_rr_multiplier": rr_multiplier,
        "effective_min_probability_pct": _round(base_probability + probability_addon, 1) if base_probability is not None else None,
        "effective_min_rr": _round(base_rr * rr_multiplier, 2) if base_rr is not None else None,
        "matched_rules_count": len(rules),
        "matched_rule_ids": [rule.get("rule_id") for rule in rules if rule.get("rule_id")],
        "top_risk_rules": scored["top_risk_rules"],
        "risk_reasons": scored["risk_reasons"] or ["No matching event-aware risk rules."],
        "warning": "Event risk overlay is research-only and disabled unless explicitly requested.",
        "research_basis": CONSERVATIVE_EVENT_RISK_OVERLAY_RESEARCH_BASIS if custom_config else EVENT_RISK_RESEARCH_BASIS,
        "limitations": [
            "Deterministic event-aware overlay, not a production default.",
            "Hard filtering failed walk-forward; soft sizing still needs paper trading validation.",
        ],
    }


def _apply_overlay_to_position_sizing(position_sizing: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(position_sizing or {})
    multiplier = _to_float(overlay.get("position_multiplier"))
    base_size = _to_float(result.get("max_position_pct"))
    if multiplier is not None:
        result["event_risk_position_multiplier"] = _round(multiplier, 2)
    if base_size is not None and multiplier is not None:
        result["event_risk_adjusted_max_position_pct"] = _round(base_size * multiplier, 2)
    flags = list(result.get("risk_flags") or [])
    if multiplier is not None and multiplier < 1:
        flags.append(f"event_risk_position_multiplier={multiplier:.2f}")
    result["risk_flags"] = flags
    return result


def apply_event_risk_overlay_to_signal(
    *,
    forecast: dict[str, Any],
    overlay: dict[str, Any],
    mode: str = "diagnostic_only",
) -> dict[str, Any]:
    result = dict(forecast or {})
    overlay_mode = normalize_event_risk_overlay_mode(mode)
    if overlay_mode == "disabled":
        result["event_risk_overlay"] = overlay
        result["event_risk_overlay_mode"] = "disabled"
        result["event_risk_action_effect"] = "none_disabled"
        result["event_risk_final_action_changed"] = False
        return result

    original_action = str(result.get("action") or result.get("consumer_action") or "")
    original_recommendation = result.get("recommendation")
    changed = False
    action_effect = "diagnostic_warning" if overlay_mode == "diagnostic_only" else "soft_adjusted"
    risk_level = str(overlay.get("risk_level") or "low")
    if overlay_mode == "experimental_downgrade" and original_action in EVENT_RISK_LONG_ACTIONS and risk_level in {"high", "extreme"}:
        result["action"] = "watch_event_risk"
        result["consumer_action"] = "watch_event_risk"
        result["recommendation"] = "Наблюдать из-за event risk"
        result["decision"] = "Event risk overlay"
        result["decision_level"] = "warning"
        result["decision_reason"] = "Experimental event risk overlay downgraded a long candidate to downside watch."
        result["is_buy_candidate"] = False
        changed = True
        action_effect = "experimental_downgraded"
    else:
        result.setdefault("consumer_action", result.get("action"))

    if overlay_mode in {"soft_adjust", "experimental_downgrade"}:
        result["position_sizing"] = _apply_overlay_to_position_sizing(result.get("position_sizing") or {}, overlay)

    result.update(
        {
            "event_risk_overlay": overlay,
            "event_risk_score": overlay.get("risk_score"),
            "event_risk_level": overlay.get("risk_level"),
            "event_risk_position_multiplier": overlay.get("position_multiplier"),
            "event_risk_min_probability_addon_pct": overlay.get("min_probability_addon_pct"),
            "event_risk_min_rr_multiplier": overlay.get("min_rr_multiplier"),
            "event_risk_effective_min_probability_pct": overlay.get("effective_min_probability_pct"),
            "event_risk_effective_min_rr": overlay.get("effective_min_rr"),
            "event_risk_matched_rule_ids": overlay.get("matched_rule_ids") or [],
            "event_risk_reasons": overlay.get("risk_reasons") or [],
            "event_risk_overlay_mode": overlay_mode,
            "event_risk_original_action": original_action,
            "event_risk_original_recommendation": original_recommendation,
            "event_risk_final_action_changed": changed,
            "event_risk_action_effect": action_effect,
            "event_risk_research_basis": overlay.get("research_basis"),
        }
    )
    audit = dict(result.get("signal_audit") or {})
    layer_scores = dict(audit.get("layer_scores") or {})
    layer_status = "neutral"
    if risk_level in {"elevated"}:
        layer_status = "warning"
    elif risk_level in {"high", "extreme"}:
        layer_status = "negative"
    layer_scores["event_risk_overlay"] = {
        "status": layer_status,
        "score": overlay.get("risk_score"),
        "reason": "; ".join((overlay.get("risk_reasons") or [])[:3]),
        "diagnostics": overlay,
    }
    audit["layer_scores"] = layer_scores
    warning_layers = list(audit.get("warning_layers") or [])
    if risk_level in {"elevated", "high", "extreme"} and "event_risk_overlay" not in warning_layers:
        warning_layers.append("event_risk_overlay")
    audit["warning_layers"] = warning_layers
    if changed:
        blocked_by = list(audit.get("blocked_by") or [])
        if "event_risk_overlay" not in blocked_by:
            blocked_by.append("event_risk_overlay")
        audit["blocked_by"] = blocked_by
    result["signal_audit"] = audit
    result["audit_blocked_by"] = audit.get("blocked_by") or []
    result["audit_top_weaknesses"] = audit.get("top_weaknesses") or []
    return result


def _event_sample_from_context(
    *,
    forecast: dict[str, Any],
    event_impact: dict[str, Any],
    confirmation: str,
) -> dict[str, Any]:
    action = str(forecast.get("action") or forecast.get("consumer_action") or "")
    scenario = str(forecast.get("scenario_direction") or "")
    setup_family = forecast.get("setup_family")
    if not setup_family:
        if action in {"buy", "consider_buy", "watch_ml_confirmed", "buy_watch", "watch_buy"} or scenario == "long":
            setup_family = "regime_supported_long"
        elif action in {"watch", "watch_market_risk", "watch_bad_rr"}:
            setup_family = "low_volatility_quality"
        else:
            setup_family = "none"
    setup_score = _to_float(forecast.get("reliability_score")) or _to_float(forecast.get("target_probability_pct")) or 50.0
    return {
        "ticker": forecast.get("ticker"),
        "sector": forecast.get("sector"),
        "setup_family": setup_family,
        "setup_score": setup_score,
        "event_family": event_impact.get("event_family"),
        "event_direction": event_impact.get("direction"),
        "event_confirmation": confirmation,
        "event_scope": event_impact.get("impact_scope"),
        "event_score": event_impact.get("score"),
        "event_id": event_impact.get("event_id") or event_impact.get("id"),
        "event_title": event_impact.get("event_title") or event_impact.get("title"),
        "sample_type": "live_overlay",
    }


def _fallback_stability_rules() -> list[dict[str, Any]]:
    generated = {rule.get("rule_id"): rule for rule in generate_event_aware_rules(max_rules=120)}
    rows: list[dict[str, Any]] = []
    for rule_id in DEFAULT_STABLE_RISK_RULE_IDS:
        rule = dict(generated.get(rule_id) or {"rule_id": rule_id, "description": "Fallback event risk rule."})
        rule.update(DEFAULT_STABLE_RULE_METRICS.get(rule_id, {}))
        rule.setdefault("source", "fallback_default_rules")
        rows.append(rule)
    return rows


def match_event_risk_rules_for_signal(
    *,
    forecast: dict[str, Any],
    related_events: list[dict[str, Any]] | None = None,
    global_events: list[dict[str, Any]] | None = None,
    setup_context: dict[str, Any] | None = None,
    stability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    if isinstance(stability_result, dict):
        rules = list(stability_result.get("stable_rules") or []) + list(stability_result.get("moderate_rules") or [])
    if not rules:
        rules = _fallback_stability_rules()
    events = [*(related_events or []), *(global_events or [])]
    if not events:
        return {
            "ok": True,
            "source": "fallback_default_rules",
            "matched_rules": [],
            "matched_rules_count": 0,
            "event_context": None,
            "warnings": ["no related/global events for overlay"],
        }
    instrument = {
        "ticker": forecast.get("ticker"),
        "sector": forecast.get("sector"),
        "asset_type": forecast.get("asset_type"),
        **(setup_context or {}),
    }
    best_sample: dict[str, Any] | None = None
    best_impact: dict[str, Any] | None = None
    best_score = -1.0
    for event in events[:12]:
        impact = map_event_to_market_impact(event, instrument=instrument)
        impact["event_id"] = event.get("id") or event.get("event_id")
        impact["event_title"] = event.get("title")
        direction = str(impact.get("direction") or "unknown")
        confirmation = "confirmed" if direction == "positive" else "conflict" if direction == "negative" else "neutral"
        sample = enrich_event_rule_sample(_event_sample_from_context(forecast=forecast, event_impact=impact, confirmation=confirmation))
        score = abs(_to_float(impact.get("score")) or 0.0)
        if score > best_score:
            best_score = score
            best_sample = sample
            best_impact = impact
    if best_sample is None:
        return {
            "ok": True,
            "source": "fallback_default_rules",
            "matched_rules": [],
            "matched_rules_count": 0,
            "event_context": None,
            "warnings": ["event mapping produced no overlay sample"],
        }
    matched = [rule for rule in rules if sample_matches_event_rule(best_sample, rule)]
    context = {
        "event_family": best_sample.get("event_family"),
        "event_direction": best_sample.get("event_direction"),
        "event_confirmation": best_sample.get("event_confirmation"),
        "event_scope": best_sample.get("event_scope"),
        "event_score": best_sample.get("event_score"),
        "event_title": best_sample.get("event_title"),
        "event_id": best_sample.get("event_id"),
        "sample": best_sample,
        "impact": best_impact,
    }
    return {
        "ok": True,
        "source": "fallback_default_rules" if not stability_result else "stability_result",
        "matched_rules": matched,
        "matched_rules_count": len(matched),
        "event_context": context,
        "warnings": [],
    }
