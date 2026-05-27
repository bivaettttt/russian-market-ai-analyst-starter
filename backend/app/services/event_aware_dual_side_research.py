from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.consumer_signals import _round, _to_float
from app.services.event_aware_rule_search import (
    concentration_diagnostics,
    enrich_event_rule_sample,
    generate_event_aware_rules,
    sample_matches_event_rule,
)
from app.services.event_aware_setup_research import build_event_aware_samples
from app.services.event_aware_walk_forward import create_walk_forward_folds
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID


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


def _rate(part: int, total: int) -> float | None:
    return _round(part / total * 100, 2) if total else None


def enrich_downside_outcomes(
    sample: dict[str, Any],
    *,
    horizon: int = 30,
    downside_threshold_pct: float = -2.0,
    severe_downside_threshold_pct: float = -5.0,
) -> dict[str, Any]:
    row = enrich_event_rule_sample(sample)
    long_return = _to_float(row.get("trade_return_pct"))
    long_outcome = row.get("outcome")
    future_return = _to_float(row.get("future_return_pct"))
    if future_return is None:
        future_return = long_return
    future_min = _to_float(row.get("future_min_return_pct"))
    if future_min is None:
        future_min = _to_float(row.get("mae_pct"))
    future_max = _to_float(row.get("future_max_return_pct"))
    if future_max is None:
        future_max = _to_float(row.get("mfe_pct"))
    long_stop = long_outcome == "stop_hit"
    long_target = long_outcome == "target_hit"
    negative = (future_return is not None and future_return < 0) or (long_return is not None and long_return < 0)
    downside = long_stop or (future_min is not None and future_min <= downside_threshold_pct)
    severe = future_min is not None and future_min <= severe_downside_threshold_pct
    avoid_benefit = max(0.0, -(long_return or 0.0))
    missed_upside = max(0.0, long_return or 0.0)
    downside_magnitude = abs(min(0.0, future_min or 0.0))
    row.update(
        {
            "horizon": horizon,
            "long_trade_return_pct": long_return,
            "long_outcome": long_outcome,
            "long_stop_hit_flag": long_stop,
            "long_target_hit_flag": long_target,
            "future_return_pct": future_return,
            "future_min_return_pct": future_min,
            "future_max_return_pct": future_max,
            "negative_return_flag": negative,
            "downside_flag": downside,
            "severe_downside_flag": severe,
            "avoid_long_benefit_pct": _round(avoid_benefit, 2) or 0.0,
            "missed_upside_pct": _round(missed_upside, 2) or 0.0,
            "downside_magnitude_pct": _round(downside_magnitude, 2) or 0.0,
            "risk_adjusted_avoid_score": _round(avoid_benefit - missed_upside * 0.75, 2) or 0.0,
            "future_metrics_available": future_min is not None or future_max is not None,
        }
    )
    return row


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return _round(numerator / denominator, 3)


def _baseline_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("long_outcome"), "trade_return_pct": row.get("long_trade_return_pct")} for row in rows]
    )
    return {
        "samples": len(rows),
        "avg_long_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "long_profit_factor": pnl.get("profit_factor"),
        "long_win_rate_pct": pnl.get("win_rate_pct"),
        "long_stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
        "long_target_hit_rate_pct": pnl.get("target_hit_rate_pct"),
        "negative_return_rate_pct": _rate(sum(1 for row in rows if row.get("negative_return_flag")), len(rows)),
        "downside_flag_rate_pct": _rate(sum(1 for row in rows if row.get("downside_flag")), len(rows)),
        "severe_downside_rate_pct": _rate(sum(1 for row in rows if row.get("severe_downside_flag")), len(rows)),
    }


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return _round(mean(clean), 2) if clean else None


def _rule_score(row: dict[str, Any], baseline: dict[str, Any], *, min_signals: int) -> float:
    score = 0.0
    avg_long = _to_float(row.get("avg_long_trade_return_pct")) or 0.0
    stop = _to_float(row.get("long_stop_hit_rate_pct")) or 0.0
    base_stop = _to_float(baseline.get("long_stop_hit_rate_pct")) or 0.0
    neg = _to_float(row.get("negative_return_rate_pct")) or 0.0
    base_neg = _to_float(baseline.get("negative_return_rate_pct")) or 0.0
    avoid = _to_float(row.get("avg_avoid_long_benefit_pct")) or 0.0
    missed = _to_float(row.get("avg_missed_upside_pct")) or 0.0
    adjusted = _to_float(row.get("risk_adjusted_avoid_score")) or 0.0
    downside_lift = _to_float(row.get("downside_lift_vs_baseline")) or 0.0
    score += max(0.0, -avg_long) * 25
    score += max(0.0, stop - base_stop) * 0.8
    score += max(0.0, neg - base_neg) * 0.6
    score += avoid * 20
    score -= missed * 15
    score += adjusted * 10
    score += downside_lift * 0.5
    if int(row.get("samples") or 0) < min_signals:
        score -= 40
    concentration = row.get("concentration") or {}
    if concentration.get("top_ticker_share_pct", 0) > 50:
        score -= 15
    if concentration.get("top_event_share_pct", 0) > 50:
        score -= 15
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _recommended_use(row: dict[str, Any], baseline: dict[str, Any], *, min_signals: int) -> tuple[str, str]:
    samples = int(row.get("samples") or 0)
    concentration = row.get("concentration") or {}
    if samples < min_signals or concentration.get("warnings"):
        return "reject", "unstable"
    avg_long = _to_float(row.get("avg_long_trade_return_pct"))
    pf = _to_float(row.get("long_profit_factor"))
    stop = _to_float(row.get("long_stop_hit_rate_pct")) or 0.0
    base_stop = _to_float(baseline.get("long_stop_hit_rate_pct")) or 0.0
    avoid = _to_float(row.get("avg_avoid_long_benefit_pct")) or 0.0
    missed = _to_float(row.get("avg_missed_upside_pct")) or 0.0
    score = _to_float(row.get("score")) or 0.0
    if avg_long is not None and avg_long < 0 and stop > base_stop and avoid > missed and score >= 25:
        return "avoid_long", "good"
    if avg_long is not None and avg_long <= 0 and score >= 10:
        return "avoid_long" if avoid > missed else "downside_watch", "medium"
    if (row.get("downside_lift_vs_baseline") or 0) > 5 and avoid >= missed * 0.7:
        return "downside_watch", "weak"
    if avg_long is not None and pf is not None and avg_long > 0 and pf > 1.05 and stop <= base_stop:
        return "long_candidate", "medium"
    if missed > avoid:
        return "reject", "bad"
    return "neutral", "weak"


def _dual_metrics(
    rows: list[dict[str, Any]],
    *,
    baseline: dict[str, Any],
    min_signals: int,
    rule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("long_outcome"), "trade_return_pct": row.get("long_trade_return_pct")} for row in rows]
    )
    samples = len(rows)
    avoid_values = [_to_float(row.get("avoid_long_benefit_pct")) for row in rows]
    missed_values = [_to_float(row.get("missed_upside_pct")) for row in rows]
    downside_values = [_to_float(row.get("downside_magnitude_pct")) for row in rows]
    result = {
        "samples": samples,
        "tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "events": len({row.get("event_id") for row in rows if row.get("event_id")}),
        "avg_long_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "long_profit_factor": pnl.get("profit_factor"),
        "long_win_rate_pct": pnl.get("win_rate_pct"),
        "long_stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
        "long_target_hit_rate_pct": pnl.get("target_hit_rate_pct"),
        "negative_return_rate_pct": _rate(sum(1 for row in rows if row.get("negative_return_flag")), samples),
        "downside_flag_rate_pct": _rate(sum(1 for row in rows if row.get("downside_flag")), samples),
        "severe_downside_rate_pct": _rate(sum(1 for row in rows if row.get("severe_downside_flag")), samples),
        "avg_future_return_pct": _avg([_to_float(row.get("future_return_pct")) for row in rows]),
        "avg_future_min_return_pct": _avg([_to_float(row.get("future_min_return_pct")) for row in rows]),
        "avg_downside_magnitude_pct": _avg(downside_values),
        "avg_avoid_long_benefit_pct": _avg(avoid_values),
        "avg_missed_upside_pct": _avg(missed_values),
        "risk_adjusted_avoid_score": _avg([_to_float(row.get("risk_adjusted_avoid_score")) for row in rows]),
        "concentration": concentration_diagnostics(rows),
        "warnings": [],
    }
    result["avoid_benefit_to_missed_upside_ratio"] = _ratio(
        _to_float(result.get("avg_avoid_long_benefit_pct")),
        _to_float(result.get("avg_missed_upside_pct")),
    )
    result["stop_hit_lift_vs_baseline"] = _round(
        (_to_float(result.get("long_stop_hit_rate_pct")) or 0.0)
        - (_to_float(baseline.get("long_stop_hit_rate_pct")) or 0.0),
        2,
    )
    result["downside_lift_vs_baseline"] = _round(
        (_to_float(result.get("downside_flag_rate_pct")) or 0.0)
        - (_to_float(baseline.get("downside_flag_rate_pct")) or 0.0),
        2,
    )
    if samples < min_signals:
        result["warnings"].append("samples below min_signals")
    result["warnings"].extend((result.get("concentration") or {}).get("warnings") or [])
    result["score"] = _rule_score(result, baseline, min_signals=min_signals)
    recommended, quality = _recommended_use(result, baseline, min_signals=min_signals)
    result["recommended_use"] = recommended
    result["quality_label"] = quality
    if rule:
        result.update(
            {
                "rule_id": rule.get("rule_id"),
                "rule_family": rule.get("rule_family"),
                "description": rule.get("description"),
            }
        )
    return result


def _build_dual_samples(
    db: Session,
    *,
    max_tickers: int,
    max_samples: int,
    max_events: int,
    min_history: int,
    horizon: int,
    policy_id: str,
    event_lookback_days: int,
    event_decay_days: int,
    commission_bps: float,
    slippage_bps: float,
    include_global_events: bool,
    include_ticker_events: bool,
) -> dict[str, Any]:
    data = build_event_aware_samples(
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
    rows = [enrich_downside_outcomes(row, horizon=horizon) for row in list(data.get("samples") or [])]
    return {"rows": rows, "summary": data.get("summary") or {}, "warnings": list(data.get("warnings") or [])}


def _evaluate_rules(rows: list[dict[str, Any]], rules: list[dict[str, Any]], *, baseline: dict[str, Any], min_signals: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for rule in rules:
        matched = [row for row in rows if sample_matches_event_rule(row, rule)]
        results.append(_dual_metrics(matched, baseline=baseline, min_signals=min_signals, rule=rule))
    results.sort(key=lambda row: (_to_float(row.get("score")) or -999, int(row.get("samples") or 0)), reverse=True)
    return results


def build_event_aware_dual_side_research(
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
    min_signals: int = 20,
    max_rules: int = 120,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    include_global_events: bool = True,
    include_ticker_events: bool = True,
) -> dict[str, Any]:
    sample_data = _build_dual_samples(
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
    rows = sample_data["rows"]
    event_rows = [row for row in rows if row.get("has_event")]
    rules = generate_event_aware_rules(max_rules=max_rules)
    baseline = _baseline_metrics(event_rows)
    results = _evaluate_rules(event_rows, rules, baseline=baseline, min_signals=min_signals)
    avoid_rules = [row for row in results if row.get("recommended_use") == "avoid_long"]
    downside_rules = [row for row in results if row.get("recommended_use") == "downside_watch"]
    long_rules = [row for row in results if row.get("recommended_use") == "long_candidate"]
    good_or_medium = [row for row in avoid_rules if row.get("quality_label") in {"good", "medium"}]
    if len(event_rows) < min_signals:
        recommendation = "needs_more_data"
    elif good_or_medium:
        recommendation = "promising_risk_filter"
    elif avoid_rules or downside_rules:
        recommendation = "research_only"
    else:
        recommendation = "no_downside_edge"
    sorted_losses = sorted(event_rows, key=lambda row: _to_float(row.get("long_trade_return_pct")) or 0.0)
    sorted_winners = sorted(event_rows, key=lambda row: _to_float(row.get("long_trade_return_pct")) or 0.0, reverse=True)
    summary = {
        "samples": len(rows),
        "event_samples": len(event_rows),
        "rules_tested": len(rules),
        "baseline": baseline,
        "best_avoid_rule_id": (avoid_rules[0] or {}).get("rule_id") if avoid_rules else None,
        "best_downside_rule_id": (downside_rules[0] or {}).get("rule_id") if downside_rules else None,
        "best_long_rule_id": (long_rules[0] or {}).get("rule_id") if long_rules else None,
        "avoid_rules_good_or_medium": len(good_or_medium),
        "recommendation": recommendation,
        "warnings": sample_data["warnings"],
    }
    return {
        "ok": True,
        "mode": "event_aware_dual_side_research",
        "summary": summary,
        "best_avoid_long_rules": avoid_rules[:20],
        "best_downside_watch_rules": downside_rules[:20],
        "best_long_candidate_rules": long_rules[:20],
        "all_results": results,
        "examples": {
            "avoided_loss_examples": sorted_losses[:10],
            "missed_upside_examples": sorted_winners[:10],
            "downside_examples": [row for row in sorted_losses if row.get("downside_flag")][:10],
        },
        "limitations": [
            "Research-only downside/risk layer; production consumer logic is unchanged.",
            "No production short or short recommendation is generated.",
            "Future downside labels use proxy trade outcomes and available MAE/MFE fields.",
            "Curated event seed can bias event-aware conclusions.",
            "Daily candle ordering and simplified costs remain limitations.",
        ],
    }


def _period(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [_as_date(row.get("date")) for row in rows if _as_date(row.get("date")) is not None]
    return {
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "samples": len(rows),
    }


def _selected_rows(rows: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for rule in rules:
        for row in rows:
            if sample_matches_event_rule(row, rule):
                key = (row.get("ticker"), row.get("date"), row.get("setup_family"), row.get("event_id"), row.get("sample_type"))
                selected[key] = row
    return list(selected.values())


def _filter_impact(baseline: dict[str, Any], kept: dict[str, Any], blocked_rows: list[dict[str, Any]], total_rows: int) -> dict[str, Any]:
    avoided_losses = [row for row in blocked_rows if (_to_float(row.get("long_trade_return_pct")) or 0.0) < 0]
    missed_winners = [row for row in blocked_rows if (_to_float(row.get("long_trade_return_pct")) or 0.0) > 0]
    return {
        "active_trades_before": total_rows,
        "active_trades_after": int(kept.get("samples") or 0),
        "blocked_trades": len(blocked_rows),
        "coverage_after_filter_pct": _round((int(kept.get("samples") or 0) / total_rows * 100), 2) if total_rows else 0.0,
        "avg_return_delta_pct": _round((_to_float(kept.get("avg_long_trade_return_pct")) or 0.0) - (_to_float(baseline.get("avg_long_trade_return_pct")) or 0.0), 2),
        "profit_factor_delta": _round((_to_float(kept.get("long_profit_factor")) or 0.0) - (_to_float(baseline.get("long_profit_factor")) or 0.0), 3),
        "stop_hit_delta_pct": _round((_to_float(kept.get("long_stop_hit_rate_pct")) or 0.0) - (_to_float(baseline.get("long_stop_hit_rate_pct")) or 0.0), 2),
        "avoided_losses": len(avoided_losses),
        "missed_winners": len(missed_winners),
        "avoided_loss_return_pct": _round(sum(abs(_to_float(row.get("long_trade_return_pct")) or 0.0) for row in avoided_losses), 2),
        "missed_upside_pct": _round(sum(_to_float(row.get("long_trade_return_pct")) or 0.0 for row in missed_winners), 2),
    }


def dual_side_walk_forward_recommendation(summary: dict[str, Any]) -> str:
    if int(summary.get("folds_completed") or 0) < 2:
        return "needs_more_data"
    positive = int(summary.get("positive_impact_folds") or 0)
    completed = int(summary.get("folds_completed") or 0)
    return_delta = _to_float(summary.get("avg_return_delta_pct")) or 0.0
    pf_delta = _to_float(summary.get("avg_profit_factor_delta")) or 0.0
    stop_delta = _to_float(summary.get("avg_stop_hit_delta_pct")) or 0.0
    coverage = _to_float(summary.get("avg_coverage_after_filter_pct")) or 0.0
    if positive >= min(3, completed) and return_delta > 0 and pf_delta > 0 and stop_delta < 0 and coverage > 50:
        return "promising_risk_filter"
    if (return_delta > 0 or pf_delta > 0 or stop_delta < 0) and positive > 0:
        return "research_only"
    return "reject"


def build_event_aware_dual_side_walk_forward(
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
    sample_data = _build_dual_samples(
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
    rows = sample_data["rows"]
    event_rows = [row for row in rows if row.get("has_event")]
    rules = generate_event_aware_rules(max_rules=max_rules)
    fold_specs = create_walk_forward_folds(
        event_rows,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    fold_results: list[dict[str, Any]] = []
    frequency: dict[str, dict[str, Any]] = {}
    for spec in fold_specs:
        train_rows = spec["train_rows"]
        test_rows = spec["test_rows"]
        train_baseline = _baseline_metrics(train_rows)
        train_rank = _evaluate_rules(train_rows, rules, baseline=train_baseline, min_signals=min_signals)
        selected = [row for row in train_rank if row.get("recommended_use") in {"avoid_long", "downside_watch"} and row.get("quality_label") in {"good", "medium", "weak"}][:top_k_rules]
        lookup = {rule["rule_id"]: rule for rule in rules}
        selected_defs = [lookup[row["rule_id"]] for row in selected if row.get("rule_id") in lookup]
        blocked = _selected_rows(test_rows, selected_defs)
        blocked_keys = {(row.get("ticker"), row.get("date"), row.get("setup_family"), row.get("event_id"), row.get("sample_type")) for row in blocked}
        kept = [
            row
            for row in test_rows
            if (row.get("ticker"), row.get("date"), row.get("setup_family"), row.get("event_id"), row.get("sample_type")) not in blocked_keys
        ]
        baseline_metrics = _baseline_metrics(test_rows)
        kept_metrics = _baseline_metrics(kept)
        blocked_metrics = _dual_metrics(blocked, baseline=baseline_metrics, min_signals=min_signals)
        impact = _filter_impact(baseline_metrics, kept_metrics, blocked, len(test_rows))
        warnings: list[str] = []
        if not selected:
            warnings.append("No avoid-long/downside rules selected on train fold.")
        if not blocked:
            warnings.append("No test trades blocked by selected risk rules.")
        for row in selected:
            rid = str(row.get("rule_id"))
            bucket = frequency.setdefault(rid, {"rule_id": rid, "rule_family": row.get("rule_family"), "selected_folds": 0, "train_scores": [], "return_deltas": [], "stop_deltas": []})
            bucket["selected_folds"] += 1
            bucket["train_scores"].append(_to_float(row.get("score")) or 0.0)
            bucket["return_deltas"].append(_to_float(impact.get("avg_return_delta_pct")) or 0.0)
            bucket["stop_deltas"].append(_to_float(impact.get("stop_hit_delta_pct")) or 0.0)
        quality = "good" if impact["avg_return_delta_pct"] > 0 and impact["profit_factor_delta"] > 0 and impact["stop_hit_delta_pct"] < 0 else "medium" if impact["avg_return_delta_pct"] > 0 or impact["stop_hit_delta_pct"] < 0 else "weak"
        if len(test_rows) < min_signals:
            quality = "unstable"
        fold_results.append(
            {
                "fold": spec["fold"],
                "train_period": _period(train_rows),
                "test_period": _period(test_rows),
                "selected_avoid_rules": selected,
                "baseline_test_metrics": baseline_metrics,
                "filtered_test_metrics": kept_metrics,
                "avoided_test_metrics": blocked_metrics,
                "impact": impact,
                "quality_label": quality,
                "warnings": warnings,
            }
        )
    completed = len(fold_results)
    return_deltas = [_to_float((fold.get("impact") or {}).get("avg_return_delta_pct")) for fold in fold_results]
    pf_deltas = [_to_float((fold.get("impact") or {}).get("profit_factor_delta")) for fold in fold_results]
    stop_deltas = [_to_float((fold.get("impact") or {}).get("stop_hit_delta_pct")) for fold in fold_results]
    coverages = [_to_float((fold.get("impact") or {}).get("coverage_after_filter_pct")) for fold in fold_results]
    positive = sum(1 for fold in fold_results if (_to_float((fold.get("impact") or {}).get("avg_return_delta_pct")) or 0.0) > 0 and (_to_float((fold.get("impact") or {}).get("stop_hit_delta_pct")) or 0.0) < 0)
    freq_rows = [
        {
            "rule_id": rid,
            "rule_family": item.get("rule_family"),
            "selected_folds": item["selected_folds"],
            "avg_train_score": _round(mean(item["train_scores"]), 2) if item["train_scores"] else None,
            "avg_return_delta_pct": _round(mean(item["return_deltas"]), 2) if item["return_deltas"] else None,
            "avg_stop_hit_delta_pct": _round(mean(item["stop_deltas"]), 2) if item["stop_deltas"] else None,
        }
        for rid, item in frequency.items()
    ]
    freq_rows.sort(key=lambda row: (int(row.get("selected_folds") or 0), _to_float(row.get("avg_train_score")) or -999), reverse=True)
    summary = {
        "samples": len(rows),
        "event_samples": len(event_rows),
        "folds_requested": folds,
        "folds_completed": completed,
        "avg_return_delta_pct": _round(mean([x for x in return_deltas if x is not None]), 2) if any(x is not None for x in return_deltas) else None,
        "avg_profit_factor_delta": _round(mean([x for x in pf_deltas if x is not None]), 3) if any(x is not None for x in pf_deltas) else None,
        "avg_stop_hit_delta_pct": _round(mean([x for x in stop_deltas if x is not None]), 2) if any(x is not None for x in stop_deltas) else None,
        "avg_coverage_after_filter_pct": _round(mean([x for x in coverages if x is not None]), 2) if any(x is not None for x in coverages) else None,
        "total_avoided_losses": sum(int((fold.get("impact") or {}).get("avoided_losses") or 0) for fold in fold_results),
        "total_missed_winners": sum(int((fold.get("impact") or {}).get("missed_winners") or 0) for fold in fold_results),
        "positive_impact_folds": positive,
        "negative_impact_folds": completed - positive,
        "best_rule_frequency": freq_rows[:10],
        "warnings": sample_data["warnings"],
    }
    summary["recommendation"] = dual_side_walk_forward_recommendation(summary)
    if not fold_results:
        summary["recommendation"] = "needs_more_data"
        summary["warnings"].append("not enough event samples to build requested dual-side walk-forward folds")
    return {
        "ok": True,
        "mode": "event_aware_dual_side_walk_forward",
        "summary": summary,
        "folds": fold_results,
        "best_rule_frequency": freq_rows,
        "limitations": [
            "Risk rules are selected on train folds only and applied to future test folds.",
            "This evaluates avoid-long/reduce-exposure filters, not production short trading.",
            "Proxy backtest uses daily candles and simplified costs.",
            "Production consumer recommendations are unchanged.",
        ],
    }
