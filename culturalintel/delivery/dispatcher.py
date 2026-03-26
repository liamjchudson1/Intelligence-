"""Dispatch reports to all configured delivery channels."""

from __future__ import annotations

import structlog

from culturalintel.delivery.email_delivery import BeehiivDelivery
from culturalintel.delivery.webhook import SlackDelivery, TeamsDelivery
from culturalintel.models import Report, get_session

logger = structlog.get_logger()


class DeliveryDispatcher:
    """Send a report to all configured delivery channels."""

    def __init__(self) -> None:
        self.channels = {
            "beehiiv": BeehiivDelivery(),
            "slack": SlackDelivery(),
            "teams": TeamsDelivery(),
        }

    def deliver(self, report: Report, channels: list[str] | None = None) -> list[str]:
        """Deliver report to specified channels (or all configured ones).

        Returns list of channels that successfully received the report.
        """
        targets = channels or list(self.channels.keys())
        delivered: list[str] = []

        for name in targets:
            channel = self.channels.get(name)
            if channel is None:
                logger.warning("delivery.unknown_channel", channel=name)
                continue

            if not channel.is_configured:
                continue

            try:
                success = channel.deliver(report)
                if success:
                    delivered.append(name)
            except Exception as e:
                logger.error("delivery.error", channel=name, error=str(e))

        # Update report with delivery info
        if delivered:
            session = get_session()
            try:
                db_report = session.query(Report).filter(Report.id == report.id).first()
                if db_report:
                    db_report.delivered = ",".join(delivered)
                    session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()

        logger.info("delivery.complete", delivered=delivered, report_id=report.id)
        return delivered
