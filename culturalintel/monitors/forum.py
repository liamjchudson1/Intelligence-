"""Generic forum scraper using BeautifulSoup for niche community forums."""

from __future__ import annotations

import datetime as dt

import httpx
from bs4 import BeautifulSoup
import structlog

from culturalintel.monitors.base import BaseMonitor, RawPost

logger = structlog.get_logger()


class ForumMonitor(BaseMonitor):
    """Scrape niche forums for cultural signals via HTML parsing."""

    source_name = "forum"

    def __init__(self, vertical_config: dict) -> None:
        super().__init__(vertical_config)
        # forums config: [{"name": "...", "url": "...", "post_selector": "...", ...}]
        self.forum_configs: list[dict] = vertical_config.get("forums", [])

    def collect(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Scrape configured forums for recent posts."""
        if since is None:
            since = dt.datetime.utcnow() - dt.timedelta(days=7)

        posts: list[RawPost] = []

        for forum in self.forum_configs:
            try:
                posts.extend(self._scrape_forum(forum, since))
            except Exception as e:
                logger.error("forum.error", forum=forum.get("name", "unknown"), error=str(e))

        return self.filter_relevant(posts)

    def _scrape_forum(self, forum: dict, since: dt.datetime) -> list[RawPost]:
        """Scrape a single forum based on its CSS selector configuration."""
        posts: list[RawPost] = []
        url = forum["url"]
        name = forum.get("name", url)

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "CulturalIntel/0.1 (research bot)"})
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Use configurable CSS selectors with sensible defaults
        post_selector = forum.get("post_selector", "article, .post, .thread, .topic")
        title_selector = forum.get("title_selector", "h2 a, h3 a, .title a, .topic-title a")
        content_selector = forum.get("content_selector", ".content, .message, .post-body, p")
        author_selector = forum.get("author_selector", ".author, .username, .poster")

        elements = soup.select(post_selector)

        for elem in elements[:100]:  # cap at 100 per forum
            title_el = elem.select_one(title_selector)
            content_el = elem.select_one(content_selector)
            author_el = elem.select_one(author_selector)

            title = title_el.get_text(strip=True) if title_el else ""
            content = content_el.get_text(strip=True) if content_el else elem.get_text(strip=True)
            author = author_el.get_text(strip=True) if author_el else "anonymous"

            post_url = url
            if title_el and title_el.get("href"):
                href = title_el["href"]
                if href.startswith("http"):
                    post_url = href
                else:
                    post_url = url.rstrip("/") + "/" + href.lstrip("/")

            posts.append(
                RawPost(
                    source="forum",
                    platform_id=f"{name}:{hash(title + content)}",
                    author=author,
                    content=f"{title}\n\n{content}" if title else content,
                    url=post_url,
                    created_at=dt.datetime.utcnow(),  # forums rarely expose structured dates
                    engagement={},
                    metadata={"forum_name": name},
                )
            )

        logger.info("forum.collected", forum=name, post_count=len(posts))
        return posts
