from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db

AIReportHTMLResponse = HTMLResponse

router = APIRouter()


# --- ML probability engine ---

from app.services.ml_probability_engine import get_ml_probability_status
from app.services.ml_probability_evaluation import evaluate_ml_probability_model
from app.services.ml_model_report import build_ml_model_report
from app.services.ml_model_report_page_html import build_ml_model_report_page_html
from app.services.ml_v2_dataset import build_ml_v2_trade_dataset
from app.services.ml_v2_evaluation import evaluate_ml_v2_trade_model
from app.services.ml_v2_gate_impact_evaluation import (
    build_ml_v2_gate_impact_evaluation,
    parse_gate_impact_thresholds,
    parse_gate_modes,
)
from app.services.ml_v2_gate_impact_page_html import build_ml_v2_gate_impact_page_html
from app.services.ml_v2_gate_walk_forward import (
    build_ml_v2_gate_walk_forward,
    parse_gate_walk_forward_modes,
    parse_gate_walk_forward_thresholds,
)
from app.services.ml_v2_gate_walk_forward_page_html import build_ml_v2_gate_walk_forward_page_html
from app.services.ml_v2_high_confidence_page_html import build_ml_v2_high_confidence_page_html
from app.services.ml_v2_high_confidence_validation import build_ml_v2_high_confidence_validation, parse_thresholds
from app.services.ml_v2_report_page_html import build_ml_v2_report_page_html
from app.services.ml_v3_consumer_candidate_dataset import build_ml_v3_consumer_candidate_dataset
from app.services.ml_v3_consumer_candidate_evaluation import (
    build_ml_v3_consumer_candidate_walk_forward,
    evaluate_ml_v3_consumer_candidate_model,
    parse_ml_v3_thresholds,
)
from app.services.ml_v3_consumer_candidate_page_html import build_ml_v3_consumer_candidate_page_html
from app.services.event_aware_setup_page_html import build_event_aware_setup_page_html
from app.services.event_aware_setup_research import (
    build_event_aware_setup_research,
    build_event_aware_setup_sweep,
    build_event_coverage_diagnostics,
)
from app.services.event_aware_dual_side_page_html import build_event_aware_dual_side_page_html
from app.services.event_aware_dual_side_research import (
    build_event_aware_dual_side_research,
    build_event_aware_dual_side_walk_forward,
)
from app.services.event_aware_rule_search import build_event_aware_rule_search
from app.services.event_aware_rule_search_page_html import build_event_aware_rule_search_page_html
from app.services.event_aware_rule_stability import build_event_aware_rule_stability_diagnostics
from app.services.event_aware_rule_stability_page_html import build_event_aware_rule_stability_page_html
from app.services.event_aware_risk_overlay_conservative_calibration import (
    build_conservative_event_risk_overlay_calibration,
)
from app.services.event_aware_risk_overlay_conservative_page_html import (
    build_event_aware_risk_overlay_conservative_page_html,
)
from app.services.event_overlay_paper_snapshot import build_event_overlay_paper_snapshot
from app.services.event_overlay_paper_snapshot_page_html import build_event_overlay_paper_snapshot_page_html
from app.services.event_overlay_paper_tracking import (
    build_event_overlay_paper_dashboard,
    build_event_overlay_paper_dashboard_csv,
    build_event_overlay_paper_lifecycle_status,
    build_event_overlay_paper_snapshot_items_csv,
    build_event_overlay_paper_snapshots_csv,
    bulk_evaluate_ready_snapshots,
    create_conservative_overlay_paper_snapshot,
    delete_event_overlay_paper_snapshot,
    evaluate_event_overlay_paper_snapshot,
    get_event_overlay_paper_snapshot_detail,
    get_ready_to_evaluate_snapshots,
    list_event_overlay_paper_snapshots,
    run_conservative_overlay_daily_workflow,
)
from app.services.event_overlay_paper_tracking_page_html import build_event_overlay_paper_tracking_page_html
from app.services.event_overlay_quality_report import (
    build_conservative_overlay_data_health,
    build_conservative_overlay_notification_summary,
    build_conservative_overlay_quality_report,
    build_conservative_overlay_quality_report_csv,
)
from app.services.event_overlay_quality_report_page_html import build_event_overlay_quality_report_page_html
from app.services.market_daily_ops import build_daily_ops_status, run_market_daily_ops
from app.services.market_daily_ops_page_html import build_market_daily_ops_page_html
from app.services.market_data_refresh import build_market_data_freshness_status, refresh_market_data_daily
from app.services.market_refresh_report import (
    build_market_refresh_notification,
    build_market_refresh_report,
    build_market_refresh_report_csv,
)
from app.services.market_refresh_report_page_html import build_market_refresh_report_page_html
from app.services.live_paper_validation_start import (
    build_live_paper_validation_status,
    start_live_paper_validation_run,
)
from app.services.live_paper_validation_page_html import build_live_paper_validation_page_html
from app.services.event_aware_risk_overlay_backtest import (
    build_event_risk_overlay_backtest,
    parse_overlay_modes,
)
from app.services.event_aware_risk_overlay_page_html import build_event_aware_risk_overlay_page_html
from app.services.event_aware_risk_overlay_walk_forward import build_event_risk_overlay_walk_forward
from app.services.event_aware_risk_overlay_walk_forward_page_html import (
    build_event_aware_risk_overlay_walk_forward_page_html,
)
from app.services.event_aware_walk_forward import build_event_aware_walk_forward
from app.services.event_aware_walk_forward_page_html import build_event_aware_walk_forward_page_html
from app.services.historical_event_bootstrap import DEFAULT_SEED_PATH
from app.services.setup_family_research import build_setup_family_parameter_sweep, build_setup_family_research
from app.services.setup_family_research_page_html import build_setup_family_research_page_html


@router.get("/signals/ml/status")
def market_signals_ml_status():
    return get_ml_probability_status()


@router.get("/signals/ml/evaluation")
def market_signals_ml_evaluation(
    thresholds: str = Query("0.30,0.35,0.40,0.45,0.50,0.55,0.60"),
    max_samples: int | None = Query(None, ge=1000, le=100000),
    db: Session = Depends(get_db),
):
    threshold_values = [
        float(item.strip())
        for item in thresholds.split(",")
        if item.strip()
    ]

    return evaluate_ml_probability_model(
        db=db,
        thresholds=threshold_values,
        max_samples=max_samples,
    )




@router.get("/signals/ml/report")
def market_signals_ml_report(
    thresholds: str = Query("0.25,0.30,0.35,0.40,0.45,0.50"),
    max_samples: int | None = Query(12000, ge=1000, le=100000),
    min_signals: int = Query(30, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    threshold_values = [
        float(item.strip())
        for item in thresholds.split(",")
        if item.strip()
    ]

    return build_ml_model_report(
        db=db,
        thresholds=threshold_values,
        max_samples=max_samples,
        min_signals=min_signals,
    )




@router.get("/signals/ml/report-page", response_class=AIReportHTMLResponse)
def market_signals_ml_report_page():
    return build_ml_model_report_page_html()


@router.get("/signals/ml-v2/dataset-summary")
def market_signals_ml_v2_dataset_summary(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    dataset = build_ml_v2_trade_dataset(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    return {
        "ok": dataset.get("ok"),
        "mode": dataset.get("mode"),
        "feature_set": dataset.get("feature_set"),
        "feature_count": len(dataset.get("feature_names") or []),
        "feature_names": dataset.get("feature_names") or [],
        "summary": dataset.get("summary") or {},
        "warnings": dataset.get("warnings") or [],
    }


@router.get("/signals/ml-v2/evaluation")
def market_signals_ml_v2_evaluation(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    label: str = Query("positive_trade_return"),
    test_size: float = Query(0.25, ge=0.1, le=0.5),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    return evaluate_ml_v2_trade_model(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        label=label,
        test_size=test_size,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@router.get("/signals/ml-v2/report-page", response_class=AIReportHTMLResponse)
def market_signals_ml_v2_report_page():
    return build_ml_v2_report_page_html()


@router.get("/signals/ml-v2/high-confidence-validation")
def market_signals_ml_v2_high_confidence_validation(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=300, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    label: str = Query("positive_trade_return"),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(500, ge=100, le=10000),
    min_test_samples: int = Query(150, ge=50, le=5000),
    thresholds: str | None = Query(None),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    return build_ml_v2_high_confidence_validation(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        label=label,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        thresholds=parse_thresholds(thresholds),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@router.get("/signals/ml-v2/high-confidence-page", response_class=AIReportHTMLResponse)
def market_signals_ml_v2_high_confidence_page():
    return build_ml_v2_high_confidence_page_html()


@router.get("/signals/ml-v2/gate-impact")
def market_signals_ml_v2_gate_impact(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=300, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    thresholds: str | None = Query(None),
    gate_modes: str | None = Query(None),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(50, ge=10, le=5000),
    db: Session = Depends(get_db),
):
    return build_ml_v2_gate_impact_evaluation(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        thresholds=parse_gate_impact_thresholds(thresholds),
        gate_modes=parse_gate_modes(gate_modes),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_signals=min_signals,
    )


@router.get("/signals/ml-v2/gate-impact-page", response_class=AIReportHTMLResponse)
def market_signals_ml_v2_gate_impact_page():
    return build_ml_v2_gate_impact_page_html()


@router.get("/signals/ml-v2/gate-walk-forward")
def market_signals_ml_v2_gate_walk_forward(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=300, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    label: str = Query("positive_trade_return"),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(500, ge=100, le=10000),
    min_test_samples: int = Query(150, ge=50, le=5000),
    thresholds: str | None = Query(None),
    gate_modes: str | None = Query(None),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(50, ge=10, le=5000),
    db: Session = Depends(get_db),
):
    return build_ml_v2_gate_walk_forward(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        label=label,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        thresholds=parse_gate_walk_forward_thresholds(thresholds),
        gate_modes=parse_gate_walk_forward_modes(gate_modes),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_signals=min_signals,
    )


@router.get("/signals/ml-v2/gate-walk-forward-page", response_class=AIReportHTMLResponse)
def market_signals_ml_v2_gate_walk_forward_page():
    return build_ml_v2_gate_walk_forward_page_html()


@router.get("/signals/ml-v3/consumer-candidate/dataset-summary")
def market_signals_ml_v3_consumer_candidate_dataset_summary(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_watch_candidates: bool = Query(False),
    db: Session = Depends(get_db),
):
    dataset = build_ml_v3_consumer_candidate_dataset(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_watch_candidates=include_watch_candidates,
    )
    return {
        "ok": dataset.get("ok"),
        "mode": dataset.get("mode"),
        "feature_set": dataset.get("feature_set"),
        "feature_count": dataset.get("feature_count"),
        "feature_names": dataset.get("feature_names") or [],
        "summary": dataset.get("summary") or {},
        "warnings": dataset.get("warnings") or [],
        "limitations": dataset.get("limitations") or [],
    }


@router.get("/signals/ml-v3/consumer-candidate/evaluation")
def market_signals_ml_v3_consumer_candidate_evaluation(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    label: str = Query("positive_trade_return"),
    test_size: float = Query(0.25, ge=0.1, le=0.5),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_watch_candidates: bool = Query(False),
    db: Session = Depends(get_db),
):
    return evaluate_ml_v3_consumer_candidate_model(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        label=label,
        test_size=test_size,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_watch_candidates=include_watch_candidates,
    )


@router.get("/signals/ml-v3/consumer-candidate/walk-forward")
def market_signals_ml_v3_consumer_candidate_walk_forward(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    label: str = Query("positive_trade_return"),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(300, ge=30, le=10000),
    min_test_samples: int = Query(100, ge=20, le=5000),
    thresholds: str | None = Query(None),
    gate_modes: str | None = Query(None),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(30, ge=10, le=5000),
    include_watch_candidates: bool = Query(False),
    db: Session = Depends(get_db),
):
    return build_ml_v3_consumer_candidate_walk_forward(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        label=label,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        thresholds=parse_ml_v3_thresholds(thresholds),
        gate_modes=parse_gate_modes(gate_modes),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_signals=min_signals,
        include_watch_candidates=include_watch_candidates,
    )


@router.get("/signals/ml-v3/consumer-candidate/page", response_class=AIReportHTMLResponse)
def market_signals_ml_v3_consumer_candidate_page():
    return build_ml_v3_consumer_candidate_page_html()


@router.get("/signals/setup-family/research")
def market_signals_setup_family_research(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(30, ge=5, le=5000),
    max_setups: int = Query(100, ge=10, le=1000),
    db: Session = Depends(get_db),
):
    return build_setup_family_research(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_signals=min_signals,
        max_setups=max_setups,
    )


@router.get("/signals/setup-family/sweep")
def market_signals_setup_family_sweep(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    setup_family: str | None = Query(None),
    max_configs: int = Query(60, ge=5, le=300),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(30, ge=5, le=5000),
    db: Session = Depends(get_db),
):
    return build_setup_family_parameter_sweep(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        setup_family=setup_family,
        max_configs=max_configs,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_signals=min_signals,
    )


@router.get("/signals/setup-family/research-page", response_class=AIReportHTMLResponse)
def market_signals_setup_family_research_page():
    return build_setup_family_research_page_html()


@router.get("/signals/event-aware/research")
def market_signals_event_aware_setup_research(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(5000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(20, ge=1, le=5000),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_event_aware_setup_research(
        db=db,
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
        min_signals=min_signals,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/event-aware/sweep")
def market_signals_event_aware_setup_sweep(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    max_events: int = Query(5000, ge=0, le=50000),
    max_configs: int = Query(60, ge=1, le=300),
    min_signals: int = Query(20, ge=1, le=5000),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    return build_event_aware_setup_sweep(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        max_configs=max_configs,
        min_signals=min_signals,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@router.get("/signals/event-aware/walk-forward")
def market_signals_event_aware_walk_forward(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(100, ge=20, le=5000),
    min_test_samples: int = Query(50, ge=10, le=5000),
    min_signals: int = Query(10, ge=1, le=1000),
    top_k_combos: int = Query(5, ge=1, le=30),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_event_aware_walk_forward(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        min_signals=min_signals,
        top_k_combos=top_k_combos,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/event-aware/rule-search")
def market_signals_event_aware_rule_search(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(100, ge=20, le=5000),
    min_test_samples: int = Query(50, ge=10, le=5000),
    min_signals: int = Query(20, ge=1, le=1000),
    max_rules: int = Query(120, ge=10, le=500),
    top_k_rules: int = Query(5, ge=1, le=30),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_event_aware_rule_search(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        min_signals=min_signals,
        max_rules=max_rules,
        top_k_rules=top_k_rules,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/event-aware/dual-side-research")
def market_signals_event_aware_dual_side_research(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    min_signals: int = Query(20, ge=1, le=1000),
    max_rules: int = Query(120, ge=10, le=500),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_event_aware_dual_side_research(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        min_signals=min_signals,
        max_rules=max_rules,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/event-aware/dual-side-walk-forward")
def market_signals_event_aware_dual_side_walk_forward(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(100, ge=20, le=5000),
    min_test_samples: int = Query(50, ge=10, le=5000),
    min_signals: int = Query(20, ge=1, le=1000),
    max_rules: int = Query(120, ge=10, le=500),
    top_k_rules: int = Query(5, ge=1, le=30),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_event_aware_dual_side_walk_forward(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        min_signals=min_signals,
        max_rules=max_rules,
        top_k_rules=top_k_rules,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/event-aware/rule-stability")
def market_signals_event_aware_rule_stability(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    min_signals: int = Query(20, ge=1, le=1000),
    max_rules: int = Query(120, ge=10, le=500),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_event_aware_rule_stability_diagnostics(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        min_signals=min_signals,
        max_rules=max_rules,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/event-aware/risk-overlay-backtest")
def market_signals_event_aware_risk_overlay_backtest(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    overlay_modes: str | None = Query(None),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return build_event_risk_overlay_backtest(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        overlay_modes=parse_overlay_modes(overlay_modes),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_signals=min_signals,
    )


@router.get("/signals/event-aware/risk-overlay-walk-forward")
def market_signals_event_aware_risk_overlay_walk_forward(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(100, ge=20, le=5000),
    min_test_samples: int = Query(50, ge=10, le=5000),
    max_configs: int = Query(60, ge=5, le=200),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_event_risk_overlay_walk_forward(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        max_configs=max_configs,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/event-aware/risk-overlay-conservative-calibration")
def market_signals_event_aware_risk_overlay_conservative_calibration(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=100, le=50000),
    max_events: int = Query(10000, ge=0, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    event_lookback_days: int = Query(7, ge=0, le=90),
    event_decay_days: int = Query(14, ge=1, le=180),
    folds: int = Query(4, ge=2, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(100, ge=20, le=5000),
    min_test_samples: int = Query(50, ge=10, le=5000),
    max_configs: int = Query(100, ge=5, le=300),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_avg_position_multiplier: float = Query(0.50, ge=0.1, le=1.0),
    max_exposure_reduction_pct: float = Query(50.0, ge=0, le=95),
    min_positive_pf_folds: int = Query(3, ge=1, le=8),
    include_global_events: bool = Query(True),
    include_ticker_events: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_conservative_event_risk_overlay_calibration(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        max_configs=max_configs,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_avg_position_multiplier=min_avg_position_multiplier,
        max_exposure_reduction_pct=max_exposure_reduction_pct,
        min_positive_pf_folds=min_positive_pf_folds,
        include_global_events=include_global_events,
        include_ticker_events=include_ticker_events,
    )


@router.get("/signals/events/coverage")
def market_signals_event_coverage(
    max_events: int = Query(5000, ge=0, le=50000),
    db: Session = Depends(get_db),
):
    return build_event_coverage_diagnostics(db=db, max_events=max_events)


@router.get("/signals/events/bootstrap-status")
def market_signals_event_bootstrap_status(
    max_events: int = Query(5000, ge=0, le=50000),
    db: Session = Depends(get_db),
):
    coverage = build_event_coverage_diagnostics(db=db, max_events=max_events)
    total_events = int((coverage.get("summary") or {}).get("total_events") or 0)
    recommendations = list(coverage.get("recommendations") or [])
    if total_events < 100:
        recommendations.append("Run the curated seed import before event-aware backtests.")
    return {
        "ok": True,
        "mode": "event_bootstrap_status",
        "coverage": coverage,
        "default_seed_path": str(DEFAULT_SEED_PATH),
        "suggested_commands": [
            "cd backend && python3 -m app.tasks.bootstrap_historical_events --dry-run",
            "cd backend && python3 -m app.tasks.bootstrap_historical_events",
        ],
        "recommendations": recommendations,
    }


@router.get("/signals/event-aware/research-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_setup_research_page():
    return build_event_aware_setup_page_html()


@router.get("/signals/event-aware/walk-forward-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_walk_forward_page():
    return build_event_aware_walk_forward_page_html()


@router.get("/signals/event-aware/rule-search-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_rule_search_page():
    return build_event_aware_rule_search_page_html()


@router.get("/signals/event-aware/dual-side-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_dual_side_page():
    return build_event_aware_dual_side_page_html()


@router.get("/signals/event-aware/rule-stability-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_rule_stability_page():
    return build_event_aware_rule_stability_page_html()


@router.get("/signals/event-aware/risk-overlay-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_risk_overlay_page():
    return build_event_aware_risk_overlay_page_html()


@router.get("/signals/event-aware/risk-overlay-walk-forward-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_risk_overlay_walk_forward_page():
    return build_event_aware_risk_overlay_walk_forward_page_html()


@router.get("/signals/event-aware/risk-overlay-conservative-page", response_class=AIReportHTMLResponse)
def market_signals_event_aware_risk_overlay_conservative_page():
    return build_event_aware_risk_overlay_conservative_page_html()


# --- Market signals dashboard ---

from app.services.signals_data import list_market_signals
from app.services.adaptive_trade_calibration import build_adaptive_trade_calibration
from app.services.adaptive_trade_calibration_page_html import build_adaptive_trade_calibration_page_html
from app.services.candidate_filter_calibration import build_candidate_filter_calibration
from app.services.candidate_filter_calibration_page_html import build_candidate_filter_calibration_page_html
from app.services.composite_rule_calibration import build_composite_rule_calibration
from app.services.composite_rule_calibration_page_html import build_composite_rule_calibration_page_html
from app.services.consumer_signals import (
    build_consumer_signal_for_ticker,
    compare_consumer_event_risk_overlay_snapshot,
    compare_consumer_ml_v2_gate_snapshot,
    list_consumer_signals,
)
from app.services.consumer_signal_backtest_audit import (
    build_consumer_signal_backtest_audit,
    build_consumer_threshold_sweep_audit,
    build_consumer_walk_forward_validation,
    build_regime_historical_evaluation,
)
from app.services.consumer_signal_backtest_audit_page_html import build_consumer_signal_backtest_audit_page_html
from app.services.consumer_threshold_sweep_page_html import build_consumer_threshold_sweep_page_html
from app.services.consumer_walk_forward_page_html import build_consumer_walk_forward_page_html
from app.services.data_coverage_diagnostics import build_data_coverage_diagnostics
from app.services.data_coverage_page_html import build_data_coverage_page_html
from app.services.expectancy_breakdown import build_expectancy_breakdown
from app.services.expectancy_breakdown_page_html import build_expectancy_breakdown_page_html
from app.services.market_regime import build_market_regime
from app.services.ml_v2_consumer_gate_backtest import (
    build_ml_v2_consumer_gate_backtest,
    parse_ml_v2_consumer_gate_backtest_modes,
    parse_ml_v2_consumer_gate_backtest_thresholds,
)
from app.services.ml_v2_consumer_gate_backtest_page_html import build_ml_v2_consumer_gate_backtest_page_html
from app.services.moex_data_bootstrap import build_data_bootstrap_status
from app.services.regime_formula_calibration import build_regime_formula_calibration
from app.services.regime_formula_calibration_page_html import build_regime_formula_calibration_page_html
from app.services.regime_historical_evaluation_page_html import build_regime_historical_evaluation_page_html
from app.services.signals_page_html import build_signals_page_html


def _parse_number_list(
    value: str | None,
    *,
    item_type: type,
    min_value: float,
    max_value: float,
) -> list[int] | list[float] | None:
    if not value:
        return None

    parsed: list[int] | list[float] = []
    for raw_item in value.split(","):
        text = raw_item.strip()
        if not text:
            continue
        try:
            number = item_type(text)
        except Exception:
            continue
        if min_value <= float(number) <= max_value:
            parsed.append(number)

    return parsed or None



@router.get("/signals/consumer.json")
def consumer_signals_data_api(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=20, le=1000),
    action: str | None = Query(None),
    min_probability: float | None = Query(None, ge=0, le=100),
    q: str | None = Query(None),
    scenario: str = Query("all", description="all, long, downside или neutral"),
    news: str = Query("all", description="all, with_events, no_events, boost, penalty, veto или info_only"),
    use_ml_v2_research_gate: bool = Query(False),
    ml_v2_gate_threshold_pct: float = Query(55.0, ge=0, le=100),
    ml_v2_gate_mode: str = Query("diagnostic_only"),
    use_event_risk_overlay: bool = Query(False),
    event_risk_overlay_mode: str = Query("diagnostic_only"),
    use_conservative_event_overlay: bool = Query(False),
    conservative_event_overlay_mode: str = Query("soft_adjust"),
    db: Session = Depends(get_db),
):
    return list_consumer_signals(
        db=db,
        limit=limit,
        action=action,
        min_probability=min_probability,
        candles_limit=candles_limit,
        q=q,
        scenario=scenario,
        news=news,
        use_ml_v2_research_gate=use_ml_v2_research_gate,
        ml_v2_gate_threshold_pct=ml_v2_gate_threshold_pct,
        ml_v2_gate_mode=ml_v2_gate_mode,
        use_event_risk_overlay=use_event_risk_overlay,
        event_risk_overlay_mode=event_risk_overlay_mode,
        use_conservative_event_overlay=use_conservative_event_overlay,
        conservative_event_overlay_mode=conservative_event_overlay_mode,
    )


@router.get("/signals/consumer/ml-v2-gate-compare")
def consumer_ml_v2_gate_compare_api(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=20, le=1000),
    ml_v2_gate_threshold_pct: float = Query(55.0, ge=0, le=100),
    ml_v2_gate_mode: str = Query("soft_downgrade"),
    db: Session = Depends(get_db),
):
    return compare_consumer_ml_v2_gate_snapshot(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        ml_v2_gate_threshold_pct=ml_v2_gate_threshold_pct,
        ml_v2_gate_mode=ml_v2_gate_mode,
    )


@router.get("/signals/consumer/event-risk-overlay-compare")
def consumer_event_risk_overlay_compare_api(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=60, le=1000),
    event_risk_overlay_mode: str = Query("soft_adjust"),
    db: Session = Depends(get_db),
):
    return compare_consumer_event_risk_overlay_snapshot(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        event_risk_overlay_mode=event_risk_overlay_mode,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-snapshot")
def event_aware_conservative_overlay_paper_snapshot_api(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=60, le=1000),
    conservative_event_overlay_mode: str = Query("soft_adjust"),
    db: Session = Depends(get_db),
):
    return build_event_overlay_paper_snapshot(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        conservative_event_overlay_mode=conservative_event_overlay_mode,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-page", response_class=AIReportHTMLResponse)
def event_aware_conservative_overlay_paper_page():
    return build_event_overlay_paper_snapshot_page_html()


@router.post("/signals/event-aware/conservative-overlay-paper-snapshots")
def event_aware_conservative_overlay_paper_snapshot_create_api(
    name: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=60, le=1000),
    horizon_days: int = Query(20, ge=1, le=120),
    overlay_mode: str = Query("soft_adjust"),
    dedupe_same_day: bool = Query(True),
    db: Session = Depends(get_db),
):
    return create_conservative_overlay_paper_snapshot(
        db=db,
        name=name,
        limit=limit,
        candles_limit=candles_limit,
        horizon_days=horizon_days,
        overlay_mode=overlay_mode,
        dedupe_same_day=dedupe_same_day,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-snapshots")
def event_aware_conservative_overlay_paper_snapshots_list_api(
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return list_event_overlay_paper_snapshots(
        db=db,
        limit=limit,
        status=status,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-snapshots.csv")
def event_aware_conservative_overlay_paper_snapshots_csv_api(
    limit: int = Query(100, ge=1, le=1000),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    csv_text = build_event_overlay_paper_snapshots_csv(
        db=db,
        limit=limit,
        status=status,
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="conservative_overlay_paper_snapshots.csv"'},
    )


@router.get("/signals/event-aware/conservative-overlay-paper-snapshots/{snapshot_id}.csv")
def event_aware_conservative_overlay_paper_snapshot_detail_csv_api(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    csv_text = build_event_overlay_paper_snapshot_items_csv(
        db=db,
        snapshot_id=snapshot_id,
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="conservative_overlay_paper_snapshot_{snapshot_id}.csv"'},
    )


@router.get("/signals/event-aware/conservative-overlay-paper-snapshots/{snapshot_id}")
def event_aware_conservative_overlay_paper_snapshot_detail_api(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    return get_event_overlay_paper_snapshot_detail(
        db=db,
        snapshot_id=snapshot_id,
    )


@router.post("/signals/event-aware/conservative-overlay-paper-snapshots/{snapshot_id}/evaluate")
def event_aware_conservative_overlay_paper_snapshot_evaluate_api(
    snapshot_id: int,
    evaluation_date: str | None = Query(None),
    horizon_days: int | None = Query(None, ge=1, le=120),
    db: Session = Depends(get_db),
):
    return evaluate_event_overlay_paper_snapshot(
        db=db,
        snapshot_id=snapshot_id,
        evaluation_date=evaluation_date,
        horizon_days=horizon_days,
    )


@router.delete("/signals/event-aware/conservative-overlay-paper-snapshots/{snapshot_id}")
def event_aware_conservative_overlay_paper_snapshot_delete_api(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    return delete_event_overlay_paper_snapshot(
        db=db,
        snapshot_id=snapshot_id,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-dashboard")
def event_aware_conservative_overlay_paper_dashboard_api(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return build_event_overlay_paper_dashboard(
        db=db,
        limit=limit,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-dashboard.csv")
def event_aware_conservative_overlay_paper_dashboard_csv_api(
    db: Session = Depends(get_db),
):
    csv_text = build_event_overlay_paper_dashboard_csv(db=db)
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="conservative_overlay_paper_dashboard.csv"'},
    )


@router.get("/signals/event-aware/conservative-overlay-paper-lifecycle-status")
def event_aware_conservative_overlay_paper_lifecycle_status_api(
    as_of_date: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return build_event_overlay_paper_lifecycle_status(
        db=db,
        as_of_date=as_of_date,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-ready")
def event_aware_conservative_overlay_paper_ready_api(
    as_of_date: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return get_ready_to_evaluate_snapshots(
        db=db,
        as_of_date=as_of_date,
        limit=limit,
    )


@router.post("/signals/event-aware/conservative-overlay-paper-evaluate-ready")
def event_aware_conservative_overlay_paper_evaluate_ready_api(
    as_of_date: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return bulk_evaluate_ready_snapshots(
        db=db,
        as_of_date=as_of_date,
        limit=limit,
    )


@router.get("/signals/event-aware/conservative-overlay-paper-tracking-page", response_class=AIReportHTMLResponse)
def event_aware_conservative_overlay_paper_tracking_page():
    return build_event_overlay_paper_tracking_page_html()


@router.get("/signals/event-aware/conservative-overlay-quality-report")
def event_aware_conservative_overlay_quality_report_api(
    limit: int = Query(30, ge=1, le=200),
    include_open_snapshots: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_conservative_overlay_quality_report(
        db=db,
        limit=limit,
        include_open_snapshots=include_open_snapshots,
    )


@router.get("/signals/event-aware/conservative-overlay-quality-report-page", response_class=AIReportHTMLResponse)
def event_aware_conservative_overlay_quality_report_page():
    return build_event_overlay_quality_report_page_html()


@router.get("/signals/event-aware/conservative-overlay-notification-summary")
def event_aware_conservative_overlay_notification_summary_api(
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return build_conservative_overlay_notification_summary(
        db=db,
        limit=limit,
    )


@router.get("/signals/event-aware/conservative-overlay-data-health")
def event_aware_conservative_overlay_data_health_api(
    stale_days: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return build_conservative_overlay_data_health(
        db=db,
        stale_days=stale_days,
    )


@router.post("/signals/event-aware/conservative-overlay-daily-run")
def event_aware_conservative_overlay_daily_run_api(
    name: str = Query("daily"),
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=60, le=1000),
    horizon_days: int = Query(20, ge=1, le=120),
    evaluate_ready: bool = Query(True),
    dedupe_same_day: bool = Query(True),
    db: Session = Depends(get_db),
):
    return run_conservative_overlay_daily_workflow(
        db=db,
        name=name,
        limit=limit,
        candles_limit=candles_limit,
        horizon_days=horizon_days,
        evaluate_ready=evaluate_ready,
        dedupe_same_day=dedupe_same_day,
    )


@router.get("/signals/event-aware/conservative-overlay-quality-report.csv")
def event_aware_conservative_overlay_quality_report_csv_api(
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    csv_text = build_conservative_overlay_quality_report_csv(
        db=db,
        limit=limit,
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="conservative_overlay_quality_report.csv"'},
    )


@router.get("/signals/daily-ops/status")
def signals_daily_ops_status_api(
    stale_days: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return build_daily_ops_status(
        db=db,
        stale_days=stale_days,
    )


@router.get("/signals/daily-ops/market-data-freshness")
def signals_daily_ops_market_data_freshness_api(
    stale_days: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return build_market_data_freshness_status(
        db=db,
        stale_days=stale_days,
    )


@router.post("/signals/daily-ops/refresh-market-data")
def signals_daily_ops_refresh_market_data_api(
    max_tickers: int = Query(150, ge=1, le=500),
    days: int = Query(120, ge=10, le=1000),
    dry_run: bool = Query(False),
    force: bool = Query(False),
    retry_failed: bool = Query(False),
    max_retries: int = Query(1, ge=0, le=3),
    db: Session = Depends(get_db),
):
    return refresh_market_data_daily(
        db=db,
        max_tickers=max_tickers,
        days=days,
        dry_run=dry_run,
        force=force,
        retry_failed=retry_failed,
        max_retries=max_retries,
    )


@router.post("/signals/daily-ops/run")
def signals_daily_ops_run_api(
    name: str = Query("daily"),
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=60, le=1000),
    horizon_days: int = Query(20, ge=1, le=120),
    refresh_market_data: bool = Query(True),
    refresh_max_tickers: int = Query(150, ge=1, le=500),
    refresh_days: int = Query(120, ge=10, le=1000),
    evaluate_ready: bool = Query(True),
    dedupe_same_day: bool = Query(True),
    dry_run: bool = Query(False),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
):
    return run_market_daily_ops(
        db=db,
        name=name,
        limit=limit,
        candles_limit=candles_limit,
        horizon_days=horizon_days,
        refresh_market_data=refresh_market_data,
        refresh_max_tickers=refresh_max_tickers,
        refresh_days=refresh_days,
        evaluate_ready=evaluate_ready,
        dedupe_same_day=dedupe_same_day,
        dry_run=dry_run,
        force_refresh=force_refresh,
    )


@router.get("/signals/daily-ops/page", response_class=AIReportHTMLResponse)
def signals_daily_ops_page():
    return build_market_daily_ops_page_html()


@router.get("/signals/daily-ops/market-refresh-report")
def signals_daily_ops_market_refresh_report_api(
    stale_days: int = Query(3, ge=1, le=30),
    max_tickers: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return build_market_refresh_report(
        db=db,
        stale_days=stale_days,
        max_tickers=max_tickers,
    )


@router.get("/signals/daily-ops/market-refresh-notification")
def signals_daily_ops_market_refresh_notification_api(
    stale_days: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return build_market_refresh_notification(
        db=db,
        stale_days=stale_days,
    )


@router.get("/signals/daily-ops/market-refresh-report.csv")
def signals_daily_ops_market_refresh_report_csv_api(
    stale_days: int = Query(3, ge=1, le=30),
    max_tickers: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    csv_text = build_market_refresh_report_csv(
        db=db,
        stale_days=stale_days,
        max_tickers=max_tickers,
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="market_refresh_report.csv"'},
    )


@router.get("/signals/daily-ops/market-refresh-report-page", response_class=AIReportHTMLResponse)
def signals_daily_ops_market_refresh_report_page():
    return build_market_refresh_report_page_html()


@router.post("/signals/live-paper-validation/start")
def signals_live_paper_validation_start_api(
    name: str = Query("official-daily"),
    limit: int = Query(100, ge=1, le=500),
    horizon_days: int = Query(20, ge=1, le=120),
    refresh_market_data: bool = Query(True),
    refresh_max_tickers: int = Query(150, ge=1, le=500),
    refresh_days: int = Query(120, ge=10, le=1000),
    require_fresh_market_data: bool = Query(True),
    max_stale_days: int = Query(3, ge=1, le=30),
    evaluate_ready: bool = Query(True),
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
):
    return start_live_paper_validation_run(
        db=db,
        name=name,
        limit=limit,
        horizon_days=horizon_days,
        refresh_market_data=refresh_market_data,
        refresh_max_tickers=refresh_max_tickers,
        refresh_days=refresh_days,
        require_fresh_market_data=require_fresh_market_data,
        max_stale_days=max_stale_days,
        evaluate_ready=evaluate_ready,
        dry_run=dry_run,
    )


@router.get("/signals/live-paper-validation/status")
def signals_live_paper_validation_status_api(
    max_stale_days: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return build_live_paper_validation_status(
        db=db,
        max_stale_days=max_stale_days,
    )


@router.get("/signals/live-paper-validation/page", response_class=AIReportHTMLResponse)
def signals_live_paper_validation_page():
    return build_live_paper_validation_page_html()


@router.get("/signals/consumer/ml-v2-gate-backtest")
def consumer_ml_v2_gate_backtest_api(
    max_tickers: int = Query(120, ge=1, le=300),
    max_samples: int = Query(10000, ge=300, le=50000),
    min_history: int = Query(80, ge=30, le=250),
    horizon: int = Query(30, ge=5, le=90),
    policy_id: str = Query("atr_t1_5_s1_6_h30_rr0_8"),
    thresholds: str | None = Query(None),
    gate_modes: str | None = Query(None),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_signals: int = Query(50, ge=10, le=5000),
    use_leakage_safe_predictions: bool = Query(True),
    folds: int = Query(4, ge=2, le=8),
    db: Session = Depends(get_db),
):
    return build_ml_v2_consumer_gate_backtest(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        thresholds=parse_ml_v2_consumer_gate_backtest_thresholds(thresholds),
        gate_modes=parse_ml_v2_consumer_gate_backtest_modes(gate_modes),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_signals=min_signals,
        use_leakage_safe_predictions=use_leakage_safe_predictions,
        folds=folds,
    )


@router.get("/signals/consumer/ml-v2-gate-backtest-page", response_class=AIReportHTMLResponse)
def consumer_ml_v2_gate_backtest_page():
    return build_ml_v2_consumer_gate_backtest_page_html()


@router.get("/signals/market-regime")
def market_regime_api(
    lookback: int = Query(60, ge=20, le=250),
    max_tickers: int = Query(120, ge=20, le=500),
    db: Session = Depends(get_db),
):
    return build_market_regime(
        db=db,
        lookback=lookback,
        max_tickers=max_tickers,
    )


@router.get("/signals/data-coverage")
def signals_data_coverage_api(
    max_tickers: int = Query(500, ge=1, le=5000),
    min_history: int = Query(80, ge=10, le=500),
    horizon: int = Query(20, ge=1, le=250),
    candles_limit: int = Query(1000, ge=50, le=5000),
    include_examples: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_data_coverage_diagnostics(
        db=db,
        max_tickers=max_tickers,
        min_history=min_history,
        horizon=horizon,
        candles_limit=candles_limit,
        include_examples=include_examples,
    )


@router.get("/signals/data-coverage-page", response_class=AIReportHTMLResponse)
def signals_data_coverage_page():
    return build_data_coverage_page_html()


@router.get("/signals/data-bootstrap-status")
def signals_data_bootstrap_status_api(db: Session = Depends(get_db)):
    return build_data_bootstrap_status(db=db)


@router.get("/signals/consumer/backtest-audit")
def consumer_signal_backtest_audit_api(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(2000, ge=50, le=20000),
    horizon: int = Query(20, ge=5, le=90),
    target_pct: float = Query(0.05, ge=0.005, le=0.25),
    stop_pct: float = Query(0.03, ge=0.005, le=0.20),
    min_history: int = Query(80, ge=30, le=250),
    use_market_regime_filter: bool = Query(False),
    commission_bps: float = Query(0.0, ge=0, le=100),
    slippage_bps: float = Query(0.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    return build_consumer_signal_backtest_audit(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_history=min_history,
        use_market_regime_filter=use_market_regime_filter,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@router.get("/signals/consumer/backtest-audit-page", response_class=AIReportHTMLResponse)
def consumer_signal_backtest_audit_page():
    return build_consumer_signal_backtest_audit_page_html()


@router.get("/signals/consumer/expectancy-breakdown")
def consumer_expectancy_breakdown_api(
    max_tickers: int = Query(100, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    horizon: int = Query(20, ge=5, le=90),
    target_pct: float = Query(0.05, ge=0.005, le=0.25),
    stop_pct: float = Query(0.03, ge=0.005, le=0.20),
    min_history: int = Query(80, ge=30, le=250),
    commission_bps: float = Query(0.0, ge=0, le=100),
    slippage_bps: float = Query(0.0, ge=0, le=100),
    min_bucket_samples: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return build_expectancy_breakdown(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_history=min_history,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_bucket_samples=min_bucket_samples,
    )


@router.get("/signals/consumer/expectancy-breakdown-page", response_class=AIReportHTMLResponse)
def consumer_expectancy_breakdown_page():
    return build_expectancy_breakdown_page_html()


@router.get("/signals/consumer/candidate-filter-calibration")
def consumer_candidate_filter_calibration_api(
    max_tickers: int = Query(100, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    horizon: int = Query(30, ge=5, le=90),
    target_pct: float = Query(0.05, ge=0.005, le=0.25),
    stop_pct: float = Query(0.03, ge=0.005, le=0.20),
    min_history: int = Query(80, ge=30, le=250),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_bucket_samples: int = Query(20, ge=1, le=1000),
    max_filters: int = Query(80, ge=5, le=300),
    use_best_adaptive_policy: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_candidate_filter_calibration(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_history=min_history,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_bucket_samples=min_bucket_samples,
        max_filters=max_filters,
        use_best_adaptive_policy=use_best_adaptive_policy,
    )


@router.get("/signals/consumer/candidate-filter-calibration-page", response_class=AIReportHTMLResponse)
def consumer_candidate_filter_calibration_page():
    return build_candidate_filter_calibration_page_html()


@router.get("/signals/consumer/composite-rule-calibration")
def consumer_composite_rule_calibration_api(
    max_tickers: int = Query(100, ge=1, le=300),
    max_samples: int = Query(3000, ge=100, le=50000),
    max_rules: int = Query(120, ge=10, le=500),
    horizon: int = Query(30, ge=5, le=90),
    min_history: int = Query(80, ge=30, le=250),
    commission_bps: float = Query(10.0, ge=0, le=100),
    slippage_bps: float = Query(5.0, ge=0, le=100),
    min_trades: int = Query(50, ge=10, le=2000),
    use_best_adaptive_policy: bool = Query(True),
    db: Session = Depends(get_db),
):
    return build_composite_rule_calibration(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_rules=max_rules,
        horizon=horizon,
        min_history=min_history,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_trades=min_trades,
        use_best_adaptive_policy=use_best_adaptive_policy,
    )


@router.get("/signals/consumer/composite-rule-calibration-page", response_class=AIReportHTMLResponse)
def consumer_composite_rule_calibration_page():
    return build_composite_rule_calibration_page_html()


@router.get("/signals/consumer/threshold-sweep")
def consumer_threshold_sweep_audit_api(
    max_tickers: int = Query(60, ge=1, le=200),
    max_samples: int = Query(1500, ge=100, le=20000),
    min_signals: int = Query(20, ge=1, le=500),
    max_configs: int = Query(120, ge=10, le=500),
    horizons: str | None = Query(None),
    target_pcts: str | None = Query(None),
    stop_pcts: str | None = Query(None),
    min_probabilities: str | None = Query(None),
    min_ml_probabilities: str | None = Query(None),
    min_rr_values: str | None = Query(None),
    use_market_regime_filter: bool = Query(False),
    commission_bps: float = Query(0.0, ge=0, le=100),
    slippage_bps: float = Query(0.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    return build_consumer_threshold_sweep_audit(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizons=_parse_number_list(horizons, item_type=int, min_value=5, max_value=90),
        target_pcts=_parse_number_list(target_pcts, item_type=float, min_value=0.005, max_value=0.25),
        stop_pcts=_parse_number_list(stop_pcts, item_type=float, min_value=0.005, max_value=0.20),
        min_probabilities=_parse_number_list(min_probabilities, item_type=float, min_value=0, max_value=100),
        min_ml_probabilities=_parse_number_list(min_ml_probabilities, item_type=float, min_value=0, max_value=100),
        min_rr_values=_parse_number_list(min_rr_values, item_type=float, min_value=0.1, max_value=5.0),
        min_signals=min_signals,
        max_configs=max_configs,
        use_market_regime_filter=use_market_regime_filter,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@router.get("/signals/consumer/threshold-sweep-page", response_class=AIReportHTMLResponse)
def consumer_threshold_sweep_page():
    return build_consumer_threshold_sweep_page_html()


@router.get("/signals/consumer/walk-forward")
def consumer_walk_forward_validation_api(
    max_tickers: int = Query(60, ge=1, le=200),
    max_samples: int = Query(2000, ge=200, le=30000),
    max_configs: int = Query(80, ge=10, le=500),
    folds: int = Query(3, ge=1, le=8),
    train_ratio: float = Query(0.6, ge=0.4, le=0.85),
    min_train_samples: int = Query(200, ge=50, le=5000),
    min_test_samples: int = Query(80, ge=20, le=3000),
    min_signals: int = Query(20, ge=1, le=1000),
    horizons: str | None = Query(None),
    target_pcts: str | None = Query(None),
    stop_pcts: str | None = Query(None),
    min_probabilities: str | None = Query(None),
    min_ml_probabilities: str | None = Query(None),
    min_rr_values: str | None = Query(None),
    use_market_regime_filter: bool = Query(False),
    commission_bps: float = Query(0.0, ge=0, le=100),
    slippage_bps: float = Query(0.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    return build_consumer_walk_forward_validation(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_configs=max_configs,
        folds=folds,
        train_ratio=train_ratio,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
        horizons=_parse_number_list(horizons, item_type=int, min_value=5, max_value=90),
        target_pcts=_parse_number_list(target_pcts, item_type=float, min_value=0.005, max_value=0.25),
        stop_pcts=_parse_number_list(stop_pcts, item_type=float, min_value=0.005, max_value=0.20),
        min_probabilities=_parse_number_list(min_probabilities, item_type=float, min_value=0, max_value=100),
        min_ml_probabilities=_parse_number_list(min_ml_probabilities, item_type=float, min_value=0, max_value=100),
        min_rr_values=_parse_number_list(min_rr_values, item_type=float, min_value=0.1, max_value=5.0),
        min_signals=min_signals,
        use_market_regime_filter=use_market_regime_filter,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@router.get("/signals/consumer/walk-forward-page", response_class=AIReportHTMLResponse)
def consumer_walk_forward_page():
    return build_consumer_walk_forward_page_html()


@router.get("/signals/consumer/regime-historical-evaluation")
def consumer_regime_historical_evaluation_api(
    max_tickers: int = Query(60, ge=5, le=300),
    max_samples: int = Query(2000, ge=100, le=30000),
    horizon: int = Query(20, ge=5, le=90),
    target_pct: float = Query(0.05, ge=0.005, le=0.25),
    stop_pct: float = Query(0.03, ge=0.005, le=0.20),
    lookback: int = Query(60, ge=20, le=250),
    min_tickers: int = Query(20, ge=5, le=200),
    db: Session = Depends(get_db),
):
    return build_regime_historical_evaluation(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        lookback=lookback,
        min_tickers=min_tickers,
    )


@router.get("/signals/consumer/regime-historical-evaluation-page", response_class=AIReportHTMLResponse)
def consumer_regime_historical_evaluation_page():
    return build_regime_historical_evaluation_page_html()


@router.get("/signals/consumer/regime-formula-calibration")
def consumer_regime_formula_calibration_api(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(2000, ge=100, le=30000),
    lookback: int = Query(60, ge=20, le=250),
    horizon: int = Query(20, ge=5, le=90),
    target_pct: float = Query(0.05, ge=0.005, le=0.25),
    stop_pct: float = Query(0.03, ge=0.005, le=0.20),
    min_history: int = Query(80, ge=30, le=250),
    max_configs: int = Query(80, ge=10, le=300),
    min_signals_after_filter: int = Query(30, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return build_regime_formula_calibration(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        lookback=lookback,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_history=min_history,
        max_configs=max_configs,
        min_signals_after_filter=min_signals_after_filter,
    )


@router.get("/signals/consumer/regime-formula-calibration-page", response_class=AIReportHTMLResponse)
def consumer_regime_formula_calibration_page():
    return build_regime_formula_calibration_page_html()


@router.get("/signals/consumer/adaptive-trade-calibration")
def consumer_adaptive_trade_calibration_api(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(2000, ge=100, le=30000),
    max_policies: int = Query(80, ge=5, le=300),
    min_samples_per_policy: int = Query(30, ge=1, le=1000),
    min_history: int = Query(80, ge=30, le=250),
    commission_bps: float = Query(0.0, ge=0, le=100),
    slippage_bps: float = Query(0.0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    return build_adaptive_trade_calibration(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_policies=max_policies,
        min_samples_per_policy=min_samples_per_policy,
        min_history=min_history,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@router.get("/signals/consumer/adaptive-trade-calibration-page", response_class=AIReportHTMLResponse)
def consumer_adaptive_trade_calibration_page():
    return build_adaptive_trade_calibration_page_html()


@router.get("/signals/consumer/{ticker}.json")
def consumer_signal_ticker_api(
    ticker: str,
    candles_limit: int = Query(240, ge=20, le=1000),
    use_ml_v2_research_gate: bool = Query(False),
    ml_v2_gate_threshold_pct: float = Query(55.0, ge=0, le=100),
    ml_v2_gate_mode: str = Query("diagnostic_only"),
    use_event_risk_overlay: bool = Query(False),
    event_risk_overlay_mode: str = Query("diagnostic_only"),
    use_conservative_event_overlay: bool = Query(False),
    conservative_event_overlay_mode: str = Query("soft_adjust"),
    db: Session = Depends(get_db),
):
    return build_consumer_signal_for_ticker(
        db=db,
        ticker=ticker,
        candles_limit=candles_limit,
        use_ml_v2_research_gate=use_ml_v2_research_gate,
        ml_v2_gate_threshold_pct=ml_v2_gate_threshold_pct,
        ml_v2_gate_mode=ml_v2_gate_mode,
        use_event_risk_overlay=use_event_risk_overlay,
        event_risk_overlay_mode=event_risk_overlay_mode,
        use_conservative_event_overlay=use_conservative_event_overlay,
        conservative_event_overlay_mode=conservative_event_overlay_mode,
    )


@router.get("/signals/data")
def market_signals_data_api(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(120, ge=20, le=1000),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return list_market_signals(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        action=action,
        model_version=model_version,
    )


@router.get("/signals", response_class=AIReportHTMLResponse)
def market_signals_page():
    return build_signals_page_html()




# --- Signal snapshots history ---

from app.services.signals_history import create_signal_snapshots, list_signal_snapshots
from app.services.signals_history_page_html import build_signals_history_page_html


@router.post("/signals/snapshot")
def market_signals_snapshot_create(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(120, ge=20, le=1000),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return create_signal_snapshots(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        action=action,
        model_version=model_version,
    )


@router.get("/signals/history.json")
def market_signals_history_json(
    limit: int = Query(100, ge=1, le=1000),
    ticker: str | None = Query(None),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return list_signal_snapshots(
        db=db,
        limit=limit,
        ticker=ticker,
        action=action,
        model_version=model_version,
    )


@router.get("/signals/history", response_class=AIReportHTMLResponse)
def market_signals_history_page():
    return build_signals_history_page_html()




# --- Signal evaluation ---

from app.services.signals_evaluation import list_signal_evaluations
from app.services.signals_evaluation_page_html import build_signals_evaluation_page_html


@router.get("/signals/evaluation.json")
def market_signals_evaluation_json(
    limit: int = Query(100, ge=1, le=1000),
    ticker: str | None = Query(None),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    future_limit: int = Query(60, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_signal_evaluations(
        db=db,
        limit=limit,
        ticker=ticker,
        action=action,
        model_version=model_version,
        future_limit=future_limit,
    )


@router.get("/signals/evaluation", response_class=AIReportHTMLResponse)
def market_signals_evaluation_page():
    return build_signals_evaluation_page_html()




# --- Signal backtest ---

from app.services.signals_backtest import run_signals_backtest
from app.services.signals_backtest_page_html import build_signals_backtest_page_html


@router.get("/signals/backtest.json")
def market_signals_backtest_json(
    tickers: str | None = Query(None),
    limit: int = Query(300, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=500),
    future_limit: int = Query(20, ge=1, le=250),
    max_points_per_ticker: int = Query(25, ge=1, le=500),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return run_signals_backtest(
        db=db,
        tickers=tickers,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
        model_version=model_version,
    )



@router.get("/signals/backtest.csv")
def market_signals_backtest_csv(
    tickers: str = Query("SBER,GAZP,LKOH,PLZL"),
    limit: int = Query(150, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=300),
    future_limit: int = Query(20, ge=1, le=120),
    max_points_per_ticker: int = Query(25, ge=1, le=300),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    import csv
    import io

    data = run_signals_backtest(
        db=db,
        tickers=tickers,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
        model_version=model_version,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id",
        "trade_date",
        "ticker",
            "model_version",
        "price",
        "change_pct",
        "action",
        "label",
        "confidence_pct",
        "risk_level",
        "entry_price",
        "target_price",
        "stop_loss",
        "horizon",
        "evaluation_status",
        "evaluation_label",
        "result_pct",
        "strategy_result_pct",
        "result_date",
        "details",
    ])

    for row in data.get("rows", []):
        evaluation = row.get("evaluation") or {}
        writer.writerow([
            row.get("id"),
            row.get("trade_date"),
            row.get("ticker"),
                row.get("model_version"),
            row.get("price"),
            row.get("change_pct"),
            row.get("action"),
            row.get("label"),
            row.get("confidence_pct"),
            row.get("risk_level"),
            row.get("entry_price"),
            row.get("target_price"),
            row.get("stop_loss"),
            row.get("horizon"),
            evaluation.get("status"),
            evaluation.get("label"),
            evaluation.get("result_pct"),
            row.get("strategy_result_pct"),
            evaluation.get("result_date"),
            evaluation.get("details"),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="signals_backtest.csv"'
        },
    )


from app.services.signals_model_compare import compare_signal_models
from app.services.signals_model_compare_page_html import build_signals_model_compare_page_html

@router.get("/signals/backtest", response_class=AIReportHTMLResponse)
def market_signals_backtest_page():
    return build_signals_backtest_page_html()




@router.get("/signals/models/compare.csv")
def market_signals_models_compare_csv(
    tickers: str = Query("SBER,GAZP,LKOH,PLZL,MOEX,VTBR"),
    model_versions: str | None = Query(None),
    limit: int = Query(150, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=300),
    future_limit: int = Query(20, ge=1, le=120),
    max_points_per_ticker: int = Query(25, ge=1, le=300),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    import csv
    import io

    data = compare_signal_models(
        db=db,
        tickers=tickers,
        model_versions=model_versions,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
    )

    winner = data.get("winner") or {}
    winner_model = winner.get("model_version")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "rank",
        "is_winner",
        "model_version",
        "score",
        "total",
        "actionable_count",
        "buy_watch",
        "hold_watch",
        "risk_sell_watch",
        "success",
        "failed",
        "open",
        "neutral",
        "accuracy_pct",
        "avg_result_pct",
        "avg_strategy_result_pct",
    ])

    for index, row in enumerate(data.get("rows") or [], start=1):
        summary = row.get("summary") or {}

        writer.writerow([
            index,
            row.get("model_version") == winner_model,
            row.get("model_version"),
            row.get("score"),
            summary.get("total"),
            summary.get("actionable_count"),
            summary.get("buy_watch"),
            summary.get("hold_watch"),
            summary.get("risk_sell_watch"),
            summary.get("success"),
            summary.get("failed"),
            summary.get("open"),
            summary.get("neutral"),
            summary.get("accuracy_pct"),
            summary.get("avg_result_pct"),
            summary.get("avg_strategy_result_pct"),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="signals_model_compare.csv"'
        },
    )


@router.get("/signals/models/compare.json")
def market_signals_models_compare_json(
    tickers: str = Query("SBER,GAZP,LKOH,PLZL,MOEX,VTBR"),
    model_versions: str | None = Query(None),
    limit: int = Query(150, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=300),
    future_limit: int = Query(20, ge=1, le=120),
    max_points_per_ticker: int = Query(25, ge=1, le=300),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return compare_signal_models(
        db=db,
        tickers=tickers,
        model_versions=model_versions,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
    )


@router.get("/signals/models/compare", response_class=AIReportHTMLResponse)
def market_signals_models_compare_page():
    return build_signals_model_compare_page_html()



# --- Signal model quality ---

from app.services.signals_model_quality import build_signal_model_quality_report
from app.services.signals_model_quality_page_html import build_signals_model_quality_page_html


@router.get("/signals/models/quality.json")
def market_signals_models_quality_json(
    model_versions: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(120, ge=20, le=1000),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return build_signal_model_quality_report(
        db=db,
        model_versions=model_versions,
        limit=limit,
        candles_limit=candles_limit,
        action=action,
    )


@router.get("/signals/models/quality", response_class=HTMLResponse)
def market_signals_models_quality_page():
    return build_signals_model_quality_page_html()


# --- Signal model registry ---

from app.services.signal_model_registry import (
    PRODUCTION_SIGNAL_MODEL_VERSION,
    get_production_signal_model_version,
    get_signal_model_info,
    list_signal_models,
    set_production_signal_model_version,
)


@router.get("/signals/models")
def market_signal_models():
    return {
        "production_model": get_signal_model_info(get_production_signal_model_version()),
        "models": list_signal_models(),
    }


@router.post("/signals/models/production")
def market_signal_models_set_production(
    model_version: str = Query(...),
):
    production_model = set_production_signal_model_version(model_version)

    return {
        "ok": True,
        "production_model": production_model,
        "models": list_signal_models(),
    }

# --- Signal champion dashboard ---

from app.services.signals_champion_page_html import build_signal_champion_page_html


@router.get("/signals/champion", response_class=HTMLResponse)
def market_signals_champion_page():
    return build_signal_champion_page_html()
