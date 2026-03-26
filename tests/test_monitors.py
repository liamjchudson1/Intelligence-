"""Tests for monitor base functionality."""

import datetime as dt

from culturalintel.monitors.base import BaseMonitor, RawPost


class MockMonitor(BaseMonitor):
    source_name = "mock"

    def collect(self, since=None):
        return [
            RawPost(
                source="mock",
                platform_id="1",
                author="testuser",
                content="I love the parlay boost on FanDuel today!",
                url="https://example.com/1",
                created_at=dt.datetime.utcnow(),
                engagement={"likes": 10},
            ),
            RawPost(
                source="mock",
                platform_id="2",
                author="testuser2",
                content="Nice weather outside today",
                url="https://example.com/2",
                created_at=dt.datetime.utcnow(),
                engagement={"likes": 5},
            ),
        ]


def test_filter_relevant():
    config = {"keywords": ["parlay", "betting", "fanduel"]}
    monitor = MockMonitor(config)
    posts = monitor.collect()
    filtered = monitor.filter_relevant(posts)
    assert len(filtered) == 1
    assert "parlay" in filtered[0].content.lower()


def test_no_keywords_returns_all():
    config = {"keywords": []}
    monitor = MockMonitor(config)
    posts = monitor.collect()
    filtered = monitor.filter_relevant(posts)
    assert len(filtered) == 2
