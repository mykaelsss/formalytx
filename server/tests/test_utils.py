import pytest
from fastapi import HTTPException

from app.utils import parse_event_id


@pytest.mark.parametrize(
    "event_id, expected",
    [
        ("t1", ("test", 1)),
        ("r5", ("race", 5)),
        ("r12", ("race", 12)),
        ("t24", ("test", 24)),
    ],
)
def test_parse_event_id_valid(event_id, expected):
    assert parse_event_id(event_id) == expected


@pytest.mark.parametrize("event_id", ["", "x3", "5", "R1", "T1"])
def test_parse_event_id_bad_prefix(event_id):
    with pytest.raises(HTTPException) as exc:
        parse_event_id(event_id)
    assert exc.value.status_code == 404


@pytest.mark.parametrize("event_id", ["r", "rabc", "t", "t1a"])
def test_parse_event_id_non_integer_number(event_id):
    with pytest.raises(HTTPException) as exc:
        parse_event_id(event_id)
    assert exc.value.status_code == 404


@pytest.mark.parametrize("event_id", ["r0", "t0", "r-1"])
def test_parse_event_id_non_positive_number(event_id):
    with pytest.raises(HTTPException) as exc:
        parse_event_id(event_id)
    assert exc.value.status_code == 404
