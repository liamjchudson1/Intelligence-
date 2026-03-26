"""Email delivery via Beehiiv API."""

from __future__ import annotations

import httpx
import structlog

from culturalintel.config import settings
from culturalintel.models import Report

logger = structlog.get_logger()

BEEHIIV_API_BASE = "https://api.beehiiv.com/v2"


class BeehiivDelivery:
    """Deliver reports as Beehiiv newsletter posts."""

    def __init__(self) -> None:
        self.api_key = settings.beehiiv_api_key
        self.publication_id = settings.beehiiv_publication_id

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.publication_id)

    def deliver(self, report: Report) -> bool:
        """Create a draft post in Beehiiv from the report."""
        if not self.is_configured:
            logger.warning("beehiiv.not_configured")
            return False

        url = f"{BEEHIIV_API_BASE}/publications/{self.publication_id}/posts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "title": report.title,
            "subtitle": f"Cultural Intelligence Report — {report.vertical.title()}",
            "content": report.content_html,
            "status": "draft",  # publish manually or change to "published"
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()

            logger.info("beehiiv.delivered", report_id=report.id, title=report.title)
            return True
        except Exception as e:
            logger.error("beehiiv.error", error=str(e))
            return False
