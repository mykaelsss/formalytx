"""Export finished sessions into the archive.

    infisical run -- uv run python -m app.archive 2025          # every finished session of 2025
    infisical run -- uv run python -m app.archive 2025 r16      # every session of one event
    infisical run -- uv run python -m app.archive 2025 r16 R    # one session
    infisical run -- uv run python -m app.archive --recent      # this year's events that ended in the last week

The year defaults to the current one; seasons end in early December, so its
last events are done by January. --recent is what the scheduled export runs:
it only checks sessions of events that are under way or ended within RECENT,
which covers the time their results take to become final.

`infisical run` supplies the R2 credentials from Infisical's dev environment,
whose bucket is only for testing. Pass --env=prod to it to export into the
production bucket.

A session is exported as soon as it has ended and FastF1 can fully load it,
and checked again on every run until its results are final, writing only what
changed. Sessions with final results are skipped; --overwrite checks them
again anyway, and --force also exports sessions that haven't ended or whose
end time is unknown.

A session FastF1 fails to load completely isn't exported, since it would stay
incomplete in the archive. Within UPLOAD_WINDOW of its end it's taken to be
still uploading. After that, a session without any laps is skipped as having
no data upstream (e.g. it was cancelled), and any other is incomplete. Run it
again later; if the data doesn't exist upstream, --allow-incomplete exports it
with the missing parts recorded. --allow-incomplete-when-final does that only
once the session's results are final, so a scheduled export retries it until
then and stops after.

The exit status is 1 when a session failed with an error. Sessions skipped as
incomplete don't count, since the next run retries them.

An event's circuit info is built when its first session is exported, or a
later one if that fails. --circuit builds only the circuit info, from the
first finished session (or the one given) with car and position data, for
events that have none, or for all of them with --overwrite:

    infisical run -- uv run python -m app.archive 2018 r12 --circuit

Every run that exports sessions first exports the season's schedule, which the
API serves the season's events from, writing it only when it changed. Events
can move or be replaced during a season, so the scheduled export keeps the
current one up to date. --schedule exports only the schedule, e.g. to add a
past season's:

    infisical run -- uv run python -m app.archive 2018 --schedule
"""

import argparse
import logging
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import fastf1

from app.archive.archive import open_archive
from app.archive.export import IncompleteLoadError, export_circuit, export_schedule, export_session
from app.archive.models import StoredSchedule
from app.config import Settings
from app.fastf1_loader import install_request_timeouts, warn_if_no_f1_account
from app.schedule.services import CircuitInfoUnavailable, fastf1_season, get_event, get_schedule

logger = logging.getLogger("uvicorn.error")

# How long after an event --recent keeps checking its sessions: past the time
# their results take to become final (SETTLE_BUFFER), with room to catch up on
# runs that were missed.
RECENT = timedelta(days=7)


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


def _sessions(
    year: int,
    event_id: str | None,
    identifier: str | None,
    *,
    ended_since: date | None = None,
    schedule: StoredSchedule | None = None,
) -> list[tuple[str, str]]:
    """Sessions to export, of events that have started and, with ended_since,
    haven't ended before that day."""
    if identifier:
        return [(event_id, identifier)]
    if event_id:
        return [(event_id, s["identifier"]) for s in get_event(year, event_id, schedule)["sessions"]]
    return [
        (event["identifier"], s["identifier"])
        for event in get_schedule(year, schedule)["events"]
        if event["status"] != "upcoming"
        and (ended_since is None or date.fromisoformat(event["event_date_end"]) >= ended_since)
        for s in get_event(year, event["identifier"], schedule)["sessions"]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.archive", description="Export finished sessions into the archive.")
    parser.add_argument("year", type=int, nargs="?", help="defaults to the current year")
    parser.add_argument("event_id", nargs="?", help="e.g. r16 or t1")
    parser.add_argument("identifier", nargs="?", help="e.g. FP1, Q or R")
    parser.add_argument("--overwrite", action="store_true", help="export sessions that are already exported")
    parser.add_argument("--force", action="store_true", help="export sessions that may not be finished yet")
    parser.add_argument(
        "--allow-incomplete", action="store_true", help="export sessions FastF1 can only partly load"
    )
    parser.add_argument(
        "--allow-incomplete-when-final",
        action="store_true",
        help="export sessions FastF1 can only partly load once their results are final",
    )
    parser.add_argument(
        "--circuit", action="store_true", help="only build circuit info, for events that have none"
    )
    parser.add_argument(
        "--recent", action="store_true", help=f"only events under way or ended in the last {RECENT.days} days"
    )
    parser.add_argument("--schedule", action="store_true", help="only export the season's schedule")
    args = parser.parse_args(argv)
    if args.identifier and not args.event_id:
        parser.error("identifier requires event_id")
    if args.recent and (args.event_id or args.circuit):
        parser.error("--recent picks the events itself, and only exports sessions")
    if args.schedule and (args.event_id or args.circuit or args.recent):
        parser.error("--schedule only exports the season's schedule")
    now = datetime.now(timezone.utc)
    year = now.year if args.year is None else args.year

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = Settings()
    archive = open_archive(settings)
    if archive is None:
        parser.error("no archive configured: run through `infisical run --`, or set R2_BUCKET (and its credentials) or ARCHIVE_LOCAL_DIR")
    os.makedirs(settings.fastf1_cache_dir, exist_ok=True)
    fastf1.Cache.configure(cache_dir=settings.fastf1_cache_dir)
    install_request_timeouts(settings.upstream_connect_timeout_seconds, settings.upstream_read_timeout_seconds)
    warn_if_no_f1_account()
    # FastF1 logs every cache read at INFO; keep the export progress readable.
    # Only its console output is quieted: the export reads FastF1's DEBUG
    # records to notice parts that failed to load.
    fastf1.set_log_level(logging.WARNING)
    logging.getLogger("fastf1").propagate = False

    outcomes: Counter[str] = Counter()
    schedule = None
    if not args.circuit:
        try:
            # Only from FastF1's own backend: the others it falls back to can
            # have less detail, which shouldn't replace the exported schedule.
            schedule = fastf1_season(year, backend="fastf1")
            outcome = export_schedule(archive, schedule)
        except Exception:
            logger.exception("Failed to export the %s schedule", year)
            outcomes["failed"] += 1
        else:
            outcomes[f"schedule {outcome.value}"] += 1
    if args.circuit:
        for event_id, identifiers in _circuit_sources(year, args.event_id, args.identifier):
            try:
                outcome = export_circuit(archive, year, event_id, identifiers, overwrite=args.overwrite)
            except CircuitInfoUnavailable as exc:
                logger.error("No circuit info for %s %s: %s", year, event_id, exc)
                outcomes["failed"] += 1
            except Exception:
                logger.exception("Failed to export circuit info for %s %s", year, event_id)
                outcomes["failed"] += 1
            else:
                outcomes[outcome.value] += 1
    elif not args.schedule:
        ended_since = (now - RECENT).date() if args.recent else None
        sessions = _sessions(year, args.event_id, args.identifier, ended_since=ended_since, schedule=schedule)
        for event_id, identifier in sessions:
            try:
                outcome = export_session(
                    archive,
                    year,
                    event_id,
                    identifier,
                    force=args.force,
                    overwrite=args.overwrite,
                    allow_incomplete=args.allow_incomplete,
                    allow_incomplete_when_final=args.allow_incomplete_when_final,
                )
            except IncompleteLoadError as exc:
                logger.error("Not exporting %s %s %s: %s", year, event_id, identifier, exc)
                outcomes["incomplete"] += 1
            except Exception:
                logger.exception("Failed to export %s %s %s", year, event_id, identifier)
                outcomes["failed"] += 1
            else:
                outcomes[outcome.value] += 1

    logger.info("Done: %s", ", ".join(f"{count} {name}" for name, count in sorted(outcomes.items())) or "nothing to export")
    return 1 if outcomes["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
