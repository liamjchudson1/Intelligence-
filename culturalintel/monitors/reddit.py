"""Reddit monitor using PRAW (Python Reddit API Wrapper)."""

from __future__ import annotations

import datetime as dt
import json

import praw
import structlog

from culturalintel.config import settings
from culturalintel.monitors.base import BaseMonitor, RawPost

logger = structlog.get_logger()


class RedditMonitor(BaseMonitor):
    """Monitor Reddit subreddits for cultural signals."""

    source_name = "reddit"

    def __init__(self, vertical_config: dict) -> None:
        super().__init__(vertical_config)
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        self.reddit.read_only = True

    def collect(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Collect recent posts from configured subreddits."""
        if since is None:
            since = dt.datetime.utcnow() - dt.timedelta(days=7)

        posts: list[RawPost] = []

        for subreddit_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                for submission in subreddit.new(limit=200):
                    created = dt.datetime.utcfromtimestamp(submission.created_utc)
                    if created < since:
                        continue

                    post = RawPost(
                        source="reddit",
                        platform_id=submission.id,
                        author=str(submission.author) if submission.author else "[deleted]",
                        content=f"{submission.title}\n\n{submission.selftext}",
                        url=f"https://reddit.com{submission.permalink}",
                        created_at=created,
                        subreddit=subreddit_name,
                        engagement={
                            "upvotes": submission.score,
                            "upvote_ratio": submission.upvote_ratio,
                            "comments": submission.num_comments,
                            "awards": submission.total_awards_received,
                        },
                        tags=[f.text for f in (submission.link_flair_richtext or [])],
                        metadata={
                            "is_self": submission.is_self,
                            "domain": submission.domain,
                        },
                    )
                    posts.append(post)

                logger.info(
                    "reddit.collected",
                    subreddit=subreddit_name,
                    post_count=len([p for p in posts if p.subreddit == subreddit_name]),
                )
            except Exception as e:
                logger.error("reddit.error", subreddit=subreddit_name, error=str(e))

        return self.filter_relevant(posts)

    def collect_comments(self, subreddit_name: str, limit: int = 500) -> list[RawPost]:
        """Collect recent comments for deeper sentiment analysis."""
        comments: list[RawPost] = []
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            for comment in subreddit.comments(limit=limit):
                created = dt.datetime.utcfromtimestamp(comment.created_utc)
                comments.append(
                    RawPost(
                        source="reddit",
                        platform_id=comment.id,
                        author=str(comment.author) if comment.author else "[deleted]",
                        content=comment.body,
                        url=f"https://reddit.com{comment.permalink}",
                        created_at=created,
                        subreddit=subreddit_name,
                        engagement={"upvotes": comment.score},
                    )
                )
        except Exception as e:
            logger.error("reddit.comments_error", subreddit=subreddit_name, error=str(e))

        return self.filter_relevant(comments)
