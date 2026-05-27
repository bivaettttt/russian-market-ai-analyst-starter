from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from itertools import product
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.models import MarketEvent
from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.consumer_signals import _round, _to_float
from app.services.event_ticker_mapping import classify_event_family, map_event_to_market_impact
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID
from app.services.setup_candidate_generator import SETUP_FAMILIES, classify_setup_families
from app.services.setup_family_research import (
    _build_policy_samples,
    classify_setup_family_quality,
    score_setup_config_result,
)


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except Exception:
            try:
                return datetime.strptime(text[:10], "%Y-%m-%d").date()
            except Exception:
                return None
    return None


def decay_event_score(raw_score: float | None, days_since_event: int | float, event_decay_days: int) -> float:
    score = _to_float(raw_score) or 0.0
    if event_decay_days <= 0:
        return _round(score, 2) or 0.0
    factor = max(0.0, 1.0 - max(0.0, float(days_since_event)) / float(event_decay_days))
    return _round(score * factor, 2) or 0.0


def event_confirmation_for_long(event_impact: dict[str, Any] | None) -> str:
    if not event_impact:
        return "none"
    direction = str(event_impact.get("direction") or "unknown").lower()
    score = _to_float(event_impact.get("effective_score") or event_impact.get("score")) or 0.0
    if direction == "positive" and score > 0:
        return "confirmed"
    if direction == "negative" or score < 0:
        return "conflict"
    if direction in {"mixed", "neutral", "unknown"}:
        return "neutral"
    return "none"


def _event_to_dict(event: MarketEvent) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    raw_analysis = getattr(event, "raw_analysis", None)
    if raw_analysis:
        try:
            parsed = json.loads(raw_analysis)
            if isinstance(parsed, dict):
                raw = parsed
        except Exception:
            raw = {}
    created_at = getattr(event, "created_at", None)
    return {
        "id": getattr(event, "id", None),
        "title": getattr(event, "title", None),
        "text": getattr(event, "text", None),
        "source": getattr(event, "source", None),
        "url": getattr(event, "url", None),
        "importance": getattr(event, "importance", None) or raw.get("importance"),
        "impact": getattr(event, "impact", None) or raw.get("impact"),
        "affected_assets": raw.get("affected_assets") or [],
        "affected_sectors": raw.get("affected_sectors") or [],
        "affected_asset_types": raw.get("affected_asset_types") or [],
        "affected_tickers": raw.get("affected_tickers") or [],
        "event_family": raw.get("event_family"),
        "direction": raw.get("direction"),
        "impact_scope": raw.get("impact_scope"),
        "score": raw.get("score"),
        "confidence": raw.get("confidence"),
        "event_type": raw.get("event_type") or raw.get("event_family"),
        "tags": raw.get("tags") or [],
        "reasoning": getattr(event, "reasoning", None) or raw.get("reasoning"),
        "raw_analysis": raw,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at) if created_at else None,
        "event_date": _as_date(created_at),
    }


def _load_events(db: Session, *, max_events: int) -> list[dict[str, Any]]:
    if max_events <= 0:
        return []
    rows = (
        db.query(MarketEvent)
        .order_by(MarketEvent.created_at.desc())
        .limit(max_events)
        .all()
    )
    events = [_event_to_dict(row) for row in rows]
    events.sort(key=lambda item: item.get("event_date") or date.min)
    return events


def _instrument(sample: dict[str, Any]) -> dict[str, Any]:
    instrument = sample.get("instrument") if isinstance(sample.get("instrument"), dict) else {}
    return {
        "ticker": sample.get("ticker") or instrument.get("ticker") or instrument.get("secid"),
        "sector": sample.get("sector") or instrument.get("sector"),
        "asset_type": sample.get("asset_type") or instrument.get("asset_type"),
    }


def _is_relevant_event(
    event_impact: dict[str, Any],
    instrument: dict[str, Any],
    *,
    include_global_events: bool,
    include_ticker_events: bool,
) -> bool:
    scope = str(event_impact.get("impact_scope") or "unknown")
    ticker = str(instrument.get("ticker") or "").upper()
    sector = str(instrument.get("sector") or "").lower()
    asset_type = str(instrument.get("asset_type") or "").lower()
    tickers = {str(item).upper() for item in event_impact.get("affected_tickers") or []}
    sectors = {str(item).lower() for item in event_impact.get("affected_sectors") or []}
    asset_types = {str(item).lower() for item in event_impact.get("affected_asset_types") or []}

    if scope == "ticker" or ticker in tickers:
        return include_ticker_events and bool(ticker and (ticker in tickers or not tickers))
    if sector and any(sector in item or item in sector for item in sectors):
        return True
    if asset_type and asset_type in asset_types:
        return True
    if scope in {"market", "asset_class", "global"}:
        return include_global_events
    if scope == "sector":
        return bool(sector and sectors)
    return include_global_events and event_impact.get("event_family") in {"macro", "geopolitics", "sanctions", "rates"}


def _best_event_for_sample(
    sample: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    event_lookback_days: int,
    event_decay_days: int,
    include_global_events: bool,
    include_ticker_events: bool,
    min_event_score: float = 0.0,
) -> dict[str, Any] | None:
    sample_date = _as_date(sample.get("date"))
    if sample_date is None:
        return None
    instrument = _instrument(sample)
    start = sample_date - timedelta(days=event_lookback_days)
    candidates: list[dict[str, Any]] = []
    for event in events:
        event_date = event.get("event_date")
        if not isinstance(event_date, date) or event_date < start or event_date > sample_date:
            continue
        impact = map_event_to_market_impact(event, instrument=instrument)
        if not _is_relevant_event(
            impact,
            instrument,
            include_global_events=include_global_events,
            include_ticker_events=include_ticker_events,
        ):
            continue
        age_days = (sample_date - event_date).days
        effective = decay_event_score(impact.get("score"), age_days, event_decay_days)
        if abs(effective) < min_event_score:
            continue
        impact["effective_score"] = effective
        impact["event_age_days"] = age_days
        impact["event_id"] = event.get("id") or (event.get("raw_analysis") or {}).get("event_id")
        impact["event_title"] = event.get("title")
        impact["event_date"] = event_date.isoformat()
        candidates.append(impact)
    if not candidates:
        return None
    return max(candidates, key=lambda item: abs(_to_float(item.get("effective_score")) or 0.0))


def _setup_rows_for_sample(sample: dict[str, Any], setup_mode: str) -> tuple[list[str], dict[str, Any]]:
    history = sample.get("history") if isinstance(sample.get("history"), list) else []
    cfg: dict[str, Any] = {}
    market_regime = sample.get("market_regime") if isinstance(sample.get("market_regime"), dict) else {}
    cfg.setdefault("market_regime", sample.get("market_regime_name") or market_regime.get("regime"))
    cfg.setdefault("market_regime_score", sample.get("market_regime_score") or market_regime.get("regime_score"))
    classified = classify_setup_families(history, config=cfg)
    if not classified.get("ok"):
        return [], classified
    active = list(classified.get("active_setup_families") or [])
    if setup_mode == "primary_setup_only":
        primary = classified.get("primary_setup_family")
        active = [primary] if primary else []
    elif setup_mode == "selected_families":
        active = [name for name in active if name in {"trend_following", "pullback", "mean_reversion", "breakout"}]
    return active, classified


def _event_rows(
    samples: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    event_lookback_days: int,
    event_decay_days: int,
    include_global_events: bool,
    include_ticker_events: bool,
    min_event_score: float = 0.0,
    confirmation_mode: str = "all",
    setup_mode: str = "any_setup",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        trade_return = _to_float(sample.get("trade_return_pct"))
        if trade_return is None:
            continue
        active, classified = _setup_rows_for_sample(sample, setup_mode)
        best_event = _best_event_for_sample(
            sample,
            events,
            event_lookback_days=event_lookback_days,
            event_decay_days=event_decay_days,
            include_global_events=include_global_events,
            include_ticker_events=include_ticker_events,
            min_event_score=min_event_score,
        )
        confirmation = event_confirmation_for_long(best_event)
        if confirmation_mode == "positive_only" and confirmation != "confirmed":
            best_event = None
            confirmation = "none"
        elif confirmation_mode == "positive_or_mixed" and confirmation == "conflict":
            best_event = None
            confirmation = "none"
        elif confirmation_mode == "exclude_conflict" and confirmation == "conflict":
            best_event = None
            confirmation = "none"

        if active:
            for family in active:
                setup = (classified.get("setups") or {}).get(family) or {}
                row_confirmation = confirmation if best_event else "none"
                sample_type = (
                    "setup_event_confirmed" if row_confirmation == "confirmed"
                    else "setup_event_conflict" if row_confirmation == "conflict"
                    else "setup_event_neutral" if row_confirmation == "neutral"
                    else "setup_only"
                )
                rows.append(_sample_row(sample, family, setup, classified, best_event, row_confirmation, sample_type))
        elif best_event and confirmation in {"confirmed", "neutral"}:
            rows.append(_sample_row(sample, None, {}, classified, best_event, "event_only", "event_only"))
    return rows


def _sample_row(
    sample: dict[str, Any],
    setup_family: str | None,
    setup: dict[str, Any],
    classified: dict[str, Any],
    event_impact: dict[str, Any] | None,
    event_confirmation: str,
    sample_type: str,
) -> dict[str, Any]:
    return {
        "ticker": sample.get("ticker"),
        "date": sample.get("date"),
        "sector": sample.get("sector") or (_instrument(sample).get("sector")),
        "setup_family": setup_family,
        "setup_score": setup.get("score"),
        "setup_confidence": setup.get("confidence"),
        "primary_setup_family": classified.get("primary_setup_family"),
        "event_family": event_impact.get("event_family") if event_impact else None,
        "event_direction": event_impact.get("direction") if event_impact else None,
        "event_scope": event_impact.get("impact_scope") if event_impact else None,
        "event_score": event_impact.get("effective_score") if event_impact else None,
        "event_raw_score": event_impact.get("score") if event_impact else None,
        "event_age_days": event_impact.get("event_age_days") if event_impact else None,
        "event_id": event_impact.get("event_id") if event_impact else None,
        "event_confirmation": event_confirmation,
        "event_title": event_impact.get("event_title") if event_impact else None,
        "sample_type": sample_type,
        "outcome": sample.get("outcome"),
        "trade_return_pct": sample.get("trade_return_pct"),
        "target_pct": sample.get("target_return_pct"),
        "stop_pct": sample.get("stop_return_pct"),
        "mfe_pct": sample.get("mfe_pct"),
        "mae_pct": sample.get("mae_pct"),
    }


def build_event_aware_samples(
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
    include_global_events: bool = True,
    include_ticker_events: bool = True,
) -> dict[str, Any]:
    base_samples, tickers_used, warnings, policy = _build_policy_samples(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    events = _load_events(db, max_events=max_events)
    if not events:
        warnings.append("no historical events found; event-aware samples contain setup-only rows")
    rows = _event_rows(
        base_samples,
        events,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )
    event_rows = [row for row in rows if row.get("event_family")]
    confirmed_rows = [row for row in rows if row.get("event_confirmation") == "confirmed"]
    if events and not event_rows:
        warnings.append("no event-linked samples found; event dates may not overlap historical candle samples/lookback window")
    return {
        "ok": True,
        "mode": "event_aware_samples",
        "samples": rows,
        "summary": {
            "samples": len(rows),
            "base_samples": len(base_samples),
            "event_samples": len(event_rows),
            "confirmed_samples": len(confirmed_rows),
            "tickers_used": len(tickers_used),
            "events_used": len(events),
            "policy": policy,
        },
        "warnings": warnings,
    }


def _metrics(rows: list[dict[str, Any]], *, group_key: str, min_signals: int) -> dict[str, Any]:
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )
    event_scores = [_to_float(row.get("event_score")) for row in rows if _to_float(row.get("event_score")) is not None]
    setup_scores = [_to_float(row.get("setup_score")) for row in rows if _to_float(row.get("setup_score")) is not None]
    tickers = {row.get("ticker") for row in rows if row.get("ticker")}
    quality = classify_setup_family_quality(
        samples=len(rows),
        profit_factor=pnl.get("profit_factor"),
        avg_trade_return_pct=pnl.get("avg_trade_return_pct"),
        min_signals=min_signals,
    )
    first = rows[0] if rows else {}
    return {
        "group_key": group_key,
        "setup_family": first.get("setup_family"),
        "event_family": first.get("event_family"),
        "event_direction": first.get("event_direction"),
        "event_confirmation": first.get("event_confirmation"),
        "event_scope": first.get("event_scope"),
        "samples": len(rows),
        "tickers": len(tickers),
        "avg_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "median_trade_return_pct": pnl.get("median_trade_return_pct"),
        "profit_factor": pnl.get("profit_factor"),
        "win_rate_pct": pnl.get("win_rate_pct"),
        "target_hit_rate_pct": pnl.get("target_hit_rate_pct"),
        "stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
        "timeout_rate_pct": pnl.get("timeout_rate_pct"),
        "avg_event_score": _round(mean(event_scores), 2) if event_scores else None,
        "avg_setup_score": _round(mean(setup_scores), 2) if setup_scores else None,
        "quality_label": quality,
        "diagnostic": _diagnostic(quality),
    }


def _diagnostic(quality: str) -> str:
    if quality == "good":
        return "Promising event/setup combination; validate with walk-forward and paper trading."
    if quality == "medium":
        return "Potential event-aware edge with modest metrics."
    if quality == "bad":
        return "Negative expectancy group in this proxy sample."
    if quality == "unstable":
        return "Too few event-linked samples for a stable conclusion."
    return "Enough samples but weak metrics."


def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quality_rank = {"good": 4, "medium": 3, "weak": 2, "bad": 1, "unstable": 0}
    return sorted(
        rows,
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label")), 0),
            _to_float(row.get("profit_factor")) if _to_float(row.get("profit_factor")) is not None else -999,
            _to_float(row.get("avg_trade_return_pct")) if _to_float(row.get("avg_trade_return_pct")) is not None else -999,
            int(row.get("samples") or 0),
        ),
        reverse=True,
    )


def event_density_score(total_events: int, events_by_year: dict[str, int]) -> str:
    if total_events <= 0:
        return "empty"
    covered_years = sum(1 for count in events_by_year.values() if int(count or 0) >= 20)
    core_years = [int(events_by_year.get(str(year), 0) or 0) for year in range(2022, 2026)]
    if total_events >= 300 and all(count >= 40 for count in core_years):
        return "good"
    if total_events >= 250 and covered_years >= 4 and all(count >= 20 for count in core_years):
        return "medium"
    return "weak"


def event_coverage_recommendations(
    *,
    total_events: int,
    events_by_year: dict[str, int],
    by_event_family: dict[str, int],
    events_with_ticker: int,
    dates: list[date],
) -> list[str]:
    recommendations: list[str] = []
    if total_events < 250:
        recommendations.append("Expand historical event seed to at least 250 events before relying on event-aware validation.")
    for year in range(2022, 2027):
        count = int(events_by_year.get(str(year), 0) or 0)
        if count < 20:
            recommendations.append(f"Add more historical events for {year}; current coverage is {count}.")
    if events_with_ticker <= 0:
        recommendations.append("Add corporate/ticker-level historical events for liquid MOEX names.")
    macro_count = sum(int(by_event_family.get(name, 0) or 0) for name in ["macro", "inflation", "rates", "fx"])
    if macro_count <= 0:
        recommendations.append("Add macro, rates and FX events to support event-aware research.")
    if dates and min(dates).year >= date.today().year:
        recommendations.append("Historical event coverage is insufficient for backtest; import events covering candle sample dates.")
    if total_events <= 0:
        recommendations.append("Import historical events covering 2022-2026 before relying on event-aware research.")
    return recommendations


def _missing_months(dates: list[date]) -> list[str]:
    if not dates:
        return []
    start = date(min(dates).year, min(dates).month, 1)
    end = date(max(dates).year, max(dates).month, 1)
    present = {f"{item.year}-{item.month:02d}" for item in dates}
    missing: list[str] = []
    cursor = start
    while cursor <= end:
        key = f"{cursor.year}-{cursor.month:02d}"
        if key not in present:
            missing.append(key)
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return missing


def _group_rows(rows: list[dict[str, Any]], key_fn: Any, *, min_signals: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(key_fn(row))].append(row)
    return _rank([_metrics(items, group_key=key, min_signals=min_signals) for key, items in groups.items()])


def build_event_aware_setup_research(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    max_events: int = 5000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    event_lookback_days: int = 7,
    event_decay_days: int = 14,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_signals: int = 20,
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
    rows = list(sample_data.get("samples") or [])
    sample_summary = sample_data.get("summary") or {}
    warnings = list(sample_data.get("warnings") or [])
    event_rows = [row for row in rows if row.get("event_family")]
    confirmed_rows = [row for row in rows if row.get("event_confirmation") == "confirmed"]

    by_event_family = _group_rows(event_rows, lambda row: row.get("event_family") or "none", min_signals=min_signals)
    by_combo = _group_rows(
        [row for row in event_rows if row.get("setup_family")],
        lambda row: f"{row.get('setup_family')}+{row.get('event_family')}_{row.get('event_direction')}",
        min_signals=min_signals,
    )
    best = by_combo[0] if by_combo else by_event_family[0] if by_event_family else None
    if not sample_summary.get("base_samples"):
        recommendation = "needs_more_event_data"
    elif not event_rows:
        recommendation = "needs_more_event_data"
    elif best and best.get("quality_label") in {"good", "medium"}:
        recommendation = "promising_event_edge"
    else:
        recommendation = "no_event_edge_found"

    event_families = Counter(row.get("event_family") for row in event_rows if row.get("event_family"))
    summary = {
        "samples": len(rows),
        "base_samples": sample_summary.get("base_samples"),
        "event_samples": len(event_rows),
        "setup_event_confirmed_samples": len(confirmed_rows),
        "tickers_used": sample_summary.get("tickers_used"),
        "events_used": sample_summary.get("events_used"),
        "event_families": dict(event_families),
        "best_group_key": best.get("group_key") if best else None,
        "best_quality_label": best.get("quality_label") if best else None,
        "policy": sample_summary.get("policy"),
        "recommendation": recommendation,
        "warnings": warnings,
    }
    sorted_examples = sorted(event_rows, key=lambda row: _to_float(row.get("trade_return_pct")) or 0.0, reverse=True)
    return {
        "ok": True,
        "mode": "event_aware_setup_research",
        "summary": summary,
        "by_event_family": by_event_family,
        "by_setup_event_combo": by_combo,
        "best_combinations": by_combo[:10],
        "bad_combinations": [row for row in by_combo if row.get("quality_label") == "bad"],
        "examples": {
            "best_examples": sorted_examples[:10],
            "conflict_examples": [row for row in event_rows if row.get("event_confirmation") == "conflict"][:10],
            "event_only_examples": [row for row in event_rows if row.get("sample_type") == "event_only"][:10],
        },
        "limitations": [
            "Historical event coverage may be incomplete or absent in local DB.",
            "Event classification and ticker/sector mapping are deterministic heuristics.",
            "No external API is called by this endpoint.",
            "Proxy backtest on daily candles; event timestamp/date granularity can be coarse.",
            "Costs are simplified commission/slippage assumptions.",
            "Research-only layer; production consumer logic is unchanged.",
        ],
    }


def build_event_coverage_diagnostics(
    db: Session,
    *,
    max_events: int = 5000,
) -> dict[str, Any]:
    events = _load_events(db, max_events=max_events)
    family_counter: Counter[str] = Counter()
    direction_counter: Counter[str] = Counter()
    scope_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    year_counter: Counter[str] = Counter()
    month_counter: Counter[str] = Counter()
    with_ticker = 0
    with_sector_scope = 0
    with_market_scope = 0
    with_tags = 0
    curated_seed_events = 0
    curated_seed_v2_events = 0
    dates: list[date] = []
    examples: list[dict[str, Any]] = []
    for event in events:
        mapped = classify_event_family(event)
        family_counter[str(mapped.get("event_family") or "unknown")] += 1
        direction_counter[str(mapped.get("direction") or "unknown")] += 1
        scope_counter[str(mapped.get("impact_scope") or "unknown")] += 1
        source = str(event.get("source") or "unknown")
        source_counter[source] += 1
        if source == "curated_seed":
            curated_seed_events += 1
        if source == "curated_seed_v2":
            curated_seed_v2_events += 1
        if mapped.get("affected_tickers"):
            with_ticker += 1
        if mapped.get("impact_scope") == "sector":
            with_sector_scope += 1
        if mapped.get("impact_scope") in {"market", "global", "asset_class"}:
            with_market_scope += 1
        if mapped.get("tags"):
            with_tags += 1
        event_date = event.get("event_date")
        if isinstance(event_date, date):
            dates.append(event_date)
            year_counter[str(event_date.year)] += 1
            month_counter[f"{event_date.year}-{event_date.month:02d}"] += 1
        if len(examples) < 10:
            examples.append(
                {
                    "title": event.get("title"),
                    "date": event_date.isoformat() if isinstance(event_date, date) else None,
                    "event_family": mapped.get("event_family"),
                    "direction": mapped.get("direction"),
                    "scope": mapped.get("impact_scope"),
                    "score": mapped.get("score"),
                }
            )
    warnings = [] if events else ["no historical events found"]
    missing_months = _missing_months(dates)
    sparse_years = {year: count for year, count in dict(year_counter).items() if int(count or 0) < 20}
    coverage_gaps = {
        "sparse_years": sparse_years,
        "missing_months": missing_months,
        "missing_months_count": len(missing_months),
    }
    recommendations = event_coverage_recommendations(
        total_events=len(events),
        events_by_year=dict(year_counter),
        by_event_family=dict(family_counter),
        events_with_ticker=with_ticker,
        dates=dates,
    )
    return {
        "ok": True,
        "mode": "event_coverage_diagnostics",
        "summary": {
            "total_events": len(events),
            "curated_seed_events": curated_seed_events,
            "curated_seed_v2_events": curated_seed_v2_events,
            "live_events": len(events) - curated_seed_events - curated_seed_v2_events,
            "events_by_source": dict(source_counter),
            "events_with_ticker": with_ticker,
            "events_with_sector_scope": with_sector_scope,
            "events_with_market_scope": with_market_scope,
            "events_with_date": len(dates),
            "events_with_tags": with_tags,
            "date_range": {"from": min(dates).isoformat(), "to": max(dates).isoformat()} if dates else {},
            "events_by_year": dict(year_counter),
            "events_by_month": dict(month_counter),
            "by_event_family": dict(family_counter),
            "by_direction": dict(direction_counter),
            "by_scope": dict(scope_counter),
            "coverage_gaps": coverage_gaps,
            "event_density_score": event_density_score(len(events), dict(year_counter)),
        },
        "by_year": dict(year_counter),
        "by_month": dict(month_counter),
        "by_source": dict(source_counter),
        "coverage_gaps": coverage_gaps,
        "examples": examples,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def _sweep_configs(max_configs: int) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for lookback, decay, min_score, confirmation, setup_mode in product(
        [3, 7, 14],
        [7, 14, 30],
        [10, 20, 30],
        ["positive_only", "positive_or_mixed", "exclude_conflict"],
        ["any_setup", "primary_setup_only"],
    ):
        configs.append(
            {
                "event_lookback_days": lookback,
                "event_decay_days": decay,
                "min_event_score": min_score,
                "confirmation_mode": confirmation,
                "setup_mode": setup_mode,
            }
        )
    return configs[:max_configs]


def build_event_aware_setup_sweep(
    db: Session,
    *,
    max_tickers: int = 80,
    max_samples: int = 3000,
    max_events: int = 5000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    max_configs: int = 60,
    min_signals: int = 20,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> dict[str, Any]:
    samples, tickers_used, warnings, policy = _build_policy_samples(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    events = _load_events(db, max_events=max_events)
    if not events:
        warnings.append("no historical events found; sweep has no event-aware candidates")
    results: list[dict[str, Any]] = []
    for index, config in enumerate(_sweep_configs(max_configs), start=1):
        rows = _event_rows(
            samples,
            events,
            event_lookback_days=int(config["event_lookback_days"]),
            event_decay_days=int(config["event_decay_days"]),
            include_global_events=True,
            include_ticker_events=True,
            min_event_score=float(config["min_event_score"]),
            confirmation_mode=str(config["confirmation_mode"]),
            setup_mode=str(config["setup_mode"]),
        )
        event_rows = [row for row in rows if row.get("event_family")]
        metrics = _metrics(event_rows, group_key=f"event_aware_config_{index}", min_signals=min_signals)
        row = {
            "config_id": f"event_aware_{index}",
            "config": config,
            "samples": metrics.get("samples"),
            "avg_trade_return_pct": metrics.get("avg_trade_return_pct"),
            "profit_factor": metrics.get("profit_factor"),
            "win_rate_pct": metrics.get("win_rate_pct"),
            "stop_hit_rate_pct": metrics.get("stop_hit_rate_pct"),
            "quality_label": metrics.get("quality_label"),
        }
        row["score"] = score_setup_config_result({**row, "coverage_pct": _round((len(event_rows) / max(1, len(samples))) * 100, 2)}, min_signals=min_signals)
        results.append(row)
    if events and not any(int(row.get("samples") or 0) for row in results):
        warnings.append("no event-linked samples found across sweep configs; event history may be too sparse or too recent")
    results = _rank(results)
    best = results[0] if results else None
    return {
        "ok": True,
        "mode": "event_aware_setup_sweep",
        "summary": {
            "base_samples": len(samples),
            "tickers_used": len(tickers_used),
            "events_used": len(events),
            "configs_tested": len(results),
            "best_config_id": best.get("config_id") if best else None,
            "best_quality_label": best.get("quality_label") if best else None,
            "policy": policy,
            "warnings": warnings,
        },
        "best_configs": results[:10],
        "results": results,
        "limitations": [
            "Bounded event-aware parameter sweep for research only.",
            "Historical event coverage can dominate results.",
            "Proxy backtest on daily candles with simplified costs.",
        ],
    }
