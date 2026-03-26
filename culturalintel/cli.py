"""Command-line interface for the Cultural Intelligence Platform."""

from __future__ import annotations

import argparse
import sys

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


def cmd_run(args: argparse.Namespace) -> None:
    """Run the full pipeline for a vertical once."""
    from culturalintel.pipeline import Pipeline
    from culturalintel.verticals import load_vertical
    from culturalintel.models import init_db

    init_db()
    config = load_vertical(args.vertical)
    pipeline = Pipeline(config)
    report = pipeline.run_full()
    print(f"\nReport generated: {report.title}")
    print(f"Signals: {report.signal_count}")
    if args.output:
        with open(args.output, "w") as f:
            f.write(report.content_markdown)
        print(f"Report saved to: {args.output}")
    else:
        print("\n" + report.content_markdown)


def cmd_schedule(args: argparse.Namespace) -> None:
    """Start the scheduler for recurring pipeline runs."""
    from culturalintel.scheduler import start_scheduler

    verticals = args.verticals if args.verticals else None
    start_scheduler(verticals=verticals)


def cmd_list(args: argparse.Namespace) -> None:
    """List available verticals."""
    from culturalintel.verticals import list_verticals

    verticals = list_verticals()
    if not verticals:
        print("No verticals configured. Add a config.json to culturalintel/verticals/<name>/")
        return
    print("Available verticals:")
    for v in verticals:
        print(f"  - {v}")


def cmd_feedback(args: argparse.Namespace) -> None:
    """Run the feedback loop for a vertical."""
    from culturalintel.learning.feedback import FeedbackLoop
    from culturalintel.models import init_db

    init_db()
    loop = FeedbackLoop(args.vertical)
    results = loop.evaluate_predictions(lookback_days=args.days)
    summary = loop.get_accuracy_summary()

    print(f"\nFeedback for '{args.vertical}':")
    print(f"  Predictions evaluated: {len(results)}")
    print(f"  Overall accuracy: {summary.get('avg_accuracy', 0):.2%}")
    if summary.get("by_type"):
        for ptype, acc in summary["by_type"].items():
            print(f"  {ptype}: {acc:.2%}")


def main() -> None:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="culturalintel",
        description="Cultural Intelligence Platform — Monitor, Analyse, Report",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run pipeline for a vertical")
    run_parser.add_argument("vertical", help="Vertical name (e.g., sports_betting)")
    run_parser.add_argument("-o", "--output", help="Save report to file")
    run_parser.set_defaults(func=cmd_run)

    # Schedule command
    sched_parser = subparsers.add_parser("schedule", help="Start the scheduler")
    sched_parser.add_argument(
        "verticals", nargs="*", help="Verticals to schedule (default: all)"
    )
    sched_parser.set_defaults(func=cmd_schedule)

    # List command
    list_parser = subparsers.add_parser("list", help="List available verticals")
    list_parser.set_defaults(func=cmd_list)

    # Feedback command
    fb_parser = subparsers.add_parser("feedback", help="Run prediction feedback loop")
    fb_parser.add_argument("vertical", help="Vertical name")
    fb_parser.add_argument("--days", type=int, default=14, help="Lookback days (default: 14)")
    fb_parser.set_defaults(func=cmd_feedback)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
