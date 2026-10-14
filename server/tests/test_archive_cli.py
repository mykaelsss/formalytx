from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.archive import __main__ as cli
from app.archive.export import ExportOutcome

SCHEDULE = {"events": [
    {"identifier": "r15", "status": "completed", "event_date_end": "2025-08-31"},
    {"identifier": "r16", "status": "completed", "event_date_end": "2025-09-07"},
    {"identifier": "r17", "status": "in_progress", "event_date_end": "2025-09-21"},
    {"identifier": "r18", "status": "upcoming", "event_date_end": "2025-10-05"},
]}


@pytest.fixture
def schedule(monkeypatch):
    monkeypatch.setattr(cli, "get_schedule", lambda year: SCHEDULE)
    monkeypatch.setattr(cli, "get_event", lambda year, event_id: {"sessions": [{"identifier": "Q"}, {"identifier": "R"}]})


def test_sessions_of_every_started_event(schedule):
    assert [e for e, _ in cli._sessions(2025, None, None)] == ["r15", "r15", "r16", "r16", "r17", "r17"]


def test_sessions_of_events_ended_since(schedule):
    sessions = cli._sessions(2025, None, None, ended_since=date(2025, 9, 7))
    assert sessions == [("r16", "Q"), ("r16", "R"), ("r17", "Q"), ("r17", "R")]


@pytest.fixture
def exports(monkeypatch):
    """Runs main without FastF1 or an archive, recording what it exports."""
    exported = []
    monkeypatch.setattr(cli, "open_archive", lambda settings: SimpleNamespace())
    monkeypatch.setattr(cli.fastf1.Cache, "enable_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "install_request_timeouts", lambda *args: None)
    monkeypatch.setattr(cli.os, "makedirs", lambda *args, **kwargs: None)

    def sessions(year, event_id, identifier, *, ended_since=None):
        exported.append((year, ended_since))
        return [("r16", "R")]

    monkeypatch.setattr(cli, "_sessions", sessions)
    monkeypatch.setattr(cli, "export_session", lambda *args, **kwargs: ExportOutcome.UNCHANGED)
    return exported


def test_main_defaults_to_the_current_year(exports):
    assert cli.main([]) == 0
    assert exports == [(datetime.now(timezone.utc).year, None)]


def test_main_recent_checks_events_ended_in_the_last_week(exports):
    assert cli.main(["--recent"]) == 0
    assert exports == [(datetime.now(timezone.utc).year, (datetime.now(timezone.utc) - cli.RECENT).date())]


def test_main_no_data_isnt_a_failure(exports, monkeypatch):
    monkeypatch.setattr(cli, "export_session", lambda *args, **kwargs: ExportOutcome.NO_DATA)
    assert cli.main(["2025"]) == 0


@pytest.mark.parametrize("argv", [["--recent", "2025", "r16"], ["--recent", "--circuit"]])
def test_main_recent_doesnt_take_an_event(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)
