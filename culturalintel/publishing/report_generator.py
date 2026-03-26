"""Generate formatted intelligence reports using Claude."""

from __future__ import annotations

import datetime as dt
import json

import anthropic
import markdown
import structlog

from culturalintel.config import settings
from culturalintel.models import Signal, Report, get_session

logger = structlog.get_logger()

REPORT_PROMPT = """\
You are a senior cultural intelligence analyst writing a weekly briefing for business \
decision-makers. Generate a polished intelligence report for the "{vertical}" vertical.

The report should:
- Open with a 2-3 sentence executive summary of the most important shifts this week
- Group signals into themes (e.g., "Emerging Trends", "Sentiment Shifts", "Watch List")
- For each signal, explain WHAT is happening, WHY it matters, and WHAT TO DO about it
- Include a "Predictions" section with 2-3 forward-looking calls
- Close with a "Signal Strength Ranking" — a numbered list of the top 5 signals by impact
- Use clear, confident, jargon-free language suitable for C-suite executives
- Format as clean Markdown with headers, bullet points, and bold key phrases

Date range: {date_start} to {date_end}

Signals data:
{signals_data}

Write the full report in Markdown format.
"""


class ReportGenerator:
    """Generate and store intelligence reports."""

    def __init__(self, vertical: str) -> None:
        self.vertical = vertical
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate(
        self,
        signals: list[Signal],
        date_start: dt.datetime | None = None,
        date_end: dt.datetime | None = None,
    ) -> Report:
        """Generate a full intelligence report from analysed signals."""
        if date_end is None:
            date_end = dt.datetime.utcnow()
        if date_start is None:
            date_start = date_end - dt.timedelta(days=7)

        signals_data = self._format_signals(signals)

        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
            temperature=0.5,
            messages=[
                {
                    "role": "user",
                    "content": REPORT_PROMPT.format(
                        vertical=self.vertical,
                        date_start=date_start.strftime("%B %d, %Y"),
                        date_end=date_end.strftime("%B %d, %Y"),
                        signals_data=signals_data,
                    ),
                }
            ],
        )

        content_md = message.content[0].text
        content_html = markdown.markdown(content_md, extensions=["tables", "fenced_code"])

        # Extract title from first heading or generate one
        title = self._extract_title(content_md, date_end)

        report = Report(
            vertical=self.vertical,
            title=title,
            content_markdown=content_md,
            content_html=content_html,
            signal_count=len(signals),
        )

        # Persist
        session = get_session()
        try:
            session.add(report)
            session.commit()
            session.refresh(report)
            logger.info(
                "report.generated",
                vertical=self.vertical,
                report_id=report.id,
                signal_count=len(signals),
            )
        except Exception as e:
            session.rollback()
            logger.error("report.persist_error", error=str(e))
        finally:
            session.close()

        return report

    def _format_signals(self, signals: list[Signal]) -> str:
        """Format signals for the report generation prompt."""
        lines = []
        for i, s in enumerate(signals, 1):
            lines.append(
                f"Signal {i}: {s.topic}\n"
                f"  Description: {s.description}\n"
                f"  Source: {s.source} | Posts: {s.post_count} | "
                f"Engagement: {s.engagement_score:.1f}\n"
                f"  Sentiment: {s.sentiment_score:+.2f} | "
                f"Growth Score: {s.growth_score:.0f}/100 | "
                f"Commercial Score: {s.commercial_score:.0f}/100\n"
                f"  Status: {s.status}\n"
                f"  Evidence: {s.raw_data[:300]}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _extract_title(content_md: str, date: dt.datetime) -> str:
        """Extract title from first markdown heading."""
        for line in content_md.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return f"Cultural Intelligence Report — Week of {date.strftime('%B %d, %Y')}"
