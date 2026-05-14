from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    board: Mapped[str] = mapped_column(String(16), default="TQBR", index=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
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
from sqlalchemy import Column as _AIReportColumn
from sqlalchemy import DateTime as _AIReportDateTime
from sqlalchemy import Integer as _AIReportInteger
from sqlalchemy import String as _AIReportString
from sqlalchemy import Text as _AIReportText
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

from sqlalchemy import Float as _PortfolioFloat


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
