from datetime import date, datetime, timezone

import pandas as pd
import pytest
from freezegun import freeze_time

from app.schedule.services import _event_status


NOW = "2026-06-21 12:00:00"


@freeze_time(NOW)
def test_event_status_none():
    assert _event_status(None) == "unknown"


@freeze_time(NOW)
def test_event_status_future_aware():
    future = datetime(2026, 12, 1, 15, 0, tzinfo=timezone.utc)
    assert _event_status(future) == "upcoming"


@freeze_time(NOW)
def test_event_status_past_aware():
    past = datetime(2024, 5, 1, 15, 0, tzinfo=timezone.utc)
    assert _event_status(past) == "completed"


@freeze_time(NOW)
def test_event_status_naive_datetime_treated_as_utc():
    naive_future = datetime(2026, 12, 1, 15, 0)
    assert _event_status(naive_future) == "upcoming"


@freeze_time(NOW)
def test_event_status_date_only_combined_at_midnight():
    assert _event_status(date(2024, 1, 1)) == "completed"


@freeze_time(NOW)
@pytest.mark.parametrize(
    "ts, expected",
    [
        (pd.Timestamp("2026-12-01 15:00:00"), "upcoming"),
        (pd.Timestamp("2024-05-01 15:00:00"), "completed"),
    ],
)
def test_event_status_pandas_timestamp(ts, expected):
    assert _event_status(ts) == expected
