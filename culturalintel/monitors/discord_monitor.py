"""Discord monitor using bot API via aiohttp (lightweight, no full discord.py dependency)."""

from __future__ import annotations

import datetime as dt

import aiohttp
import structlog

from culturalintel.config import settings
from culturalintel.monitors.base import BaseMonitor, RawPost

logger = structlog.get_logger()

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordMonitor(BaseMonitor):
    """Monitor Discord channels for cultural signals."""

    source_name = "discord"

    def __init__(self, vertical_config: dict) -> None:
        super().__init__(vertical_config)
        self.channel_ids: list[str] = vertical_config.get("discord_channel_ids", [])
        self.headers = {
            "Authorization": f"Bot {settings.discord_bot_token}",
            "Content-Type": "application/json",
        }

    def collect(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Collect messages from configured Discord channels (sync wrapper)."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an async context, create a new task
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return loop.run_in_executor(pool, self._collect_sync, since)
            return loop.run_until_complete(self._collect_async(since))
        except RuntimeError:
            return asyncio.run(self._collect_async(since))

    def _collect_sync(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Synchronous fallback for Discord collection."""
        import asyncio

        return asyncio.run(self._collect_async(since))

    async def _collect_async(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Async collection from Discord channels."""
        if since is None:
            since = dt.datetime.utcnow() - dt.timedelta(days=7)

        posts: list[RawPost] = []

        async with aiohttp.ClientSession(headers=self.headers) as session:
            for channel_id in self.channel_ids:
                try:
                    # Convert since to Discord snowflake for pagination
                    snowflake = int((since.timestamp() - 1420070400) * 1000) << 22
                    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
                    params = {"after": str(snowflake), "limit": 100}

                    async with session.get(url, params=params) as resp:
                        if resp.status != 200:
                            logger.error(
                                "discord.api_error",
                                channel=channel_id,
                                status=resp.status,
                            )
                            continue

                        messages = await resp.json()
                        for msg in messages:
                            if msg.get("author", {}).get("bot", False):
                                continue

                            created = dt.datetime.fromisoformat(
                                msg["timestamp"].replace("+00:00", "")
                            )
                            posts.append(
                                RawPost(
                                    source="discord",
                                    platform_id=msg["id"],
                                    author=msg.get("author", {}).get("username", "unknown"),
                                    content=msg.get("content", ""),
                                    url=f"https://discord.com/channels/-/{channel_id}/{msg['id']}",
                                    created_at=created,
                                    engagement={
                                        "reactions": sum(
                                            r.get("count", 0)
                                            for r in msg.get("reactions", [])
                                        ),
                                    },
                                )
                            )

                    logger.info(
                        "discord.collected",
                        channel=channel_id,
                        message_count=len(
                            [p for p in posts if channel_id in p.url]
                        ),
                    )
                except Exception as e:
                    logger.error("discord.error", channel=channel_id, error=str(e))

        return self.filter_relevant(posts)
