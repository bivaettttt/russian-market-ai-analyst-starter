from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.consumer_signals import _round, _to_float
from app.services.event_aware_setup_research import build_event_aware_samples
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID
from app.services.setup_family_research import classify_setup_family_quality


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


def event_aware_combo_key(row: dict[str, Any], *, detailed: bool = True) -> str:
    setup = str(row.get("setup_family") or "event_only")
    family = str(row.get("event_family") or "none")
    if not detailed:
        return f"{setup}+{family}"
    direction = str(row.get("event_direction") or "none")
    confirmation = str(row.get("event_confirmation") or "none")
    return f"{setup}+{family}+{direction}+{confirmation}"


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )
    return {
        "samples": len(rows),
        "avg_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "profit_factor": pnl.get("profit_factor"),
        "win_rate_pct": pnl.get("win_rate_pct"),
        "stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
        "target_hit_rate_pct": pnl.get("target_hit_rate_pct"),
        "timeout_rate_pct": pnl.get("timeout_rate_pct"),
    }


def _delta(selected: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "avg_trade_return_delta_pct": _round((_to_float(selected.get("avg_trade_return_pct")) or 0.0) - (_to_float(baseline.get("avg_trade_return_pct")) or 0.0), 2),
        "profit_factor_delta": _round((_to_float(selected.get("profit_factor")) or 0.0) - (_to_float(baseline.get("profit_factor")) or 0.0), 3),
        "win_rate_delta_pct": _round((_to_float(selected.get("win_rate_pct")) or 0.0) - (_to_float(baseline.get("win_rate_pct")) or 0.0), 2),
        "stop_hit_delta_pct": _round((_to_float(selected.get("stop_hit_rate_pct")) or 0.0) - (_to_float(baseline.get("stop_hit_rate_pct")) or 0.0), 2),
    }


def concentration_risk(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {
            "top_ticker_share_pct": 0.0,
            "top_event_share_pct": 0.0,
            "top_year_share_pct": 0.0,
            "warnings": ["no selected samples"],
        }
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


def _combo_score(metrics: dict[str, Any], rows: list[dict[str, Any]]) -> float:
    avg = _to_float(metrics.get("avg_trade_return_pct")) or 0.0
    pf = _to_float(metrics.get("profit_factor")) or 0.0
    win = _to_float(metrics.get("win_rate_pct")) or 0.0
    stop = _to_float(metrics.get("stop_hit_rate_pct")) or 0.0
    concentration = concentration_risk(rows)
    penalty = 0.0
    if concentration.get("top_ticker_share_pct", 0) > 50:
        penalty += 12
    if concentration.get("top_event_share_pct", 0) > 50:
        penalty += 12
    if concentration.get("top_year_share_pct", 0) > 70:
        penalty += 12
    score = avg * 25 + max(0.0, pf - 1.0) * 35 + win * 0.2 - stop * 0.2 - penalty
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def select_top_train_combos(
    rows: list[dict[str, Any]],
    *,
    min_signals: int,
    top_k: int,
    detailed: bool = True,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("event_family") and row.get("setup_family"):
            groups[event_aware_combo_key(row, detailed=detailed)].append(row)
    selected: list[dict[str, Any]] = []
    for key, items in groups.items():
        if len(items) < min_signals:
            continue
        metrics = _metrics(items)
        quality = classify_setup_family_quality(
            samples=len(items),
            profit_factor=metrics.get("profit_factor"),
            avg_trade_return_pct=metrics.get("avg_trade_return_pct"),
            min_signals=min_signals,
        )
        if quality == "unstable":
            continue
        score = _combo_score(metrics, items)
        selected.append(
            {
                "combo_key": key,
                "train_samples": len(items),
                "train_avg_trade_return_pct": metrics.get("avg_trade_return_pct"),
                "train_profit_factor": metrics.get("profit_factor"),
                "train_win_rate_pct": metrics.get("win_rate_pct"),
                "train_stop_hit_rate_pct": metrics.get("stop_hit_rate_pct"),
                "train_score": score,
                "train_quality_label": quality,
            }
        )
    selected.sort(
        key=lambda row: (
            _to_float(row.get("train_score")) or -999,
            _to_float(row.get("train_profit_factor")) or -999,
            _to_float(row.get("train_avg_trade_return_pct")) or -999,
            int(row.get("train_samples") or 0),
        ),
        reverse=True,
    )
    return selected[:top_k]


def create_walk_forward_folds(
    rows: list[dict[str, Any]],
    *,
    folds: int,
    train_ratio: float,
    min_train_samples: int,
    min_test_samples: int,
) -> list[dict[str, Any]]:
    dated = [(row, _as_date(row.get("date"))) for row in rows if _as_date(row.get("date")) is not None]
    dated.sort(key=lambda item: (item[1], str(item[0].get("ticker") or "")))
    sorted_rows = [item[0] for item in dated]
    n = len(sorted_rows)
    result: list[dict[str, Any]] = []
    if n < min_train_samples + min_test_samples:
        return result
    base_train_end = max(min_train_samples, int(n * train_ratio))
    remaining = n - base_train_end
    if remaining < min_test_samples:
        return result
    test_window = max(min_test_samples, remaining // folds)
    for fold in range(1, folds + 1):
        train_end = base_train_end + (fold - 1) * test_window
        test_end = n if fold == folds else min(n, train_end + test_window)
        if train_end < min_train_samples or test_end - train_end < min_test_samples:
            continue
        train_rows = sorted_rows[:train_end]
        test_rows = sorted_rows[train_end:test_end]
        result.append({"fold": fold, "train_rows": train_rows, "test_rows": test_rows})
    return result


def _period(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [_as_date(row.get("date")) for row in rows if _as_date(row.get("date")) is not None]
    return {
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "samples": len(rows),
    }


def _fold_quality(metrics: dict[str, Any], concentration: dict[str, Any], *, min_signals: int) -> str:
    samples = int(metrics.get("samples") or 0)
    if samples < min_signals or concentration.get("warnings"):
        return "unstable"
    pf = _to_float(metrics.get("profit_factor")) or 0.0
    avg = _to_float(metrics.get("avg_trade_return_pct")) or 0.0
    if pf >= 1.10 and avg > 0:
        return "good"
    if pf >= 1.02 and avg >= 0:
        return "medium"
    return "weak"


def recommendation_from_summary(summary: dict[str, Any], *, concentration_warning: bool) -> str:
    if int(summary.get("event_samples") or 0) < 50 or int(summary.get("folds_completed") or 0) < 2:
        return "needs_more_event_data"
    pf = _to_float(summary.get("avg_test_selected_profit_factor")) or 0.0
    avg = _to_float(summary.get("avg_test_selected_return_pct")) or 0.0
    completed = int(summary.get("folds_completed") or 0)
    positive = int(summary.get("positive_folds") or 0)
    if completed >= 3 and positive >= min(3, completed) and pf >= 1.10 and avg > 0 and not concentration_warning:
        return "promising_event_edge"
    if pf >= 1.02 and avg >= 0 and positive > 0:
        return "research_only"
    return "reject"


def build_event_aware_walk_forward(
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
    min_signals: int = 10,
    top_k_combos: int = 5,
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
    rows = list(sample_data.get("samples") or [])
    event_rows = [row for row in rows if row.get("event_family")]
    confirmed_rows = [row for row in rows if row.get("event_confirmation") == "confirmed"]
    warnings = list(sample_data.get("warnings") or [])
    fold_specs = create_walk_forward_folds(
        event_rows,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    fold_results: list[dict[str, Any]] = []
    selected_frequency: dict[str, dict[str, Any]] = {}
    for spec in fold_specs:
        train_rows = spec["train_rows"]
        test_rows = spec["test_rows"]
        selected = select_top_train_combos(train_rows, min_signals=min_signals, top_k=top_k_combos, detailed=True)
        fold_warnings: list[str] = []
        if not selected:
            selected = select_top_train_combos(train_rows, min_signals=min_signals, top_k=top_k_combos, detailed=False)
            if selected:
                fold_warnings.append("used simplified combo key because detailed train combos were too sparse")
        selected_keys = {row["combo_key"] for row in selected}
        use_detailed = not any("simplified" in item for item in fold_warnings)
        test_selected = [
            row
            for row in test_rows
            if event_aware_combo_key(row, detailed=use_detailed) in selected_keys
        ]
        selected_metrics = _metrics(test_selected)
        baseline_metrics = _metrics(test_rows)
        confirmed_metrics = _metrics([row for row in test_rows if row.get("event_confirmation") == "confirmed"])
        setup_only_metrics = _metrics([row for row in test_rows if row.get("sample_type") == "setup_only"])
        concentration = concentration_risk(test_selected)
        fold_quality = _fold_quality(selected_metrics, concentration, min_signals=min_signals)
        for combo in selected:
            key = combo["combo_key"]
            bucket = selected_frequency.setdefault(
                key,
                {"combo_key": key, "selected_folds": 0, "train_scores": [], "test_returns": [], "test_pfs": []},
            )
            combo_test = [row for row in test_rows if event_aware_combo_key(row, detailed=use_detailed) == key]
            combo_metrics = _metrics(combo_test)
            bucket["selected_folds"] += 1
            bucket["train_scores"].append(_to_float(combo.get("train_score")) or 0.0)
            if combo_metrics.get("avg_trade_return_pct") is not None:
                bucket["test_returns"].append(_to_float(combo_metrics.get("avg_trade_return_pct")) or 0.0)
            if combo_metrics.get("profit_factor") is not None:
                bucket["test_pfs"].append(_to_float(combo_metrics.get("profit_factor")) or 0.0)
        fold_results.append(
            {
                "fold": spec["fold"],
                "train_period": _period(train_rows),
                "test_period": _period(test_rows),
                "selected_combos": selected,
                "test_selected_metrics": selected_metrics,
                "test_baseline_metrics": baseline_metrics,
                "test_confirmed_metrics": confirmed_metrics,
                "test_setup_only_metrics": setup_only_metrics,
                "delta_vs_baseline": _delta(selected_metrics, baseline_metrics),
                "concentration": concentration,
                "quality_label": fold_quality,
                "warnings": fold_warnings + list(concentration.get("warnings") or []),
            }
        )
    completed = len(fold_results)
    selected_returns = [_to_float((fold.get("test_selected_metrics") or {}).get("avg_trade_return_pct")) for fold in fold_results]
    selected_pfs = [_to_float((fold.get("test_selected_metrics") or {}).get("profit_factor")) for fold in fold_results]
    selected_wins = [_to_float((fold.get("test_selected_metrics") or {}).get("win_rate_pct")) for fold in fold_results]
    selected_stops = [_to_float((fold.get("test_selected_metrics") or {}).get("stop_hit_rate_pct")) for fold in fold_results]
    deltas_return = [_to_float((fold.get("delta_vs_baseline") or {}).get("avg_trade_return_delta_pct")) for fold in fold_results]
    deltas_pf = [_to_float((fold.get("delta_vs_baseline") or {}).get("profit_factor_delta")) for fold in fold_results]
    positive_folds = sum(1 for fold in fold_results if (_to_float((fold.get("test_selected_metrics") or {}).get("avg_trade_return_pct")) or 0.0) > 0)
    negative_folds = completed - positive_folds
    concentration_warning = any((fold.get("concentration") or {}).get("warnings") for fold in fold_results)
    combo_frequency = [
        {
            "combo_key": key,
            "selected_folds": item["selected_folds"],
            "avg_train_score": _round(mean(item["train_scores"]), 2) if item["train_scores"] else None,
            "avg_test_return_pct": _round(mean(item["test_returns"]), 2) if item["test_returns"] else None,
            "avg_test_profit_factor": _round(mean(item["test_pfs"]), 3) if item["test_pfs"] else None,
        }
        for key, item in selected_frequency.items()
    ]
    combo_frequency.sort(key=lambda row: (int(row.get("selected_folds") or 0), _to_float(row.get("avg_train_score")) or -999), reverse=True)
    summary = {
        "samples": len(rows),
        "event_samples": len(event_rows),
        "confirmed_samples": len(confirmed_rows),
        "folds_requested": folds,
        "folds_completed": completed,
        "top_k_combos": top_k_combos,
        "avg_test_selected_return_pct": _round(mean([x for x in selected_returns if x is not None]), 2) if any(x is not None for x in selected_returns) else None,
        "avg_test_selected_profit_factor": _round(mean([x for x in selected_pfs if x is not None]), 3) if any(x is not None for x in selected_pfs) else None,
        "avg_test_selected_win_rate_pct": _round(mean([x for x in selected_wins if x is not None]), 2) if any(x is not None for x in selected_wins) else None,
        "avg_test_selected_stop_hit_rate_pct": _round(mean([x for x in selected_stops if x is not None]), 2) if any(x is not None for x in selected_stops) else None,
        "avg_delta_vs_baseline_return_pct": _round(mean([x for x in deltas_return if x is not None]), 2) if any(x is not None for x in deltas_return) else None,
        "avg_delta_vs_baseline_profit_factor": _round(mean([x for x in deltas_pf if x is not None]), 3) if any(x is not None for x in deltas_pf) else None,
        "positive_folds": positive_folds,
        "negative_folds": negative_folds,
        "stable_positive_rate_pct": _round(positive_folds / completed * 100, 2) if completed else 0.0,
        "best_overall_combos": combo_frequency[:10],
        "warnings": warnings,
    }
    summary["recommendation"] = recommendation_from_summary(summary, concentration_warning=concentration_warning)
    if not fold_results:
        warnings.append("not enough event samples to build requested walk-forward folds")
    return {
        "ok": True,
        "mode": "event_aware_walk_forward",
        "summary": summary,
        "folds": fold_results,
        "selected_combo_frequency": combo_frequency,
        "best_combos": combo_frequency[:10],
        "limitations": [
            "Train folds select event/setup combinations only from past samples; future test samples are not used for selection.",
            "Historical events include curated seed data and require source-based expansion before production use.",
            "Proxy backtest uses daily candles with simplified target/stop ordering and costs.",
            "This is research-only validation; production consumer logic is unchanged.",
        ],
    }
