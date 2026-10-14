from datetime import date, datetime, timezone

import pytest

from app.archive import __main__ as cli
from app.archive.export import ExportOutcome, IncompleteLoadError

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
def run(monkeypatch, tmp_path):
    """Runs the command against a local archive, with the sessions to export
    and each one's outcome (or exception) given by the test."""
    monkeypatch.setenv("ARCHIVE_LOCAL_DIR", str(tmp_path / "archive"))
    monkeypatch.setenv("FASTF1_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("R2_BUCKET", raising=False)
    monkeypatch.setattr(cli, "install_request_timeouts", lambda *args: None)

    def run(argv, outcomes):
        listed = []
        exported = []

        def sessions(year, event_id, identifier, *, ended_since=None):
            listed.append((year, ended_since))
            return list(outcomes)

        def export_session(archive, year, event_id, identifier, **kwargs):
            exported.append((year, event_id, identifier, kwargs))
            outcome = outcomes[(event_id, identifier)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(cli, "_sessions", sessions)
        monkeypatch.setattr(cli, "export_session", export_session)
        return cli.main(argv), listed, exported

    return run


def test_defaults_to_the_current_season(run):
    status, listed, _ = run([], {("r1", "R"): ExportOutcome.EXPORTED})
    assert status == 0
    assert listed == [(datetime.now(timezone.utc).year, None)]


def test_recent_checks_events_ended_in_the_last_week(run):
    _, listed, _ = run(["--recent"], {("r1", "R"): ExportOutcome.UNCHANGED})
    now = datetime.now(timezone.utc)
    assert listed == [(now.year, (now - cli.RECENT).date())]


@pytest.mark.parametrize("argv", [["--recent", "2025", "r16"], ["--recent", "--circuit"]])
def test_recent_doesnt_take_an_event(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)


def test_passes_allow_incomplete_when_final(run):
    _, _, exported = run(["2025", "--allow-incomplete-when-final"], {("r1", "R"): ExportOutcome.EXPORTED})
    assert exported[0][3]["allow_incomplete_when_final"] is True
    assert exported[0][3]["allow_incomplete"] is False


def test_incomplete_sessions_and_no_data_dont_fail_the_run(run):
    status, _, exported = run(["2025"], {
        ("r1", "FP3"): ExportOutcome.NO_DATA,
        ("r1", "S"): IncompleteLoadError(["position data for 2 of 20 drivers"]),
        ("r1", "R"): ExportOutcome.EXPORTED,
    })
    assert status == 0
    assert len(exported) == 3


def test_errors_fail_the_run(run):
    status, _, exported = run(["2025"], {
        ("r1", "S"): RuntimeError("R2 is down"),
        ("r1", "R"): ExportOutcome.EXPORTED,
    })
    assert status == 1
    assert len(exported) == 2
