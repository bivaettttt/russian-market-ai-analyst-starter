from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import mean, pstdev
from typing import Any

from sqlalchemy.orm import Session

from app.services.consumer_signals import _round, _to_float
from app.services.event_aware_dual_side_research import (
    _baseline_metrics,
    _build_dual_samples,
    _dual_metrics,
)
from app.services.event_aware_rule_search import (
    generate_event_aware_rules,
    sample_matches_event_rule,
)
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


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return _round(mean(clean), 2) if clean else None


def concentration_label(concentration: dict[str, Any]) -> str:
    ticker = _to_float(concentration.get("top_ticker_share_pct")) or 0.0
    event = _to_float(concentration.get("top_event_share_pct")) or 0.0
    year = _to_float(concentration.get("top_year_share_pct")) or 0.0
    worst = max(ticker, event, year)
    if worst > 70:
        return "extreme"
    if worst > 50:
        return "high"
    if worst > 30:
        return "medium"
    return "low"


def _concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {
            "top_ticker": None,
            "top_ticker_share_pct": 0.0,
            "top_event_id": None,
            "top_event_share_pct": 0.0,
            "top_year": None,
            "top_year_share_pct": 0.0,
            "top_sector": None,
            "top_sector_share_pct": 0.0,
            "concentration_label": "low",
        }
    tickers = Counter(str(row.get("ticker") or "unknown") for row in rows)
    events = Counter(str(row.get("event_id") or row.get("event_title") or "none") for row in rows)
    years = Counter(str((_as_date(row.get("date")) or date.min).year) for row in rows)
    sectors = Counter(str(row.get("sector") or "unknown") for row in rows)
    top_ticker = tickers.most_common(1)[0]
    top_event = events.most_common(1)[0]
    top_year = years.most_common(1)[0]
    top_sector = sectors.most_common(1)[0]
    result = {
        "top_ticker": top_ticker[0],
        "top_ticker_share_pct": _round(top_ticker[1] / total * 100, 2) or 0.0,
        "top_event_id": top_event[0],
        "top_event_share_pct": _round(top_event[1] / total * 100, 2) or 0.0,
        "top_year": top_year[0],
        "top_year_share_pct": _round(top_year[1] / total * 100, 2) or 0.0,
        "top_sector": top_sector[0],
        "top_sector_share_pct": _round(top_sector[1] / total * 100, 2) or 0.0,
    }
    result["concentration_label"] = concentration_label(result)
    return result


def _risk_positive(row: dict[str, Any]) -> bool:
    return (
        (_to_float(row.get("avg_long_trade_return_pct")) or 0.0) <= 0
        and (_to_float(row.get("avg_avoid_long_benefit_pct")) or 0.0)
        >= (_to_float(row.get("avg_missed_upside_pct")) or 0.0)
    )


def _minimal_metrics(rows: list[dict[str, Any]], baseline: dict[str, Any], *, min_signals: int) -> dict[str, Any]:
    metrics = _dual_metrics(rows, baseline=baseline, min_signals=min_signals)
    return {
        "samples": metrics.get("samples"),
        "avg_long_trade_return_pct": metrics.get("avg_long_trade_return_pct"),
        "long_profit_factor": metrics.get("long_profit_factor"),
        "long_stop_hit_rate_pct": metrics.get("long_stop_hit_rate_pct"),
        "avoid_benefit": metrics.get("avg_avoid_long_benefit_pct"),
        "missed_upside": metrics.get("avg_missed_upside_pct"),
        "score": metrics.get("score"),
        "quality_label": metrics.get("quality_label"),
    }


def _group_breakdown(rows: list[dict[str, Any]], field: str, baseline: dict[str, Any], *, min_signals: int, label: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if field == "date":
            row_date = _as_date(value)
            value = str(row_date.year) if row_date else "unknown"
        groups[str(value or "unknown")].append(row)
    result = []
    for key, items in sorted(groups.items()):
        entry = _minimal_metrics(items, baseline, min_signals=min_signals)
        entry[label] = int(key) if key.isdigit() and label == "year" else key
        result.append(entry)
    return result


def _time_buckets(rows: list[dict[str, Any]], baseline: dict[str, Any], *, min_signals: int, buckets: int = 4) -> list[dict[str, Any]]:
    dated = [row for row in rows if _as_date(row.get("date")) is not None]
    dated.sort(key=lambda row: (_as_date(row.get("date")) or date.min, str(row.get("ticker") or "")))
    if not dated:
        return []
    size = max(1, len(dated) // buckets)
    result = []
    for index in range(buckets):
        start = index * size
        end = len(dated) if index == buckets - 1 else min(len(dated), (index + 1) * size)
        items = dated[start:end]
        if not items:
            continue
        entry = _minimal_metrics(items, baseline, min_signals=min_signals)
        entry["bucket"] = index + 1
        entry["first_date"] = (_as_date(items[0].get("date")) or date.min).isoformat()
        entry["last_date"] = (_as_date(items[-1].get("date")) or date.min).isoformat()
        result.append(entry)
    return result


def _regime_value(row: dict[str, Any]) -> str:
    value = row.get("market_regime") or row.get("market_regime_name") or row.get("regime")
    if isinstance(value, dict):
        value = value.get("regime") or value.get("label")
    text = str(value or "unknown").lower()
    if "risk_off" in text or "bear" in text:
        return "risk_off"
    if "risk_on" in text or "bull" in text:
        return "risk_on"
    if "neutral" in text or "sideways" in text:
        return "neutral"
    return "unknown"


def score_rule_stability(
    *,
    overall_metrics: dict[str, Any],
    by_year: list[dict[str, Any]],
    by_time_bucket: list[dict[str, Any]],
    concentration: dict[str, Any],
    baseline: dict[str, Any],
    min_signals: int,
) -> dict[str, Any]:
    samples = int(overall_metrics.get("samples") or 0)
    years_with_samples = sum(1 for row in by_year if int(row.get("samples") or 0) > 0)
    positive_years = sum(1 for row in by_year if _risk_positive(row))
    negative_years = sum(1 for row in by_year if int(row.get("samples") or 0) > 0 and not _risk_positive(row))
    positive_buckets = sum(1 for row in by_time_bucket if _risk_positive(row))
    negative_buckets = sum(1 for row in by_time_bucket if int(row.get("samples") or 0) > 0 and not _risk_positive(row))
    year_rate = _round(positive_years / years_with_samples * 100, 2) if years_with_samples else 0.0
    bucket_total = positive_buckets + negative_buckets
    bucket_rate = _round(positive_buckets / bucket_total * 100, 2) if bucket_total else 0.0
    scores = [_to_float(row.get("score")) for row in by_year if _to_float(row.get("score")) is not None]
    avg_avoid = _to_float(overall_metrics.get("avg_avoid_long_benefit_pct")) or _to_float(overall_metrics.get("avoid_benefit")) or 0.0
    avg_missed = _to_float(overall_metrics.get("avg_missed_upside_pct")) or _to_float(overall_metrics.get("missed_upside")) or 0.0
    score = (_to_float(overall_metrics.get("score")) or 0.0)
    score += year_rate * 0.25
    score += bucket_rate * 0.25
    score += min(years_with_samples, 4) * 3
    score += positive_years * 3
    score -= negative_years * 3
    if avg_missed > avg_avoid:
        score -= 25
    if (_to_float(concentration.get("top_ticker_share_pct")) or 0.0) > 50:
        score -= 20
    if (_to_float(concentration.get("top_event_share_pct")) or 0.0) > 50:
        score -= 20
    if (_to_float(concentration.get("top_year_share_pct")) or 0.0) > 70:
        score -= 15
    if samples < min_signals:
        score -= 40
    if years_with_samples < 2:
        score -= 25
    score = _round(max(-100.0, min(100.0, score)), 2) or 0.0

    concentration_bad = (
        (_to_float(concentration.get("top_ticker_share_pct")) or 0.0) > 50
        or (_to_float(concentration.get("top_event_share_pct")) or 0.0) > 50
    )
    if avg_missed > avg_avoid or score < 0 or concentration.get("concentration_label") == "extreme":
        label = "reject"
    elif (
        samples >= min_signals
        and years_with_samples >= 3
        and year_rate >= 60
        and bucket_rate >= 50
        and not concentration_bad
        and avg_avoid > avg_missed
        and score >= 25
    ):
        label = "stable"
    elif samples >= min_signals and years_with_samples >= 2 and score >= 10:
        label = "moderate"
    else:
        label = "unstable"
    return {
        "stability_score": score,
        "stability_label": label,
        "years_with_samples": years_with_samples,
        "positive_risk_years": positive_years,
        "negative_risk_years": negative_years,
        "year_stability_rate_pct": year_rate,
        "positive_buckets": positive_buckets,
        "negative_buckets": negative_buckets,
        "bucket_stability_rate_pct": bucket_rate,
        "worst_year_score": _round(min(scores), 2) if scores else None,
        "best_year_score": _round(max(scores), 2) if scores else None,
        "score_std": _round(pstdev(scores), 2) if len(scores) > 1 else 0.0,
    }


def _failure_modes(row: dict[str, Any]) -> list[str]:
    failures = []
    if int(row.get("samples") or 0) < int(row.get("min_signals") or 0):
        failures.append("low_sample_count")
    if (_to_float(row.get("avg_missed_upside_pct")) or 0.0) > (_to_float(row.get("avg_avoid_long_benefit_pct")) or 0.0):
        failures.append("missed_winners_high")
    if (_to_float(row.get("top_ticker_share_pct")) or 0.0) > 50:
        failures.append("ticker_concentration")
    if (_to_float(row.get("top_event_share_pct")) or 0.0) > 50:
        failures.append("one_event_dependency")
    if (_to_float(row.get("top_year_share_pct")) or 0.0) > 70 or int(row.get("years_with_samples") or 0) < 2:
        failures.append("one_year_dependency")
    if (_to_float(row.get("year_stability_rate_pct")) or 0.0) < 50:
        failures.append("inconsistent_by_year")
    if (_to_float(row.get("bucket_stability_rate_pct")) or 0.0) < 50:
        failures.append("static_only_no_walk_forward_transfer")
    return failures


def _diagnostic_note(failures: list[str]) -> str:
    if "missed_winners_high" in failures:
        return "Rule avoids too many future winners relative to avoided losses."
    if "one_year_dependency" in failures or "one_event_dependency" in failures:
        return "Rule is concentrated in a narrow event/year window."
    if "ticker_concentration" in failures:
        return "Rule is too dependent on one ticker."
    if "inconsistent_by_year" in failures:
        return "Rule is not stable across calendar years."
    if "static_only_no_walk_forward_transfer" in failures:
        return "Static result does not transfer across chronological buckets."
    return "Rule has mixed diagnostics."


def _regime_specificity(by_regime: list[dict[str, Any]]) -> tuple[str, str | None, str | None]:
    eligible = [row for row in by_regime if int(row.get("samples") or 0) > 0]
    if not eligible:
        return "unknown", None, None
    eligible.sort(key=lambda row: _to_float(row.get("score")) or -999, reverse=True)
    best = eligible[0]
    worst = eligible[-1]
    positive = [row for row in eligible if _risk_positive(row)]
    if len(positive) >= 2:
        specificity = "broad"
    elif positive:
        regime = str(positive[0].get("market_regime") or "unknown")
        specificity = f"{regime}_only" if regime in {"risk_on", "risk_off", "neutral"} else "unknown"
    else:
        specificity = "unknown"
    return specificity, str(best.get("market_regime")), str(worst.get("market_regime"))


def diagnose_static_to_walk_forward_failure(
    *,
    static_results: list[dict[str, Any]],
    walk_forward_result: dict[str, Any] | None = None,
    stability_results: list[dict[str, Any]],
) -> dict[str, Any]:
    findings: list[str] = []
    stable = [row for row in stability_results if row.get("stability_label") == "stable"]
    high_concentration = [row for row in stability_results if "one_event_dependency" in (row.get("failure_modes") or []) or "one_year_dependency" in (row.get("failure_modes") or [])]
    winner_miss = [row for row in stability_results if "missed_winners_high" in (row.get("failure_modes") or [])]
    regime_specific = [row for row in stability_results if str(row.get("recommended_use")) == "regime_specific_filter"]
    if not stable:
        primary = "rule_instability"
        findings.append("No rule met stable multi-year and multi-bucket criteria.")
    else:
        primary = "unknown"
        findings.append(f"{len(stable)} stable rules found.")
    if winner_miss:
        primary = "winner_miss_rate"
        findings.append("Several rules avoid future winners as often as or more than losers.")
    if high_concentration and not winner_miss:
        primary = "concentration"
        findings.append("Many rules depend on one event/year window.")
    if regime_specific and not stable:
        primary = "regime_shift"
        findings.append("Some rules appear useful only in a specific market regime.")
    if not stability_results:
        primary = "unknown"
        findings.append("No stability rows were available.")
    if primary == "rule_instability":
        next_step = "diagnostic_only"
    elif primary == "regime_shift":
        next_step = "build_regime_specific_overlay"
    elif primary in {"winner_miss_rate", "concentration"}:
        next_step = "reject_event_risk_filter"
    else:
        next_step = "diagnostic_only"
    return {
        "primary_failure_reason": primary,
        "findings": findings,
        "recommended_next_step": next_step,
    }


def _rule_stability_row(
    rule: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    baseline: dict[str, Any],
    min_signals: int,
) -> dict[str, Any]:
    overall = _dual_metrics(rows, baseline=baseline, min_signals=min_signals, rule=rule)
    by_year = _group_breakdown(rows, "date", baseline, min_signals=min_signals, label="year")
    by_bucket = _time_buckets(rows, baseline, min_signals=min_signals)
    by_regime = _group_breakdown([{**row, "market_regime_bucket": _regime_value(row)} for row in rows], "market_regime_bucket", baseline, min_signals=min_signals, label="market_regime")
    by_event_family = _group_breakdown(rows, "event_family", baseline, min_signals=min_signals, label="event_family")
    by_setup_group = _group_breakdown(rows, "setup_group", baseline, min_signals=min_signals, label="setup_group")
    concentration = _concentration(rows)
    stability = score_rule_stability(
        overall_metrics=overall,
        by_year=by_year,
        by_time_bucket=by_bucket,
        concentration=concentration,
        baseline=baseline,
        min_signals=min_signals,
    )
    regime_specificity, best_regime, worst_regime = _regime_specificity(by_regime)
    row = {
        "rule_id": rule.get("rule_id"),
        "rule_family": rule.get("rule_family"),
        "description": rule.get("description"),
        "samples": overall.get("samples"),
        "tickers": overall.get("tickers"),
        "events": overall.get("events"),
        "avg_long_trade_return_pct": overall.get("avg_long_trade_return_pct"),
        "long_profit_factor": overall.get("long_profit_factor"),
        "long_win_rate_pct": overall.get("long_win_rate_pct"),
        "long_stop_hit_rate_pct": overall.get("long_stop_hit_rate_pct"),
        "long_target_hit_rate_pct": overall.get("long_target_hit_rate_pct"),
        "negative_return_rate_pct": overall.get("negative_return_rate_pct"),
        "downside_flag_rate_pct": overall.get("downside_flag_rate_pct"),
        "avg_avoid_long_benefit_pct": overall.get("avg_avoid_long_benefit_pct"),
        "avg_missed_upside_pct": overall.get("avg_missed_upside_pct"),
        "risk_adjusted_avoid_score": overall.get("risk_adjusted_avoid_score"),
        "overall_score": overall.get("score"),
        "overall_quality_label": overall.get("quality_label"),
        "stop_hit_lift_vs_baseline": overall.get("stop_hit_lift_vs_baseline"),
        "downside_lift_vs_baseline": overall.get("downside_lift_vs_baseline"),
        "by_year": by_year,
        "by_time_bucket": by_bucket,
        "by_market_regime": by_regime,
        "by_event_family": by_event_family,
        "by_setup_group": by_setup_group,
        "best_regime": best_regime,
        "worst_regime": worst_regime,
        "regime_specificity": regime_specificity,
        **concentration,
        **stability,
        "min_signals": min_signals,
    }
    failures = _failure_modes(row)
    if row["stability_label"] == "stable" and row["overall_quality_label"] in {"good", "medium"}:
        recommended = "stable_risk_filter"
    elif row["stability_label"] in {"stable", "moderate"} and regime_specificity not in {"broad", "unknown"}:
        recommended = "regime_specific_filter"
    elif row["stability_label"] in {"moderate", "unstable"} and row["overall_quality_label"] not in {"bad", "unstable"}:
        recommended = "diagnostic_only"
    else:
        recommended = "reject"
    row.update(
        {
            "recommended_use": recommended,
            "failure_modes": failures,
            "diagnostic_note": _diagnostic_note(failures),
        }
    )
    return row


def build_event_aware_rule_stability_diagnostics(
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
    results = []
    for rule in rules:
        matched = [row for row in event_rows if sample_matches_event_rule(row, rule)]
        results.append(_rule_stability_row(rule, matched, baseline=baseline, min_signals=min_signals))
    results.sort(key=lambda row: (_to_float(row.get("stability_score")) or -999, int(row.get("samples") or 0)), reverse=True)
    stable = [row for row in results if row.get("stability_label") == "stable"]
    moderate = [row for row in results if row.get("stability_label") == "moderate"]
    unstable = [row for row in results if row.get("stability_label") == "unstable"]
    rejected = [row for row in results if row.get("stability_label") == "reject"]
    failure = diagnose_static_to_walk_forward_failure(static_results=results, stability_results=results)
    if len(event_rows) < min_signals:
        recommendation = "needs_more_data"
    elif any(row.get("recommended_use") == "stable_risk_filter" for row in stable):
        recommendation = "stable_risk_overlay_candidate"
    elif moderate or stable:
        recommendation = "diagnostic_only"
    else:
        recommendation = "reject_event_risk_filter"
    summary = {
        "samples": len(rows),
        "event_samples": len(event_rows),
        "rules_tested": len(rules),
        "stable_rules": len(stable),
        "moderate_rules": len(moderate),
        "unstable_rules": len(unstable),
        "rejected_rules": len(rejected),
        "best_stable_rule_id": (stable[0] or {}).get("rule_id") if stable else None,
        "primary_failure_reason": failure.get("primary_failure_reason"),
        "recommendation": recommendation,
        "warnings": sample_data["warnings"],
    }
    return {
        "ok": True,
        "mode": "event_aware_rule_stability",
        "summary": summary,
        "stable_rules": stable,
        "moderate_rules": moderate,
        "unstable_rules": unstable,
        "rejected_rules": rejected,
        "failure_analysis": failure,
        "baseline": baseline,
        "limitations": [
            "Diagnostics use curated event seed and proxy historical outcomes.",
            "Stability buckets are chronological diagnostics, not production trading rules.",
            "No production event-aware risk filter is enabled by this endpoint.",
            "Daily candle ambiguity and simplified costs still apply.",
        ],
    }
