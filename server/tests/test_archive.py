import gzip
import hashlib
import io
import json
import socket
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from pydantic import SecretStr

from app.archive.archive import (
    SessionArchive,
    circuit_key,
    driver_laps_key,
    lap_telemetry_key,
    open_archive,
    schedule_key,
    session_key,
)
from app.archive.models import (
    StoredCarData,
    StoredCircuit,
    StoredCorner,
    StoredDriverLaps,
    StoredEvent,
    StoredLap,
    StoredLapTelemetry,
    StoredPosData,
    StoredSchedule,
    StoredScheduleEvent,
    StoredScheduleSession,
    StoredSession,
)
from app.archive.store import (
    KEEPALIVE_SOCKET_OPTIONS,
    READ_TIMEOUT_SECONDS,
    WRITE_TIMEOUT_SECONDS,
    LocalBlobStore,
    R2BlobStore,
)

_CEST = timezone(timedelta(hours=2))


def _session(**overrides) -> StoredSession:
    values = dict(
        exported_at=datetime(2025, 9, 8, tzinfo=timezone.utc),
        fastf1_version="3.8.2",
        results_final=True,
        year=2025,
        event_id="r16",
        identifier="R",
        name="Race",
        start_utc=datetime(2025, 9, 7, 13, tzinfo=timezone.utc),
        event=StoredEvent(
            round=16, name="Italian Grand Prix", official_name=None, country="Italy",
            location="Monza", date="2025-09-07", format="conventional",
        ),
        drivers=[],
        lap_drivers=["VER"],
        fastest_lap=None,
        weather=None,
    )
    values.update(overrides)
    return StoredSession(**values)


def _schedule_event(**overrides) -> StoredScheduleEvent:
    values = dict(
        round=16,
        event_id="r16",
        name="Italian Grand Prix",
        official_name="FORMULA 1 PIRELLI GRAN PREMIO D'ITALIA 2025",
        country="Italy",
        location="Monza",
        date="2025-09-07",
        format="conventional",
        sessions=[
            StoredScheduleSession(name="Practice 1", start=datetime(2025, 9, 5, 13, 30, tzinfo=_CEST)),
            StoredScheduleSession(name="Qualifying", start=datetime(2025, 9, 6, 16, tzinfo=_CEST)),
            StoredScheduleSession(name="Race", start=datetime(2025, 9, 7, 15, tzinfo=_CEST)),
        ],
    )
    values.update(overrides)
    return StoredScheduleEvent(**values)


def _schedule(*events: StoredScheduleEvent, **overrides) -> StoredSchedule:
    values = dict(
        exported_at=datetime(2025, 9, 8, tzinfo=timezone.utc),
        fastf1_version="3.8.2",
        year=2025,
        events=list(events) or [_schedule_event()],
    )
    values.update(overrides)
    return StoredSchedule(**values)


def _lap(**overrides) -> StoredLap:
    values = {name: None for name in StoredLap.model_fields}
    values.update(lap_number=1, is_personal_best=False, has_telemetry=True)
    values.update(overrides)
    return StoredLap(**values)


def _telemetry(driver="VER", lap_number=10) -> StoredLapTelemetry:
    return StoredLapTelemetry(
        driver=driver,
        lap_number=lap_number,
        car=StoredCarData(
            time=[0.0, 0.25], speed=[300.0, None], throttle=[100.0, 99.0], brake=[False, True],
            gear=[8, 7], drs=[12, 0], rpm=[11000.0, 10800.0], distance=[0.0, 21.0],
        ),
        pos=StoredPosData(time=[0.0, 0.2], x=[1.5, 2.5], y=[-3.0, None]),
    )


@pytest.fixture
def archive(tmp_path):
    return SessionArchive(LocalBlobStore(str(tmp_path)))


def test_keys():
    assert session_key(2025, "R16", "r") == "v1/2025/r16/R/session.json.gz"
    assert driver_laps_key(2025, "r16", "Q", "ver") == "v1/2025/r16/Q/laps/VER.json.gz"
    assert lap_telemetry_key(2025, "r16", "Q", "VER", 7) == "v1/2025/r16/Q/telemetry/VER/7.json.gz"
    assert circuit_key(2025, "t1") == "v1/2025/t1/circuit.json.gz"
    assert schedule_key(2025) == "v1/2025/schedule.json.gz"


def test_session_named_identifier_key():
    assert session_key(2023, "r4", "Sprint Shootout") == "v1/2023/r4/SPRINT_SHOOTOUT/session.json.gz"


@pytest.mark.parametrize(
    "build",
    [
        lambda: session_key(2025, "../r16", "R"),
        lambda: session_key(2025, "r16", "R/x"),
        lambda: driver_laps_key(2025, "r16", "R", "VER.."),
        lambda: lap_telemetry_key(2025, "r16", "R", "", 1),
    ],
)
def test_keys_reject_unsafe_segments(build):
    with pytest.raises(ValueError):
        build()


def test_missing_objects_are_none(archive):
    assert archive.get_session(2025, "r16", "R") is None
    assert archive.get_driver_laps(2025, "r16", "R", "VER") is None
    assert archive.get_lap_telemetry(2025, "r16", "R", "VER", 1) is None
    assert archive.get_circuit(2025, "r16") is None
    assert archive.get_schedule(2025) is None


def test_round_trips(archive):
    session = _session()
    laps = StoredDriverLaps(driver="VER", driver_number="1", laps=[_lap(lap_number=1, qualifying_part=2)])
    telemetry = _telemetry()
    circuit = StoredCircuit(
        rotation=95.0,
        corners=[StoredCorner(x=1.0, y=2.0, number=1, angle=90.0, distance=500.0)],
        marshal_sectors=[],
        sector_distances=[1890.4, 3699.3],
    )

    archive.put_session(session)
    archive.put_driver_laps(2025, "r16", "R", laps)
    archive.put_lap_telemetry(2025, "r16", "R", telemetry)
    archive.put_circuit(2025, "r16", circuit)
    archive.put_schedule(_schedule())

    assert archive.get_session(2025, "r16", "R") == session
    assert archive.get_driver_laps(2025, "r16", "R", "VER") == laps
    assert archive.get_lap_telemetry(2025, "r16", "R", "VER", 10) == telemetry
    assert archive.get_circuit(2025, "r16") == circuit
    assert archive.get_schedule(2025) == _schedule()


def test_objects_are_gzipped_json(tmp_path, archive):
    archive.put_lap_telemetry(2025, "r16", "R", _telemetry())
    raw = (tmp_path / "v1/2025/r16/R/telemetry/VER/10.json.gz").read_bytes()
    body = json.loads(gzip.decompress(raw))
    assert body["format_version"] == 1
    assert body["car"]["speed"] == [300.0, None]


def test_encoding_is_deterministic(tmp_path, archive):
    path = tmp_path / "v1/2025/r16/R/telemetry/VER/10.json.gz"
    archive.put_lap_telemetry(2025, "r16", "R", _telemetry())
    first = path.read_bytes()
    archive.put_lap_telemetry(2025, "r16", "R", _telemetry())
    assert path.read_bytes() == first


def test_local_store_overwrites_and_leaves_no_temp_files(tmp_path):
    store = LocalBlobStore(str(tmp_path))
    store.put("a/b.bin", b"one", "application/octet-stream")
    store.put("a/b.bin", b"two", "application/octet-stream")
    assert store.get("a/b.bin") == b"two"
    assert [p.name for p in (tmp_path / "a").iterdir()] == ["b.bin"]


def test_local_store_rejects_keys_outside_root(tmp_path):
    store = LocalBlobStore(str(tmp_path / "root"))
    with pytest.raises(ValueError):
        store.get("../outside")


@pytest.fixture
def r2():
    client = boto3.client(
        "s3", region_name="auto", endpoint_url="https://account.r2.cloudflarestorage.com",
        aws_access_key_id="key", aws_secret_access_key="secret",
    )
    with Stubber(client) as stubber:
        yield R2BlobStore("account", "key", "secret", "formalytx-data", client=client), stubber


def test_r2_get(r2):
    store, stubber = r2
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(io.BytesIO(b"data"), 4)},
        {"Bucket": "formalytx-data", "Key": "v1/a.json.gz"},
    )
    assert store.get("v1/a.json.gz") == b"data"


def test_r2_get_missing_is_none(r2):
    store, stubber = r2
    stubber.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    assert store.get("v1/missing.json.gz") is None


def test_r2_get_other_errors_raise(r2):
    store, stubber = r2
    stubber.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)
    with pytest.raises(Exception, match="AccessDenied"):
        store.get("v1/a.json.gz")


def test_r2_reads_give_up_sooner_than_uploads():
    store = R2BlobStore("account", "key", "secret", "formalytx-data")
    assert store._reads.meta.config.read_timeout == READ_TIMEOUT_SECONDS
    assert store._writes.meta.config.read_timeout == WRITE_TIMEOUT_SECONDS
    assert READ_TIMEOUT_SECONDS < WRITE_TIMEOUT_SECONDS


def test_r2_connections_probe_while_idle():
    store = R2BlobStore("account", "key", "secret", "formalytx-data")
    with socket.create_server(("127.0.0.1", 0)) as server:
        url = f"http://127.0.0.1:{server.getsockname()[1]}"
        for client in (store._reads, store._writes):
            # Open a connection the way a request would: from the client's pool.
            conn = client._endpoint.http_session._manager.connection_from_url(url)._get_conn()
            conn.connect()
            try:
                assert conn.sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
                for level, option, value in KEEPALIVE_SOCKET_OPTIONS:
                    assert conn.sock.getsockopt(level, option) == value
            finally:
                conn.close()


def test_r2_put(r2):
    store, stubber = r2
    stubber.add_response(
        "put_object",
        {},
        {"Bucket": "formalytx-data", "Key": "v1/a.json.gz", "Body": b"data", "ContentType": "application/gzip"},
    )
    store.put("v1/a.json.gz", b"data", "application/gzip")
    stubber.assert_no_pending_responses()


def _settings(**overrides):
    values = dict(
        r2_account_id="", r2_access_key_id="", r2_secret_access_key=SecretStr(""),
        r2_bucket="", archive_local_dir="",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_open_archive_disabled_by_default():
    assert open_archive(_settings()) is None


def test_open_archive_local(tmp_path):
    archive = open_archive(_settings(archive_local_dir=str(tmp_path)))
    archive.put_session(_session())
    assert archive.get_session(2025, "r16", "R") is not None


def test_open_archive_r2_requires_credentials():
    with pytest.raises(ValueError, match="r2_account_id, r2_secret_access_key"):
        open_archive(_settings(r2_bucket="formalytx-data", r2_access_key_id="key"))


def test_open_archive_prefers_r2(tmp_path):
    archive = open_archive(_settings(
        r2_bucket="formalytx-data", r2_account_id="account", r2_access_key_id="key",
        r2_secret_access_key=SecretStr("secret"), archive_local_dir=str(tmp_path),
    ))
    assert isinstance(archive._store, R2BlobStore)


def test_put_skips_objects_stored_already(tmp_path, archive):
    archive.put_session(_session())
    digests = archive.digests(2025, "r16", "R")
    assert list(digests) == ["v1/2025/r16/R/session.json.gz"]
    assert not archive.put_session(_session(), unless=digests)
    assert archive.put_session(_session(lap_drivers=["VER", "NOR"]), unless=digests)
    assert archive.get_session(2025, "r16", "R").lap_drivers == ["VER", "NOR"]


def test_digests_cover_the_session_and_its_event_circuit(archive):
    archive.put_session(_session())
    archive.put_session(_session(identifier="Q", name="Qualifying"))
    archive.put_lap_telemetry(2025, "r16", "R", _telemetry())
    archive.put_circuit(2025, "r16", StoredCircuit(rotation=0.0, corners=[], marshal_sectors=[], sector_distances=[]))
    assert sorted(archive.digests(2025, "r16", "R")) == [
        "v1/2025/r16/R/session.json.gz",
        "v1/2025/r16/R/telemetry/VER/10.json.gz",
        "v1/2025/r16/circuit.json.gz",
    ]
    assert archive.digests(2025, "r1", "R") == {}


def test_local_digests_are_md5(tmp_path):
    store = LocalBlobStore(str(tmp_path))
    store.put("v1/a/b.json.gz", b"data", "application/gzip")
    store.put("v1/ab.json.gz", b"other", "application/gzip")
    assert store.digests("v1/a/") == {"v1/a/b.json.gz": hashlib.md5(b"data").hexdigest()}
    assert sorted(store.digests("v1/a")) == ["v1/a/b.json.gz", "v1/ab.json.gz"]


def test_r2_digests_are_etags(r2):
    store, stubber = r2
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "v1/a/b.json.gz", "ETag": '"8d777f385d3dfec8815d20f7496026dc"'}], "IsTruncated": False},
        {"Bucket": "formalytx-data", "Prefix": "v1/a/"},
    )
    assert store.digests("v1/a/") == {"v1/a/b.json.gz": "8d777f385d3dfec8815d20f7496026dc"}


def test_schedule_keeps_local_start_times(archive):
    archive.put_schedule(_schedule())
    start = archive.get_schedule(2025).events[0].sessions[0].start
    assert (start.hour, start.utcoffset()) == (13, timedelta(hours=2))
