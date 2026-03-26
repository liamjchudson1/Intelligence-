"""Main pipeline orchestrator — ties monitor, analyse, publish, learn, deliver together."""

from __future__ import annotations

import datetime as dt

import structlog

from culturalintel.monitors.base import RawPost
from culturalintel.monitors.reddit import RedditMonitor
from culturalintel.monitors.twitter import TwitterMonitor
from culturalintel.monitors.discord_monitor import DiscordMonitor
from culturalintel.monitors.forum import ForumMonitor
from culturalintel.analysis.engine import AnalysisEngine
from culturalintel.publishing.report_generator import ReportGenerator
from culturalintel.learning.feedback import FeedbackLoop
from culturalintel.delivery.dispatcher import DeliveryDispatcher
from culturalintel.models import Signal, Report, init_db

logger = structlog.get_logger()

MONITOR_CLASSES = {
    "reddit": RedditMonitor,
    "twitter": TwitterMonitor,
    "discord": DiscordMonitor,
    "forum": ForumMonitor,
}


class Pipeline:
    """End-to-end pipeline for a single vertical."""

    def __init__(self, vertical_config: dict) -> None:
        self.config = vertical_config
        self.vertical = vertical_config["name"]
        self.monitors = self._init_monitors()
        self.analyser = AnalysisEngine(self.vertical)
        self.report_generator = ReportGenerator(self.vertical)
        self.feedback = FeedbackLoop(self.vertical)
        self.dispatcher = DeliveryDispatcher()

    def _init_monitors(self) -> list:
        """Initialize only the monitors specified in the vertical config."""
        monitors = []
        for name in self.config.get("monitors", ["reddit"]):
            cls = MONITOR_CLASSES.get(name)
            if cls:
                monitors.append(cls(self.config))
            else:
                logger.warning("pipeline.unknown_monitor", monitor=name)
        return monitors

    def run_collection(self, since: dt.datetime | None = None) -> list[RawPost]:
        """Step 1: Collect posts from all configured monitors."""
        logger.info("pipeline.collecting", vertical=self.vertical)
        all_posts: list[RawPost] = []

        for monitor in self.monitors:
            try:
                posts = monitor.collect(since=since)
                all_posts.extend(posts)
                logger.info(
                    "pipeline.monitor_done",
                    source=monitor.source_name,
                    posts=len(posts),
                )
            except Exception as e:
                logger.error(
                    "pipeline.monitor_error",
                    source=monitor.source_name,
                    error=str(e),
                )

        logger.info("pipeline.collected", vertical=self.vertical, total_posts=len(all_posts))
        return all_posts

    def run_analysis(self, posts: list[RawPost]) -> list[Signal]:
        """Step 2: Analyse collected posts with Claude."""
        logger.info("pipeline.analysing", vertical=self.vertical, posts=len(posts))
        return self.analyser.analyse_posts(posts)

    def run_report(self, signals: list[Signal]) -> Report:
        """Step 3: Generate intelligence report."""
        logger.info("pipeline.reporting", vertical=self.vertical, signals=len(signals))
        return self.report_generator.generate(signals)

    def run_feedback(self) -> list[dict]:
        """Step 4: Evaluate past predictions."""
        logger.info("pipeline.feedback", vertical=self.vertical)
        return self.feedback.evaluate_predictions()

    def run_delivery(self, report: Report) -> list[str]:
        """Step 5: Deliver report to configured channels."""
        channels = self.config.get("delivery_channels")
        return self.dispatcher.deliver(report, channels=channels)

    def run_full(self, since: dt.datetime | None = None) -> Report:
        """Run the complete pipeline end-to-end."""
        init_db()

        # Collect
        posts = self.run_collection(since=since)
        if not posts:
            logger.warning("pipeline.no_posts", vertical=self.vertical)
            # Generate report with empty signals anyway for continuity
            signals = []
        else:
            # Analyse
            signals = self.run_analysis(posts)

        # Generate report
        report = self.run_report(signals)

        # Evaluate past predictions (learning loop)
        self.run_feedback()

        # Deliver
        delivered = self.run_delivery(report)

        logger.info(
            "pipeline.complete",
            vertical=self.vertical,
            posts=len(posts),
            signals=len(signals),
            delivered=delivered,
        )
        return report
