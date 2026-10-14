from datetime import datetime, timezone

import pytest

from app.archive import __main__ as cli
from app.archive.export import ExportOutcome, IncompleteLoadError


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

        def sessions(year, event_id, identifier):
            listed.append(year)
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
    assert listed == [datetime.now(timezone.utc).year]


def test_passes_allow_incomplete_when_final(run):
    _, _, exported = run(["2025", "--allow-incomplete-when-final"], {("r1", "R"): ExportOutcome.EXPORTED})
    assert exported[0][3]["allow_incomplete_when_final"] is True
    assert exported[0][3]["allow_incomplete"] is False


def test_incomplete_sessions_dont_fail_the_run(run):
    status, _, exported = run(["2025"], {
        ("r1", "S"): IncompleteLoadError(["position data for 2 of 20 drivers"]),
        ("r1", "R"): ExportOutcome.EXPORTED,
    })
    assert status == 0
    assert len(exported) == 2


def test_errors_fail_the_run(run):
    status, _, exported = run(["2025"], {
        ("r1", "S"): RuntimeError("R2 is down"),
        ("r1", "R"): ExportOutcome.EXPORTED,
    })
    assert status == 1
    assert len(exported) == 2
