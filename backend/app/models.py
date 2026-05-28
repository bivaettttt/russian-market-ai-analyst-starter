from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, Text
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    board: Mapped[str] = mapped_column(String(16), default="TQBR", index=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    is_signal_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("ticker", "board", "trade_date", name="uq_candle_ticker_board_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    board: Mapped[str] = mapped_column(String(16), default="TQBR", index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketEvent(Base):
    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    importance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impact: Mapped[str | None] = mapped_column(String(64), nullable=True)
    affected_assets: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class MacroValue(Base):
    __tablename__ = "macro_values"
    __table_args__ = (
        UniqueConstraint("metric", "date", name="uq_macro_metric_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    metric: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float]
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- AI Report history ---

from datetime import datetime as _AIReportDatetime
from sqlalchemy import Boolean, Column as _AIReportColumn
from sqlalchemy import Boolean, DateTime as _AIReportDateTime
from sqlalchemy import Boolean, Integer as _AIReportInteger
from sqlalchemy import Boolean, String as _AIReportString
from sqlalchemy import Boolean, Text as _AIReportText
from sqlalchemy import Boolean as _AIReportBoolean


class AIReportSnapshot(Base):
    __tablename__ = "ai_report_snapshots"

    id = _AIReportColumn(_AIReportInteger, primary_key=True, index=True)
    created_at = _AIReportColumn(_AIReportDateTime, default=_AIReportDatetime.utcnow, index=True)
    report_date = _AIReportColumn(_AIReportString(32), index=True)
    title = _AIReportColumn(_AIReportString(255), default="AI Report российского рынка")
    portfolio_json = _AIReportColumn(_AIReportText)
    report_json = _AIReportColumn(_AIReportText)
    markdown = _AIReportColumn(_AIReportText)
    is_favorite = _AIReportColumn(_AIReportBoolean, default=False, index=True)
    note = _AIReportColumn(_AIReportText, default="")


# --- User portfolio ---

from sqlalchemy import Boolean, Float as _PortfolioFloat


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id = _AIReportColumn(_AIReportInteger, primary_key=True, index=True)
    ticker = _AIReportColumn(_AIReportString(32), unique=True, index=True, nullable=False)
    quantity = _AIReportColumn(_PortfolioFloat, nullable=False, default=0)
    updated_at = _AIReportColumn(_AIReportDateTime, default=_AIReportDatetime.utcnow)



class SignalSnapshot(Base):
    __tablename__ = "signal_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    ticker = Column(String, nullable=False, index=True)
    model_version = Column(String, nullable=True, default="tech_v1_sma_momentum")
    trade_date = Column(String, nullable=True)

    price = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)

    action = Column(String, nullable=False, index=True)
    label = Column(String, nullable=True)

    entry_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)

    confidence_pct = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    horizon = Column(String, nullable=True)

    reasons_json = Column(Text, nullable=False, default="[]")
    technical_json = Column(Text, nullable=False, default="{}")
    signal_json = Column(Text, nullable=False, default="{}")


# --- Portfolio constructor snapshots ---

class PortfolioConstructSnapshot(Base):
    __tablename__ = "portfolio_construct_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    horizon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)

    positions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    excluded_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


# --- Conservative event overlay paper tracking ---

class EventOverlayPaperSnapshot(Base):
    __tablename__ = "event_overlay_paper_snapshots"
    __table_args__ = (
        Index("ix_event_overlay_snapshot_date_status", "snapshot_date", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    snapshot_date = Column(String(32), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    source = Column(String(128), nullable=False, default="conservative_event_overlay")
    config_id = Column(String(128), nullable=False, index=True)
    overlay_mode = Column(String(64), nullable=False, default="soft_adjust")
    limit = Column(Integer, nullable=True)
    candles_limit = Column(Integer, nullable=True)
    horizon_days = Column(Integer, nullable=False, default=20)

    baseline_total_exposure = Column(Float, nullable=True)
    overlay_total_exposure = Column(Float, nullable=True)
    exposure_reduction_pct = Column(Float, nullable=True)
    avg_multiplier = Column(Float, nullable=True)
    risk_level_counts_json = Column(Text, nullable=False, default="{}")
    summary_json = Column(Text, nullable=False, default="{}")

    status = Column(String(64), nullable=False, default="open", index=True)
    evaluated_at = Column(DateTime, nullable=True, index=True)
    notes = Column(Text, nullable=True)


class EventOverlayPaperSnapshotItem(Base):
    __tablename__ = "event_overlay_paper_snapshot_items"
    __table_args__ = (
        Index("ix_event_overlay_item_snapshot_ticker", "snapshot_id", "ticker"),
    )

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("event_overlay_paper_snapshots.id"), nullable=False, index=True)
    ticker = Column(String(32), nullable=False, index=True)
    action = Column(String(128), nullable=True)
    recommendation = Column(Text, nullable=True)
    entry_price = Column(Float, nullable=True)
    entry_date = Column(String(32), nullable=True, index=True)

    base_position_size_pct = Column(Float, nullable=True)
    overlay_position_size_pct = Column(Float, nullable=True)
    event_risk_score = Column(Float, nullable=True)
    event_risk_level = Column(String(64), nullable=True, index=True)
    event_risk_multiplier = Column(Float, nullable=True)
    event_risk_reasons_json = Column(Text, nullable=False, default="[]")
    matched_rules_json = Column(Text, nullable=False, default="[]")

    target_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    target_probability_pct = Column(Float, nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)
    sector = Column(String(128), nullable=True)
    market_regime = Column(String(64), nullable=True)
    row_json = Column(Text, nullable=False, default="{}")

    realized_price = Column(Float, nullable=True)
    realized_date = Column(String(32), nullable=True)
    realized_return_pct = Column(Float, nullable=True)
    baseline_realized_pnl_pct = Column(Float, nullable=True)
    overlay_realized_pnl_pct = Column(Float, nullable=True)
    overlay_delta_pnl_pct = Column(Float, nullable=True)
    realized_outcome = Column(String(64), nullable=False, default="pending", index=True)
    evaluated_at = Column(DateTime, nullable=True, index=True)
