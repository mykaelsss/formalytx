import pandas as pd
import pytest
from fastapi import HTTPException

from app.sessions.services import _parse_selected_laps
from app.utils import format_lap_time


@pytest.mark.parametrize("td", [None, pd.NaT])
def testformat_lap_time_missing(td):
    assert format_lap_time(td) is None


@pytest.mark.parametrize(
    "td, expected",
    [
        (pd.Timedelta(minutes=1, seconds=23, milliseconds=456), "1:23.456"),
        (pd.Timedelta(seconds=5, milliseconds=100), "0:05.100"),
        (pd.Timedelta(minutes=2), "2:00.000"),
        (pd.Timedelta(seconds=59, milliseconds=999), "0:59.999"),
        (pd.Timedelta(minutes=1, seconds=0, milliseconds=1), "1:00.001"),
    ],
)
def testformat_lap_time_formats(td, expected):
    assert format_lap_time(td) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("VER:1", [("VER", [1])]),
        ("VER:1,2,3", [("VER", [1, 2, 3])]),
        ("VER:1|HAM:2", [("VER", [1]), ("HAM", [2])]),
        ("VER:1|", [("VER", [1])]),
        ("|VER:1", [("VER", [1])]),
        (" VER : 1 , 2 ", [("VER", [1, 2])]),
        ("VER:1,,2", [("VER", [1, 2])]),
    ],
)
def test_parse_selected_laps_valid(raw, expected):
    assert _parse_selected_laps(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "|", " | "])
def test_parse_selected_laps_empty(raw):
    with pytest.raises(HTTPException) as exc:
        _parse_selected_laps(raw)
    assert exc.value.status_code == 400
    assert "No laps selected" in exc.value.detail


@pytest.mark.parametrize("raw", ["VER1", "VER1|HAM:2"])
def test_parse_selected_laps_missing_colon(raw):
    with pytest.raises(HTTPException) as exc:
        _parse_selected_laps(raw)
    assert exc.value.status_code == 400
    assert "Malformed" in exc.value.detail


def test_parse_selected_laps_empty_driver():
    with pytest.raises(HTTPException) as exc:
        _parse_selected_laps(":1")
    assert exc.value.status_code == 400
    assert "Malformed" in exc.value.detail


def test_parse_selected_laps_no_lap_numbers():
    with pytest.raises(HTTPException) as exc:
        _parse_selected_laps("VER:")
    assert exc.value.status_code == 400
    assert "No lap numbers given" in exc.value.detail


@pytest.mark.parametrize("raw", ["VER:abc", "VER:1,abc", "VER:1.5"])
def test_parse_selected_laps_non_integer_lap(raw):
    with pytest.raises(HTTPException) as exc:
        _parse_selected_laps(raw)
    assert exc.value.status_code == 400
    assert "Invalid lap number" in exc.value.detail
