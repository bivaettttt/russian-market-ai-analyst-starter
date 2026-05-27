from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.consumer_signals import _round, _to_float
from app.services.event_aware_setup_research import build_event_aware_samples
from app.services.event_aware_walk_forward import create_walk_forward_folds
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID


TREND_SETUPS = {"trend_following", "momentum_continuation", "breakout", "regime_supported_long"}
REBOUND_SETUPS = {"pullback", "mean_reversion", "oversold_rebound", "volatility_squeeze"}
QUALITY_SETUPS = {"blue_chip_liquidity", "low_volatility_quality"}
EVENT_GROUPS = {
    "macro_rates": {"rates", "inflation", "macro"},
    "risk_fx": {"fx", "sanctions", "geopolitics"},
    "commodity": {"oil_gas", "commodities"},
    "corporate": {"dividend", "earnings", "corporate_action", "ticker_news"},
    "sector": {"sector_news"},
}


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except Exception:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except Exception:
                return None
    return None


def enrich_event_rule_sample(sample: dict[str, Any]) -> dict[str, Any]:
    row = dict(sample)
    setup = str(row.get("setup_family") or "").strip()
    family = str(row.get("event_family") or "").strip()
    direction = str(row.get("event_direction") or "").strip()
    confirmation = str(row.get("event_confirmation") or "").strip()
    scope = str(row.get("event_scope") or "").strip()
    event_score = _to_float(row.get("event_score")) or 0.0
    setup_score = _to_float(row.get("setup_score")) or 0.0

    if setup in TREND_SETUPS:
        setup_group = "trend_like"
    elif setup in REBOUND_SETUPS:
        setup_group = "rebound_like"
    elif setup in QUALITY_SETUPS:
        setup_group = "quality_like"
    else:
        setup_group = "unknown"

    event_group = "unknown"
    for group, families in EVENT_GROUPS.items():
        if family in families:
            event_group = group
            break

    row.update(
        {
            "has_active_setup": bool(setup and setup != "none"),
            "has_event": bool(family and family != "none"),
            "is_confirmed": confirmation == "confirmed",
            "is_conflict": confirmation == "conflict",
            "is_neutral_event": confirmation in {"neutral", "none", ""},
            "is_negative_event": direction == "negative",
            "is_positive_event": direction == "positive",
            "is_mixed_event": direction == "mixed",
            "abs_event_score": abs(event_score),
            "is_high_event_score": abs(event_score) >= 30,
            "is_medium_event_score": abs(event_score) >= 15,
            "is_market_or_sector_scope": scope in {"market", "sector", "asset_class", "global"},
            "setup_group": setup_group,
            "event_group": event_group,
            "conflict_rebound_candidate": confirmation == "conflict"
            and direction in {"negative", "mixed"}
            and setup_group in {"rebound_like", "trend_like"},
            "positive_confirmation_candidate": confirmation == "confirmed" and direction == "positive",
            "avoid_long_candidate": confirmation == "conflict" and direction == "negative" and setup_score < 50,
        }
    )
    return row


def _compare(value: Any, op: str, expected: Any) -> bool:
    if op == "not_exists":
        return value is None or value == ""
    if op == "exists":
        return value is not None and value != ""
    if value is None:
        return False
    if op == "==":
        return value == expected
    if op == "!=":
        return value != expected
    if op == "in":
        expected_values = expected if isinstance(expected, list) else [expected]
        if isinstance(value, list):
            return any(item in expected_values for item in value)
        return value in expected_values
    if op == "not_in":
        expected_values = expected if isinstance(expected, list) else [expected]
        if isinstance(value, list):
            return all(item not in expected_values for item in value)
        return value not in expected_values
    left = _to_float(value)
    right = _to_float(expected)
    if left is None or right is None:
        return False
    if op == ">=":
        return left >= right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == "<":
        return left < right
    return False


def sample_matches_event_rule(sample: dict[str, Any], rule: dict[str, Any]) -> bool:
    enriched = enrich_event_rule_sample(sample)
    conditions = list(rule.get("conditions") or [])
    logic = str(rule.get("logic") or "all")
    results = [
        _compare(enriched.get(condition.get("field")), str(condition.get("op") or "=="), condition.get("value"))
        for condition in conditions
    ]
    if not results:
        return False
    return any(results) if logic == "any" else all(results)


def _condition(field: str, op: str, value: Any = None) -> dict[str, Any]:
    return {"field": field, "op": op, "value": value}


def _rule(rule_id: str, description: str, rule_family: str, conditions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "description": description,
        "rule_family": rule_family,
        "conditions": conditions,
        "logic": "all",
    }


def generate_event_aware_rules(max_rules: int = 120) -> list[dict[str, Any]]:
    rules = [
        _rule("confirmed_positive_any_setup", "Any active setup with confirmed positive event.", "confirmation", [_condition("has_active_setup", "==", True), _condition("is_confirmed", "==", True), _condition("is_positive_event", "==", True)]),
        _rule("confirmed_positive_trend_like", "Trend-like setup with confirmed positive event.", "confirmation", [_condition("setup_group", "==", "trend_like"), _condition("positive_confirmation_candidate", "==", True)]),
        _rule("confirmed_positive_rebound_like", "Rebound-like setup with confirmed positive event.", "confirmation", [_condition("setup_group", "==", "rebound_like"), _condition("positive_confirmation_candidate", "==", True)]),
        _rule("confirmed_positive_high_score", "Confirmed positive event with high absolute score.", "confirmation", [_condition("positive_confirmation_candidate", "==", True), _condition("abs_event_score", ">=", 30)]),
        _rule("confirmed_macro_rates_positive", "Macro/rates positive confirmation.", "confirmation", [_condition("event_group", "==", "macro_rates"), _condition("positive_confirmation_candidate", "==", True)]),
        _rule("confirmed_corporate_positive", "Corporate positive confirmation.", "confirmation", [_condition("event_group", "==", "corporate"), _condition("positive_confirmation_candidate", "==", True)]),
        _rule("confirmed_sector_positive", "Sector positive confirmation.", "confirmation", [_condition("event_group", "==", "sector"), _condition("positive_confirmation_candidate", "==", True)]),
        _rule("conflict_negative_any_setup", "Any active setup with negative event conflict.", "conflict_rebound", [_condition("has_active_setup", "==", True), _condition("is_conflict", "==", True), _condition("is_negative_event", "==", True)]),
        _rule("conflict_negative_rebound_like", "Rebound-like setup into negative event conflict.", "conflict_rebound", [_condition("setup_group", "==", "rebound_like"), _condition("is_conflict", "==", True), _condition("is_negative_event", "==", True)]),
        _rule("conflict_negative_trend_like", "Trend-like setup into negative event conflict.", "conflict_rebound", [_condition("setup_group", "==", "trend_like"), _condition("is_conflict", "==", True), _condition("is_negative_event", "==", True)]),
        _rule("conflict_macro_rates_negative", "Macro/rates negative conflict as rebound candidate.", "conflict_rebound", [_condition("event_group", "==", "macro_rates"), _condition("is_conflict", "==", True), _condition("is_negative_event", "==", True)]),
        _rule("conflict_sector_negative", "Sector negative conflict as rebound candidate.", "conflict_rebound", [_condition("event_group", "==", "sector"), _condition("is_conflict", "==", True), _condition("is_negative_event", "==", True)]),
        _rule("conflict_fx_negative", "FX/risk group negative conflict.", "conflict_rebound", [_condition("event_group", "==", "risk_fx"), _condition("is_conflict", "==", True), _condition("is_negative_event", "==", True)]),
        _rule("conflict_geopolitics_negative", "Geopolitical negative conflict.", "conflict_rebound", [_condition("event_family", "==", "geopolitics"), _condition("is_conflict", "==", True), _condition("is_negative_event", "==", True)]),
        _rule("conflict_high_event_score", "High-score conflict with active setup.", "conflict_rebound", [_condition("has_active_setup", "==", True), _condition("is_conflict", "==", True), _condition("abs_event_score", ">=", 30)]),
        _rule("macro_rates_any_setup", "Any setup with macro/rates event.", "event_group", [_condition("has_active_setup", "==", True), _condition("event_group", "==", "macro_rates")]),
        _rule("risk_fx_any_setup", "Any setup with FX/sanctions/geopolitics event.", "event_group", [_condition("has_active_setup", "==", True), _condition("event_group", "==", "risk_fx")]),
        _rule("commodity_any_setup", "Any setup with commodity event.", "event_group", [_condition("has_active_setup", "==", True), _condition("event_group", "==", "commodity")]),
        _rule("corporate_any_setup", "Any setup with corporate/ticker event.", "event_group", [_condition("has_active_setup", "==", True), _condition("event_group", "==", "corporate")]),
        _rule("sector_any_setup", "Any setup with sector event.", "event_group", [_condition("has_active_setup", "==", True), _condition("event_group", "==", "sector")]),
        _rule("sector_or_rates_conflict", "Sector or rates conflict.", "event_group", [_condition("event_group", "in", ["sector", "macro_rates"]), _condition("is_conflict", "==", True)]),
        _rule("trend_like_positive_event", "Trend-like setup with positive event.", "setup_event_direction", [_condition("setup_group", "==", "trend_like"), _condition("is_positive_event", "==", True)]),
        _rule("trend_like_mixed_event", "Trend-like setup with mixed event.", "setup_event_direction", [_condition("setup_group", "==", "trend_like"), _condition("is_mixed_event", "==", True)]),
        _rule("trend_like_conflict", "Trend-like setup with conflict.", "setup_event_direction", [_condition("setup_group", "==", "trend_like"), _condition("is_conflict", "==", True)]),
        _rule("rebound_like_negative_event", "Rebound-like setup with negative event.", "setup_event_direction", [_condition("setup_group", "==", "rebound_like"), _condition("is_negative_event", "==", True)]),
        _rule("rebound_like_conflict", "Rebound-like setup with conflict.", "setup_event_direction", [_condition("setup_group", "==", "rebound_like"), _condition("is_conflict", "==", True)]),
        _rule("quality_like_negative_event", "Quality-like setup with negative event.", "setup_event_direction", [_condition("setup_group", "==", "quality_like"), _condition("is_negative_event", "==", True)]),
        _rule("quality_like_confirmed", "Quality-like setup with confirmed event.", "setup_event_direction", [_condition("setup_group", "==", "quality_like"), _condition("is_confirmed", "==", True)]),
        _rule("event_score_abs_ge_15_any_setup", "Any setup with event score abs >= 15.", "score_threshold", [_condition("has_active_setup", "==", True), _condition("abs_event_score", ">=", 15)]),
        _rule("event_score_abs_ge_30_any_setup", "Any setup with event score abs >= 30.", "score_threshold", [_condition("has_active_setup", "==", True), _condition("abs_event_score", ">=", 30)]),
        _rule("positive_event_score_ge_20", "Positive event score >= 20 with setup.", "score_threshold", [_condition("has_active_setup", "==", True), _condition("event_score", ">=", 20)]),
        _rule("negative_event_score_le_minus_20_conflict", "Negative event score <= -20 with conflict.", "score_threshold", [_condition("is_conflict", "==", True), _condition("event_score", "<=", -20)]),
        _rule("setup_score_ge_60_with_event", "Setup score >= 60 with any event.", "score_threshold", [_condition("setup_score", ">=", 60), _condition("has_event", "==", True)]),
        _rule("setup_score_ge_70_with_confirmed", "Setup score >= 70 with confirmed event.", "score_threshold", [_condition("setup_score", ">=", 70), _condition("is_confirmed", "==", True)]),
        _rule("any_setup_with_any_event", "Any active setup with any event.", "broad_coverage", [_condition("has_active_setup", "==", True), _condition("has_event", "==", True)]),
        _rule("any_setup_exclude_negative_conflict", "Any setup except negative conflict.", "broad_coverage", [_condition("has_active_setup", "==", True), _condition("avoid_long_candidate", "==", False), _condition("has_event", "==", True)]),
        _rule("any_setup_event_not_negative", "Any setup with event direction not negative.", "broad_coverage", [_condition("has_active_setup", "==", True), _condition("event_direction", "!=", "negative"), _condition("has_event", "==", True)]),
        _rule("event_only_positive", "Positive event-only candidate.", "broad_coverage", [_condition("sample_type", "==", "event_only"), _condition("is_positive_event", "==", True)]),
        _rule("event_only_macro_positive", "Positive macro/rates event-only candidate.", "broad_coverage", [_condition("sample_type", "==", "event_only"), _condition("event_group", "==", "macro_rates"), _condition("is_positive_event", "==", True)]),
        _rule("setup_or_event_positive", "Active setup with positive event direction.", "broad_coverage", [_condition("has_active_setup", "==", True), _condition("is_positive_event", "==", True)]),
        _rule("confirmed_or_neutral_only", "Confirmed or neutral event, excluding conflicts.", "filter_style", [_condition("has_active_setup", "==", True), _condition("event_confirmation", "in", ["confirmed", "neutral"])]),
        _rule("exclude_geopolitical_negative", "Any setup excluding negative geopolitics.", "filter_style", [_condition("has_active_setup", "==", True), _condition("event_family", "!=", "geopolitics"), _condition("has_event", "==", True)]),
        _rule("exclude_sanctions_negative", "Any setup excluding negative sanctions.", "filter_style", [_condition("has_active_setup", "==", True), _condition("event_family", "!=", "sanctions"), _condition("has_event", "==", True)]),
        _rule("exclude_low_score_events", "Any setup with medium/high event score only.", "filter_style", [_condition("has_active_setup", "==", True), _condition("is_medium_event_score", "==", True)]),
    ]
    return rules[: max(0, max_rules)]


def _sample_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("date"),
        row.get("setup_family"),
        row.get("event_id"),
        row.get("sample_type"),
    )


def concentration_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {"top_ticker_share_pct": 0.0, "top_event_share_pct": 0.0, "top_year_share_pct": 0.0, "warnings": ["no selected samples"]}
    tickers = Counter(str(row.get("ticker") or "unknown") for row in rows)
    events = Counter(str(row.get("event_id") or row.get("event_title") or "none") for row in rows)
    years = Counter(str((_as_date(row.get("date")) or date.min).year) for row in rows)
    top_ticker = tickers.most_common(1)[0]
    top_event = events.most_common(1)[0]
    top_year = years.most_common(1)[0]
    result = {
        "top_ticker": top_ticker[0],
        "top_ticker_share_pct": _round(top_ticker[1] / total * 100, 2) or 0.0,
        "top_event": top_event[0],
        "top_event_share_pct": _round(top_event[1] / total * 100, 2) or 0.0,
        "top_year": top_year[0],
        "top_year_share_pct": _round(top_year[1] / total * 100, 2) or 0.0,
        "warnings": [],
    }
    if result["top_ticker_share_pct"] > 50:
        result["warnings"].append("top ticker concentration above 50%")
    if result["top_event_share_pct"] > 50:
        result["warnings"].append("top event concentration above 50%")
    if result["top_year_share_pct"] > 70:
        result["warnings"].append("top year concentration above 70%")
    return result


def _metrics(rows: list[dict[str, Any]], *, total_rows: int, min_signals: int, rule: dict[str, Any] | None = None) -> dict[str, Any]:
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )
    event_scores = [_to_float(row.get("event_score")) for row in rows if _to_float(row.get("event_score")) is not None]
    setup_scores = [_to_float(row.get("setup_score")) for row in rows if _to_float(row.get("setup_score")) is not None]
    concentration = concentration_diagnostics(rows)
    samples = len(rows)
    avg = _to_float(pnl.get("avg_trade_return_pct"))
    pf = _to_float(pnl.get("profit_factor"))
    if samples < min_signals or concentration.get("warnings"):
        quality = "unstable"
    elif pf is not None and avg is not None and pf >= 1.10 and avg > 0:
        quality = "good"
    elif pf is not None and avg is not None and pf >= 1.02 and avg >= 0:
        quality = "medium"
    elif (pf is not None and pf < 0.95) or (avg is not None and avg < 0):
        quality = "bad"
    else:
        quality = "weak"
    warnings = list(concentration.get("warnings") or [])
    if samples < min_signals:
        warnings.append("samples below min_signals")
    result = {
        "samples": samples,
        "tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "events": len({row.get("event_id") for row in rows if row.get("event_id")}),
        "avg_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "median_trade_return_pct": pnl.get("median_trade_return_pct"),
        "profit_factor": pnl.get("profit_factor"),
        "win_rate_pct": pnl.get("win_rate_pct"),
        "target_hit_rate_pct": pnl.get("target_hit_rate_pct"),
        "stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
        "timeout_rate_pct": pnl.get("timeout_rate_pct"),
        "avg_event_score": _round(mean(event_scores), 2) if event_scores else None,
        "avg_setup_score": _round(mean(setup_scores), 2) if setup_scores else None,
        "coverage_pct": _round(samples / total_rows * 100, 2) if total_rows else 0.0,
        "concentration": concentration,
        "quality_label": quality,
        "warnings": warnings,
    }
    score = (
        (_to_float(result.get("avg_trade_return_pct")) or 0.0) * 25
        + max(0.0, (_to_float(result.get("profit_factor")) or 0.0) - 1.0) * 35
        + (_to_float(result.get("win_rate_pct")) or 0.0) * 0.2
        - (_to_float(result.get("stop_hit_rate_pct")) or 0.0) * 0.2
        + min(samples, 100) * 0.05
    )
    if concentration.get("top_ticker_share_pct", 0) > 50:
        score -= 15
    if concentration.get("top_event_share_pct", 0) > 50:
        score -= 15
    if concentration.get("top_year_share_pct", 0) > 70:
        score -= 15
    if samples < min_signals:
        score -= 40
    result["score"] = _round(max(-100.0, min(100.0, score)), 2) or 0.0
    if rule:
        result.update(
            {
                "rule_id": rule.get("rule_id"),
                "rule_family": rule.get("rule_family"),
                "description": rule.get("description"),
            }
        )
    return result


def _delta(selected: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "avg_trade_return_delta_pct": _round((_to_float(selected.get("avg_trade_return_pct")) or 0.0) - (_to_float(baseline.get("avg_trade_return_pct")) or 0.0), 2),
        "profit_factor_delta": _round((_to_float(selected.get("profit_factor")) or 0.0) - (_to_float(baseline.get("profit_factor")) or 0.0), 3),
        "win_rate_delta_pct": _round((_to_float(selected.get("win_rate_pct")) or 0.0) - (_to_float(baseline.get("win_rate_pct")) or 0.0), 2),
        "stop_hit_delta_pct": _round((_to_float(selected.get("stop_hit_rate_pct")) or 0.0) - (_to_float(baseline.get("stop_hit_rate_pct")) or 0.0), 2),
    }


def _period(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [_as_date(row.get("date")) for row in rows if _as_date(row.get("date")) is not None]
    return {
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "samples": len(rows),
    }


def _rows_between_dates(rows: list[dict[str, Any]], start: date | None, end: date | None) -> list[dict[str, Any]]:
    if start is None or end is None:
        return []
    result: list[dict[str, Any]] = []
    for row in rows:
        row_date = _as_date(row.get("date"))
        if row_date is not None and start <= row_date <= end:
            result.append(row)
    return result


def _evaluate_rules(rows: list[dict[str, Any]], rules: list[dict[str, Any]], *, min_signals: int) -> list[dict[str, Any]]:
    total = len(rows)
    results: list[dict[str, Any]] = []
    for rule in rules:
        matched = [row for row in rows if sample_matches_event_rule(row, rule)]
        results.append(_metrics(matched, total_rows=total, min_signals=min_signals, rule=rule))
    results.sort(
        key=lambda row: (
            0 if row.get("quality_label") in {"unstable", "bad"} else 1,
            _to_float(row.get("score")) or -999,
            int(row.get("samples") or 0),
        ),
        reverse=True,
    )
    return results


def _selected_rows_for_rules(rows: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for rule in rules:
        for row in rows:
            if sample_matches_event_rule(row, rule):
                selected[_sample_key(row)] = row
    return list(selected.values())


def rule_search_recommendation(summary: dict[str, Any], *, concentration_warning: bool) -> str:
    if int(summary.get("event_samples") or 0) < 100 or int(summary.get("folds_completed") or 0) < 2:
        return "needs_more_data"
    completed = int(summary.get("folds_completed") or 0)
    positive = int(summary.get("positive_folds") or 0)
    pf = _to_float(summary.get("avg_test_selected_profit_factor")) or 0.0
    avg = _to_float(summary.get("avg_test_selected_return_pct")) or 0.0
    avg_samples = _to_float(summary.get("avg_selected_samples_per_fold")) or 0.0
    min_signals = int(summary.get("min_signals") or 0)
    if completed >= 3 and positive >= min(3, completed) and pf >= 1.10 and avg > 0 and avg_samples >= min_signals and not concentration_warning:
        return "promising_generalized_event_rule"
    if pf >= 1.02 and avg >= 0 and positive > 0:
        return "research_only"
    return "reject"


def build_event_aware_rule_search(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    max_events: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    event_lookback_days: int = 7,
    event_decay_days: int = 14,
    folds: int = 4,
    train_ratio: float = 0.6,
    min_train_samples: int = 100,
    min_test_samples: int = 50,
    min_signals: int = 20,
    max_rules: int = 120,
    top_k_rules: int = 5,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    include_global_events: bool = True,
    include_ticker_events: bool = True,
) -> dict[str, Any]:
    sample_data = build_event_aware_samples(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )
    rows = [enrich_event_rule_sample(row) for row in list(sample_data.get("samples") or [])]
    event_rows = [row for row in rows if row.get("has_event")]
    confirmed_rows = [row for row in event_rows if row.get("is_confirmed")]
    rules = generate_event_aware_rules(max_rules=max_rules)
    warnings = list(sample_data.get("warnings") or [])
    static_results = _evaluate_rules(rows, rules, min_signals=min_signals)
    fold_specs = create_walk_forward_folds(
        event_rows,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    fold_results: list[dict[str, Any]] = []
    rule_frequency: dict[str, dict[str, Any]] = {}
    for spec in fold_specs:
        train_rows = spec["train_rows"]
        test_rows = spec["test_rows"]
        train_rank = _evaluate_rules(train_rows, rules, min_signals=min_signals)
        selected_rules = [row for row in train_rank if row.get("quality_label") not in {"unstable", "bad"} and int(row.get("samples") or 0) >= min_signals]
        if not selected_rules:
            selected_rules = [row for row in train_rank if int(row.get("samples") or 0) >= min_signals]
        selected_rules = selected_rules[:top_k_rules]
        rule_lookup = {rule["rule_id"]: rule for rule in rules}
        selected_rule_defs = [rule_lookup[row["rule_id"]] for row in selected_rules if row.get("rule_id") in rule_lookup]
        test_selected = _selected_rows_for_rules(test_rows, selected_rule_defs)
        selected_metrics = _metrics(test_selected, total_rows=len(test_rows), min_signals=min_signals)
        event_baseline = _metrics(test_rows, total_rows=len(test_rows), min_signals=min_signals)
        confirmed_baseline = _metrics([row for row in test_rows if row.get("is_confirmed")], total_rows=len(test_rows), min_signals=min_signals)
        test_dates = [_as_date(row.get("date")) for row in test_rows if _as_date(row.get("date")) is not None]
        setup_only_rows = [
            row
            for row in _rows_between_dates(rows, min(test_dates) if test_dates else None, max(test_dates) if test_dates else None)
            if row.get("sample_type") == "setup_only"
        ]
        setup_only_baseline = _metrics(setup_only_rows, total_rows=max(1, len(setup_only_rows)), min_signals=min_signals)
        concentration = concentration_diagnostics(test_selected)
        fold_warnings = list(concentration.get("warnings") or [])
        if not selected_rules:
            fold_warnings.append("No train rules passed min_signals.")
        if not test_selected:
            fold_warnings.append("No selected rule samples in test fold.")
        for rule_row in selected_rules:
            rid = str(rule_row.get("rule_id"))
            bucket = rule_frequency.setdefault(rid, {"rule_id": rid, "rule_family": rule_row.get("rule_family"), "selected_folds": 0, "train_scores": [], "test_returns": [], "test_pfs": []})
            rule_def = rule_lookup.get(rid)
            combo_test = [row for row in test_rows if rule_def and sample_matches_event_rule(row, rule_def)]
            combo_metrics = _metrics(combo_test, total_rows=len(test_rows), min_signals=min_signals)
            bucket["selected_folds"] += 1
            bucket["train_scores"].append(_to_float(rule_row.get("score")) or 0.0)
            if combo_metrics.get("avg_trade_return_pct") is not None:
                bucket["test_returns"].append(_to_float(combo_metrics.get("avg_trade_return_pct")) or 0.0)
            if combo_metrics.get("profit_factor") is not None:
                bucket["test_pfs"].append(_to_float(combo_metrics.get("profit_factor")) or 0.0)
        fold_results.append(
            {
                "fold": spec["fold"],
                "train_period": _period(train_rows),
                "test_period": _period(test_rows),
                "selected_rules": selected_rules,
                "test_selected_metrics": selected_metrics,
                "test_event_baseline_metrics": event_baseline,
                "test_confirmed_baseline_metrics": confirmed_baseline,
                "test_setup_only_metrics": setup_only_baseline,
                "delta_vs_event_baseline": _delta(selected_metrics, event_baseline),
                "concentration": concentration,
                "quality_label": selected_metrics.get("quality_label"),
                "warnings": fold_warnings,
            }
        )

    completed = len(fold_results)
    selected_returns = [_to_float((fold.get("test_selected_metrics") or {}).get("avg_trade_return_pct")) for fold in fold_results]
    selected_pfs = [_to_float((fold.get("test_selected_metrics") or {}).get("profit_factor")) for fold in fold_results]
    selected_samples = [int((fold.get("test_selected_metrics") or {}).get("samples") or 0) for fold in fold_results]
    deltas_return = [_to_float((fold.get("delta_vs_event_baseline") or {}).get("avg_trade_return_delta_pct")) for fold in fold_results]
    deltas_pf = [_to_float((fold.get("delta_vs_event_baseline") or {}).get("profit_factor_delta")) for fold in fold_results]
    positive_folds = sum(1 for value in selected_returns if (value or 0.0) > 0)
    negative_folds = completed - positive_folds
    freq = [
        {
            "rule_id": rid,
            "rule_family": item.get("rule_family"),
            "selected_folds": item["selected_folds"],
            "avg_train_score": _round(mean(item["train_scores"]), 2) if item["train_scores"] else None,
            "avg_test_return_pct": _round(mean(item["test_returns"]), 2) if item["test_returns"] else None,
            "avg_test_profit_factor": _round(mean(item["test_pfs"]), 3) if item["test_pfs"] else None,
        }
        for rid, item in rule_frequency.items()
    ]
    freq.sort(key=lambda row: (int(row.get("selected_folds") or 0), _to_float(row.get("avg_train_score")) or -999), reverse=True)
    concentration_warning = any((fold.get("concentration") or {}).get("warnings") for fold in fold_results)
    best_rule = static_results[0] if static_results else {}
    summary = {
        "samples": len(rows),
        "event_samples": len(event_rows),
        "confirmed_samples": len(confirmed_rows),
        "rules_tested": len(rules),
        "folds_requested": folds,
        "folds_completed": completed,
        "min_signals": min_signals,
        "avg_selected_samples_per_fold": _round(mean(selected_samples), 2) if selected_samples else 0.0,
        "selected_samples_by_fold": [{"fold": fold.get("fold"), "selected_samples": (fold.get("test_selected_metrics") or {}).get("samples")} for fold in fold_results],
        "avg_test_selected_return_pct": _round(mean([x for x in selected_returns if x is not None]), 2) if any(x is not None for x in selected_returns) else None,
        "avg_test_selected_profit_factor": _round(mean([x for x in selected_pfs if x is not None]), 3) if any(x is not None for x in selected_pfs) else None,
        "positive_folds": positive_folds,
        "negative_folds": negative_folds,
        "avg_delta_vs_event_baseline_return_pct": _round(mean([x for x in deltas_return if x is not None]), 2) if any(x is not None for x in deltas_return) else None,
        "avg_delta_vs_event_baseline_profit_factor": _round(mean([x for x in deltas_pf if x is not None]), 3) if any(x is not None for x in deltas_pf) else None,
        "best_rule_id": best_rule.get("rule_id"),
        "best_rule_family": best_rule.get("rule_family"),
        "warnings": warnings,
    }
    summary["recommendation"] = rule_search_recommendation(summary, concentration_warning=concentration_warning)
    if not fold_results:
        warnings.append("not enough event samples to build requested rule-search folds")
    return {
        "ok": True,
        "mode": "event_aware_rule_search",
        "summary": summary,
        "static_best_rules": static_results[:20],
        "folds": fold_results,
        "rule_frequency": freq,
        "limitations": [
            "Rules are selected on train folds only and evaluated on future test folds.",
            "Rule search can still overfit the curated historical event seed.",
            "Proxy backtest uses daily candles with simplified costs and target/stop ordering.",
            "Research-only layer; production consumer logic is unchanged.",
        ],
    }
