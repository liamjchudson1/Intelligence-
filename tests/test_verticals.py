"""Tests for vertical loading and configuration."""

from culturalintel.verticals.loader import load_vertical, list_verticals


def test_list_verticals():
    verticals = list_verticals()
    assert "sports_betting" in verticals


def test_load_sports_betting():
    config = load_vertical("sports_betting")
    assert config["name"] == "sports_betting"
    assert len(config["keywords"]) > 0
    assert len(config["subreddits"]) > 0
    assert "reddit" in config["monitors"]


def test_load_missing_vertical():
    try:
        load_vertical("nonexistent_vertical")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass
