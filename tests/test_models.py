"""Tests for database models."""

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from culturalintel.models import Base, Signal, Report, Prediction


def test_signal_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    signal = Signal(
        vertical="sports_betting",
        source="reddit",
        topic="Same Game Parlay Fatigue",
        description="Users expressing frustration with SGP outcomes",
        post_count=42,
        engagement_score=156.3,
        sentiment_score=-0.4,
        growth_score=72.0,
        commercial_score=65.0,
    )
    session.add(signal)
    session.commit()

    result = session.query(Signal).first()
    assert result.topic == "Same Game Parlay Fatigue"
    assert result.vertical == "sports_betting"
    assert result.growth_score == 72.0
    session.close()


def test_report_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    report = Report(
        vertical="sports_betting",
        title="Weekly Intelligence Report",
        content_markdown="# Report\n\nTest content",
        content_html="<h1>Report</h1><p>Test content</p>",
        signal_count=5,
    )
    session.add(report)
    session.commit()

    result = session.query(Report).first()
    assert result.title == "Weekly Intelligence Report"
    assert result.signal_count == 5
    session.close()


def test_prediction_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    signal = Signal(
        vertical="sports_betting",
        source="twitter",
        topic="Test Signal",
    )
    session.add(signal)
    session.flush()

    prediction = Prediction(
        signal_id=signal.id,
        vertical="sports_betting",
        prediction_type="growth",
        predicted_value=85.0,
    )
    session.add(prediction)
    session.commit()

    result = session.query(Prediction).first()
    assert result.predicted_value == 85.0
    assert result.actual_value is None
    session.close()
