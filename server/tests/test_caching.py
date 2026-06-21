from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from app import caching
from app.caching import (
    LIVE,
    PAST_SEASON,
    SETTLING,
    cache_control_for,
    cache_control_for_year,
)


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
