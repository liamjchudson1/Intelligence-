"""Twitter/X monitor using Tweepy v2 API."""

from __future__ import annotations

import datetime as dt

import tweepy
import structlog

from culturalintel.config import settings
from culturalintel.monitors.base import BaseMonitor, RawPost

logger = structlog.get_logger()


class TwitterMonitor(BaseMonitor):
    """Monitor Twitter/X for cultural signals using the v2 API."""

    source_name = "twitter"

    def __init__(self, vertical_config: dict) -> None:
        super().__init__(vertical_config)
        self.client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            wait_on_rate_limit=True,
        )
        self.search_queries: list[str] = vertical_config.get("twitter_queries", [])

    def collect(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Collect recent tweets matching configured queries."""
        if since is None:
            since = dt.datetime.utcnow() - dt.timedelta(days=7)

        posts: list[RawPost] = []

        for query in self.search_queries:
            try:
                response = self.client.search_recent_tweets(
                    query=query,
                    max_results=100,
                    start_time=since,
                    tweet_fields=["created_at", "public_metrics", "author_id", "entities"],
                    expansions=["author_id"],
                )

                if not response.data:
                    continue

                # Build author lookup
                authors = {}
                if response.includes and "users" in response.includes:
                    authors = {u.id: u.username for u in response.includes["users"]}

                for tweet in response.data:
                    metrics = tweet.public_metrics or {}
                    post = RawPost(
                        source="twitter",
                        platform_id=str(tweet.id),
                        author=authors.get(tweet.author_id, str(tweet.author_id)),
                        content=tweet.text,
                        url=f"https://x.com/i/status/{tweet.id}",
                        created_at=tweet.created_at or dt.datetime.utcnow(),
                        engagement={
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "replies": metrics.get("reply_count", 0),
                            "impressions": metrics.get("impression_count", 0),
                        },
                        tags=self._extract_hashtags(tweet),
                    )
                    posts.append(post)

                logger.info("twitter.collected", query=query, tweet_count=len(response.data))

            except Exception as e:
                logger.error("twitter.error", query=query, error=str(e))

        return self.filter_relevant(posts)

    @staticmethod
    def _extract_hashtags(tweet) -> list[str]:
        """Extract hashtags from tweet entities."""
        if tweet.entities and "hashtags" in tweet.entities:
            return [h["tag"] for h in tweet.entities["hashtags"]]
        return []
