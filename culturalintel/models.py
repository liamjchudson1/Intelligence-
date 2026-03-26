"""SQLAlchemy models for persisting signals, reports, and predictions."""

from __future__ import annotations

import datetime as dt
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from culturalintel.config import settings


class Base(DeclarativeBase):
    pass


class SignalStatus(str, Enum):
    NEW = "new"
    RISING = "rising"
    PEAKED = "peaked"
    DECLINING = "declining"


class Signal(Base):
    """A detected cultural signal from a monitored source."""

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vertical = Column(String(100), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # reddit, twitter, discord, forum
    topic = Column(String(500), nullable=False)
    description = Column(Text, default="")
    first_seen = Column(DateTime, default=dt.datetime.utcnow)
    last_seen = Column(DateTime, default=dt.datetime.utcnow)
    post_count = Column(Integer, default=1)
    engagement_score = Column(Float, default=0.0)
    sentiment_score = Column(Float, default=0.0)  # -1.0 to 1.0
    growth_score = Column(Float, default=0.0)  # predicted growth trajectory 0-100
    commercial_score = Column(Float, default=0.0)  # commercial relevance 0-100
    status = Column(String(20), default=SignalStatus.NEW)
    raw_data = Column(Text, default="")  # JSON blob of source data


class Report(Base):
    """A generated intelligence report."""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vertical = Column(String(100), nullable=False, index=True)
    generated_at = Column(DateTime, default=dt.datetime.utcnow)
    title = Column(String(500), nullable=False)
    content_markdown = Column(Text, nullable=False)
    content_html = Column(Text, default="")
    signal_count = Column(Integer, default=0)
    delivered = Column(String(200), default="")  # comma-separated delivery channels


class Prediction(Base):
    """A prediction made by the analysis engine, tracked for learning."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, nullable=False)
    vertical = Column(String(100), nullable=False)
    predicted_at = Column(DateTime, default=dt.datetime.utcnow)
    prediction_type = Column(String(50), nullable=False)  # growth, virality, commercial
    predicted_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=True)  # filled in later
    evaluated_at = Column(DateTime, nullable=True)
    accuracy_score = Column(Float, nullable=True)  # 0-1, calculated after evaluation


engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
