"""Base monitor interface that all platform monitors implement."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


@dataclass
class RawPost:
    """A raw post collected from any platform."""

    source: str
    platform_id: str
    author: str
    content: str
    url: str
    created_at: dt.datetime
    engagement: dict = field(default_factory=dict)  # likes, comments, shares, etc.
    subreddit: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BaseMonitor(ABC):
    """Abstract base class for all platform monitors."""

    source_name: str = "unknown"

    def __init__(self, vertical_config: dict) -> None:
        self.vertical_config = vertical_config
        self.keywords: list[str] = vertical_config.get("keywords", [])
        self.subreddits: list[str] = vertical_config.get("subreddits", [])
        self.channels: list[str] = vertical_config.get("channels", [])
        self.forums: list[dict] = vertical_config.get("forums", [])

    @abstractmethod
    def collect(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Collect posts from the platform since the given datetime."""
        ...

    def filter_relevant(self, posts: list[RawPost]) -> list[RawPost]:
        """Filter posts by keyword relevance."""
        if not self.keywords:
            return posts
        filtered = []
        for post in posts:
            content_lower = post.content.lower()
            if any(kw.lower() in content_lower for kw in self.keywords):
                filtered.append(post)
        return filtered
