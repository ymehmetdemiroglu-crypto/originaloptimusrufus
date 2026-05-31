"""Standalone entry point for the agent orchestrator.

Usage:
    # Run the full pipeline once (blocking)
    cd backend
    python -m agent --once

    # Run a specific job
    python -m agent --job scrape

    # Start scheduler in foreground
    python -m agent --schedule
"""

import argparse
import logging
import sys
import time

# Configure logging before any imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from agent.orchestrator import get_orchestrator
from agent.jobs import JobRegistry


def main():
    parser = argparse.ArgumentParser(description="Optimus Rufus Autonomous Agent")
    parser.add_argument("--once", action="store_true", help="Run full pipeline once and exit")
    parser.add_argument("--job", type=str, choices=JobRegistry.list_jobs(), help="Run a single job")
    parser.add_argument("--schedule", action="store_true", help="Start scheduler and block")
    parser.add_argument("--status", action="store_true", help="Print scheduler status and exit")
    args = parser.parse_args()

    orch = get_orchestrator()

    if args.status:
        import json
        print(json.dumps(orch.get_status(), indent=2, default=str))
        return

    if args.job:
        result = orch.trigger_job(args.job, triggered_by="cli")
        print(result)
        return

    if args.once:
        results = orch.run_full_pipeline_once(triggered_by="cli")
        for r in results:
            print(r)
        return

    if args.schedule:
        orch.start()
        print("Scheduler running. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            orch.stop()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
