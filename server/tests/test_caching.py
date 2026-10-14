import logging
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app import caching
from app.archive import reader as archive_reader
from app.archive.archive import SessionArchive
from app.archive.models import StoredEvent, StoredScheduleSession
from app.archive.reader import ArchiveReader
from app.archive.store import LocalBlobStore
from app.caching import (
    LIVE,
    PAST_SEASON,
    SETTLING,
    cache_control_for,
    cache_control_for_year,
)
from app.schedule import services as schedule_services
from tests.test_archive import _schedule, _schedule_event, _session


SESSION_END = datetime(2025, 6, 15, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def fixed_session_end(monkeypatch):
    monkeypatch.setattr(caching, "_session_end", lambda *_: SESSION_END)


@freeze_time("2025-06-15 14:30:00")
def test_cache_control_live_before_session_end(fixed_session_end):
    assert cache_control_for(2025, "r5", "R") == LIVE


@freeze_time("2025-06-15 15:30:00")
def test_cache_control_settling_just_after_end(fixed_session_end):
    assert cache_control_for(2025, "r5", "R") == SETTLING


@freeze_time("2025-06-17 14:59:00")
def test_cache_control_settling_inside_buffer(fixed_session_end):
    assert cache_control_for(2025, "r5", "R") == SETTLING


@freeze_time("2025-06-17 15:01:00")
def test_cache_control_past_season_after_buffer(fixed_session_end):
    assert cache_control_for(2025, "r5", "R") == PAST_SEASON


def test_cache_control_falls_back_when_session_end_raises(monkeypatch):
    def boom(*_):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(caching, "_session_end", boom)
    assert cache_control_for(2025, "r5", "R") == SETTLING


def test_cache_control_falls_back_when_session_end_returns_none(monkeypatch):
    monkeypatch.setattr(caching, "_session_end", lambda *_: None)
    assert cache_control_for(2025, "r5", "R") == SETTLING


@freeze_time("2026-06-21 00:00:00")
def test_cache_control_for_year_past():
    assert cache_control_for_year(2024) == PAST_SEASON


@freeze_time("2026-06-21 00:00:00")
def test_cache_control_for_year_current():
    assert cache_control_for_year(2026) == SETTLING


@freeze_time("2026-06-21 00:00:00")
def test_cache_control_for_year_future():
    assert cache_control_for_year(2027) == SETTLING


WEEKEND = _schedule_event(
    round=5,
    event_id="r5",
    sessions=[
        StoredScheduleSession(name="Practice 1", start=datetime(2024, 5, 3, 11, 30, tzinfo=timezone.utc)),
        StoredScheduleSession(name="Practice 2", start=datetime(2024, 5, 3, 15, tzinfo=timezone.utc)),
        StoredScheduleSession(name="Practice 3", start=datetime(2024, 5, 4, 10, 30, tzinfo=timezone.utc)),
        StoredScheduleSession(name="Qualifying", start=datetime(2024, 5, 4, 14, tzinfo=timezone.utc)),
        StoredScheduleSession(name="Race", start=datetime(2024, 5, 5, 13, tzinfo=timezone.utc)),
    ],
)


@pytest.fixture
def stub_event(monkeypatch):
    def _stub(event=WEEKEND):
        monkeypatch.setattr(caching, "season", lambda year: _schedule(event, year=year))

    return _stub


def test_session_end_resolves_practice(stub_event):
    stub_event()
    assert caching._session_end(2024, "r5", "FP1") == datetime(
        2024, 5, 3, 12, 30, tzinfo=timezone.utc
    )


def test_session_end_uses_per_session_duration(stub_event):
    stub_event()
    assert caching._session_end(2024, "r5", "R") == datetime(
        2024, 5, 5, 15, 0, tzinfo=timezone.utc
    )


def test_session_end_identifier_is_case_insensitive(stub_event):
    stub_event()
    assert caching._session_end(2024, "r5", "fp1") == caching._session_end(
        2024, "r5", "FP1"
    )


def test_session_end_attaches_utc_to_naive_start(stub_event):
    stub_event(WEEKEND.model_copy(update={
        "sessions": [StoredScheduleSession(name="Practice 1", start=datetime(2024, 5, 3, 11, 30))],
    }))
    assert caching._session_end(2024, "r5", "FP1") == datetime(
        2024, 5, 3, 12, 30, tzinfo=timezone.utc
    )


def test_session_end_converts_local_start_to_utc(stub_event):
    local = timezone(timedelta(hours=-4))
    stub_event(WEEKEND.model_copy(update={
        "sessions": [StoredScheduleSession(name="Practice 1", start=datetime(2024, 5, 3, 7, 30, tzinfo=local))],
    }))
    end = caching._session_end(2024, "r5", "FP1")
    assert end == datetime(2024, 5, 3, 12, 30, tzinfo=timezone.utc)
    assert end.tzinfo == timezone.utc


def test_testing_day_ends_after_the_day(stub_event):
    stub_event(_schedule_event(
        round=0, event_id="t1", format="testing",
        sessions=[StoredScheduleSession(name="Practice 1", start=datetime(2025, 2, 26, 7, tzinfo=timezone.utc))],
    ))
    assert caching._session_end(2025, "t1", "FP1") == datetime(2025, 2, 26, 16, tzinfo=timezone.utc)


def test_session_end_none_when_session_not_in_event(stub_event):
    stub_event()
    assert caching._session_end(2024, "r5", "SQ") is None


def test_session_end_none_for_unknown_identifier(stub_event):
    stub_event()
    assert caching._session_end(2024, "r5", "XYZ") is None


@freeze_time("2026-06-21 12:00:00")
def test_cache_control_for_past_event_through_real_session_end(stub_event):
    stub_event()
    assert cache_control_for(2024, "r5", "FP1") == PAST_SEASON


def test_cache_control_for_event_not_in_the_season(stub_event, caplog):
    stub_event()
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        assert cache_control_for(2024, "r30", "R") == SETTLING
    assert "falling back to SETTLING" in caplog.text


def test_cache_control_for_logs_when_identifier_is_not_a_string(stub_event, caplog):
    stub_event()
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        assert cache_control_for(2024, "r5", 1) == SETTLING
    assert "falling back to SETTLING" in caplog.text


@pytest.mark.parametrize("directive", [LIVE, SETTLING, PAST_SEASON])
def test_no_directive_grants_browsers_a_ttl(directive):
    assert "max-age=0" in directive or "no-cache" in directive


def test_directives_match_policy():
    assert LIVE == "public, no-cache"
    assert SETTLING == "public, max-age=0, s-maxage=3600"
    assert PAST_SEASON == "public, max-age=0, s-maxage=604800"


@pytest.fixture
def archive(tmp_path):
    archive = SessionArchive(LocalBlobStore(str(tmp_path)))
    archive_reader.configure(ArchiveReader(archive, workers=4))
    yield archive
    archive_reader.configure(None)


@pytest.fixture
def no_fastf1_schedule(monkeypatch):
    def _fail(*_, **__):
        raise AssertionError("read FastF1's schedule")

    monkeypatch.setattr(schedule_services.fastf1, "get_event_schedule", _fail)


def test_archived_session_ends_without_fastf1(archive, no_fastf1_schedule):
    archive.put_session(_session(identifier="FP1", name="Practice 1", start_utc=datetime(2025, 9, 5, 11, 30, tzinfo=timezone.utc)))
    assert caching._session_end(2025, "r16", "fp1") == datetime(2025, 9, 5, 12, 30, tzinfo=timezone.utc)


def test_archived_session_uses_per_session_duration(archive, no_fastf1_schedule):
    archive.put_session(_session())
    assert caching._session_end(2025, "r16", "R") == datetime(2025, 9, 7, 15, 0, tzinfo=timezone.utc)


def test_archived_testing_day_runs_all_day(archive, no_fastf1_schedule):
    archive.put_session(_session(
        event_id="t1", identifier="1", name="Practice 1",
        start_utc=datetime(2025, 2, 26, 7, tzinfo=timezone.utc),
        event=StoredEvent(
            round=0, name="Pre-Season Testing", official_name=None, country="Bahrain",
            location="Sakhir", date="2025-02-28", format="testing",
        ),
    ))
    assert caching._session_end(2025, "t1", "1") == datetime(2025, 2, 26, 16, tzinfo=timezone.utc)


def test_archived_session_without_start_has_no_end(archive, no_fastf1_schedule):
    archive.put_session(_session(start_utc=None))
    assert caching._session_end(2025, "r16", "R") is None


@freeze_time("2025-09-08 12:00:00")
def test_cache_control_for_archived_session_still_settling(archive, no_fastf1_schedule):
    archive.put_session(_session(results_final=False))
    assert cache_control_for(2025, "r16", "R") == SETTLING


@freeze_time("2026-06-21 12:00:00")
def test_cache_control_for_archived_past_session(archive, no_fastf1_schedule):
    archive.put_session(_session())
    assert cache_control_for(2025, "r16", "R") == PAST_SEASON


def test_unarchived_session_ends_from_the_archived_schedule(archive, no_fastf1_schedule):
    archive.put_schedule(_schedule(WEEKEND, year=2024))
    assert caching._session_end(2024, "r5", "FP1") == datetime(2024, 5, 3, 12, 30, tzinfo=timezone.utc)
