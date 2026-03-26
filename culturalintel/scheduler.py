"""Scheduler for running pipelines on a recurring basis using APScheduler."""

from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from culturalintel.pipeline import Pipeline
from culturalintel.verticals import load_vertical, list_verticals
from culturalintel.models import init_db

logger = structlog.get_logger()


def run_vertical_pipeline(vertical_name: str) -> None:
    """Execute the full pipeline for a vertical."""
    try:
        config = load_vertical(vertical_name)
        pipeline = Pipeline(config)
        report = pipeline.run_full()
        logger.info(
            "scheduler.pipeline_done",
            vertical=vertical_name,
            report_title=report.title,
        )
    except Exception as e:
        logger.error("scheduler.pipeline_error", vertical=vertical_name, error=str(e))


def start_scheduler(verticals: list[str] | None = None) -> None:
    """Start the scheduler with jobs for each vertical.

    Each vertical gets:
    - A monitoring job that runs every N hours (for data freshness)
    - A report generation job that runs weekly
    """
    init_db()

    if verticals is None:
        verticals = list_verticals()

    if not verticals:
        logger.error("scheduler.no_verticals")
        return

    scheduler = BlockingScheduler()

    for vertical_name in verticals:
        try:
            config = load_vertical(vertical_name)
            schedule = config.get("schedule", {})

            # Weekly full pipeline (collect + analyse + report + deliver)
            report_day = schedule.get("report_day", "monday")
            report_hour = schedule.get("report_hour", 8)

            scheduler.add_job(
                run_vertical_pipeline,
                trigger=CronTrigger(day_of_week=report_day[:3], hour=report_hour),
                args=[vertical_name],
                id=f"{vertical_name}_weekly_report",
                name=f"Weekly report for {vertical_name}",
                misfire_grace_time=3600,
            )

            logger.info(
                "scheduler.job_added",
                vertical=vertical_name,
                schedule=f"{report_day} {report_hour}:00",
            )

        except Exception as e:
            logger.error("scheduler.setup_error", vertical=vertical_name, error=str(e))

    logger.info("scheduler.starting", verticals=verticals)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler.shutdown")
        scheduler.shutdown()
