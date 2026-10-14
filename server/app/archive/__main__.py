"""Export finished sessions into the archive.

    infisical run -- uv run python -m app.archive 2025          # every finished session of 2025
    infisical run -- uv run python -m app.archive 2025 r16      # every session of one event
    infisical run -- uv run python -m app.archive 2025 r16 R    # one session

`infisical run` supplies the R2 credentials from Infisical's dev environment,
whose bucket is only for testing. Pass --env=prod to it to export into the
production bucket.

Sessions already exported are skipped unless their results have since become
final. --overwrite exports them again anyway; --force also exports sessions
that ended less than EXPORT_DELAY ago or whose end time is unknown.

A session FastF1 fails to load completely isn't exported, since it would stay
incomplete in the archive. Run it again later; if the data doesn't exist
upstream, --allow-incomplete exports it with the missing parts recorded.

An event's circuit info is built when its first session is exported, or a
later one if that fails. --circuit builds only the circuit info, from the
first finished session (or the one given) with car and position data, for
events that have none, or for all of them with --overwrite:

    infisical run -- uv run python -m app.archive 2018 r12 --circuit
"""

import argparse
import logging
import os
import sys
from collections import Counter

import fastf1

from app.archive.archive import open_archive
from app.archive.export import IncompleteLoadError, export_circuit, export_session
from app.config import Settings
from app.fastf1_loader import install_request_timeouts
from app.schedule.services import CircuitInfoUnavailable, get_event, get_schedule

logger = logging.getLogger("uvicorn.error")


def _circuit_sources(year: int, event_id: str | None, identifier: str | None) -> list[tuple[str, list[str]]]:
    """Each event with the sessions to try building its circuit info from, in order."""
    if identifier:
        return [(event_id, [identifier])]
    event_ids = [event_id] if event_id else [
        event["identifier"] for event in get_schedule(year)["events"] if event["status"] != "upcoming"
    ]
    return [
        (e, [s["identifier"] for s in get_event(year, e)["sessions"] if s["status"] != "upcoming"])
        for e in event_ids
    ]


def _sessions(year: int, event_id: str | None, identifier: str | None) -> list[tuple[str, str]]:
    if identifier:
        return [(event_id, identifier)]
    if event_id:
        return [(event_id, s["identifier"]) for s in get_event(year, event_id)["sessions"]]
    return [
        (event["identifier"], s["identifier"])
        for event in get_schedule(year)["events"]
        if event["status"] != "upcoming"
        for s in get_event(year, event["identifier"])["sessions"]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.archive", description="Export finished sessions into the archive.")
    parser.add_argument("year", type=int)
    parser.add_argument("event_id", nargs="?", help="e.g. r16 or t1")
    parser.add_argument("identifier", nargs="?", help="e.g. FP1, Q or R")
    parser.add_argument("--overwrite", action="store_true", help="export sessions that are already exported")
    parser.add_argument("--force", action="store_true", help="export sessions that may not be finished yet")
    parser.add_argument(
        "--allow-incomplete", action="store_true", help="export sessions FastF1 can only partly load"
    )
    parser.add_argument(
        "--circuit", action="store_true", help="only build circuit info, for events that have none"
    )
    args = parser.parse_args(argv)
    if args.identifier and not args.event_id:
        parser.error("identifier requires event_id")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = Settings()
    archive = open_archive(settings)
    if archive is None:
        parser.error("no archive configured: run through `infisical run --`, or set R2_BUCKET (and its credentials) or ARCHIVE_LOCAL_DIR")
    os.makedirs(settings.fastf1_cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(settings.fastf1_cache_dir)
    install_request_timeouts(settings.upstream_connect_timeout_seconds, settings.upstream_read_timeout_seconds)
    # FastF1 logs every cache read at INFO; keep the export progress readable.
    # Only its console output is quieted: the export reads FastF1's DEBUG
    # records to notice parts that failed to load.
    fastf1.set_log_level(logging.WARNING)
    logging.getLogger("fastf1").propagate = False

    outcomes: Counter[str] = Counter()
    if args.circuit:
        for event_id, identifiers in _circuit_sources(args.year, args.event_id, args.identifier):
            try:
                outcome = export_circuit(archive, args.year, event_id, identifiers, overwrite=args.overwrite)
            except CircuitInfoUnavailable as exc:
                logger.error("No circuit info for %s %s: %s", args.year, event_id, exc)
                outcomes["failed"] += 1
            except Exception:
                logger.exception("Failed to export circuit info for %s %s", args.year, event_id)
                outcomes["failed"] += 1
            else:
                outcomes[outcome.value] += 1
    else:
        for event_id, identifier in _sessions(args.year, args.event_id, args.identifier):
            try:
                outcome = export_session(
                    archive,
                    args.year,
                    event_id,
                    identifier,
                    force=args.force,
                    overwrite=args.overwrite,
                    allow_incomplete=args.allow_incomplete,
                )
            except IncompleteLoadError as exc:
                logger.error("Not exporting %s %s %s: %s", args.year, event_id, identifier, exc)
                outcomes["failed"] += 1
            except Exception:
                logger.exception("Failed to export %s %s %s", args.year, event_id, identifier)
                outcomes["failed"] += 1
            else:
                outcomes[outcome.value] += 1

    logger.info("Done: %s", ", ".join(f"{count} {name}" for name, count in sorted(outcomes.items())) or "nothing to export")
    return 1 if outcomes["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
