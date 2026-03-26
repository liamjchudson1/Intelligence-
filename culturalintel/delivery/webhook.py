"""Webhook delivery for Slack and Microsoft Teams."""

from __future__ import annotations

import httpx
import structlog

from culturalintel.config import settings
from culturalintel.models import Report

logger = structlog.get_logger()


class SlackDelivery:
    """Deliver report summaries via Slack incoming webhook."""

    def __init__(self) -> None:
        self.webhook_url = settings.slack_webhook_url

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def deliver(self, report: Report) -> bool:
        """Post a summary of the report to Slack."""
        if not self.is_configured:
            logger.warning("slack.not_configured")
            return False

        # Truncate for Slack (max ~3000 chars for a readable message)
        summary = report.content_markdown[:2500]
        if len(report.content_markdown) > 2500:
            summary += "\n\n_...report truncated. See full report in dashboard._"

        payload = {
            "text": f"*{report.title}*",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": report.title[:150]},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": summary},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": (
                                f"Vertical: {report.vertical} | "
                                f"Signals: {report.signal_count} | "
                                f"Generated: {report.generated_at}"
                            ),
                        }
                    ],
                },
            ],
        }

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(self.webhook_url, json=payload)
                resp.raise_for_status()

            logger.info("slack.delivered", report_id=report.id)
            return True
        except Exception as e:
            logger.error("slack.error", error=str(e))
            return False


class TeamsDelivery:
    """Deliver report summaries via Microsoft Teams incoming webhook."""

    def __init__(self) -> None:
        self.webhook_url = settings.teams_webhook_url

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def deliver(self, report: Report) -> bool:
        """Post a summary of the report to Teams."""
        if not self.is_configured:
            logger.warning("teams.not_configured")
            return False

        summary = report.content_markdown[:3000]

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": report.title,
            "themeColor": "0076D7",
            "title": report.title,
            "sections": [
                {
                    "activityTitle": f"Cultural Intelligence — {report.vertical.title()}",
                    "text": summary,
                    "facts": [
                        {"name": "Signals", "value": str(report.signal_count)},
                        {"name": "Generated", "value": str(report.generated_at)},
                    ],
                }
            ],
        }

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(self.webhook_url, json=payload)
                resp.raise_for_status()

            logger.info("teams.delivered", report_id=report.id)
            return True
        except Exception as e:
            logger.error("teams.error", error=str(e))
            return False
