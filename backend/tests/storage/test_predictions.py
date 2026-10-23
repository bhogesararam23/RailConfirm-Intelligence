"""Tests for the opt-in prediction history.

These are privacy tests as much as storage tests: what matters is not that a row round-
trips, but that an identifier can never become a row, that retention is enforceable, and
that a row the code does not understand is refused instead of guessed at.
"""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from railconfirm.storage.predictions import (
    SCHEMA_VERSION,
    PredictionStorageError,
    PredictionStore,
    assert_storeable,
)

PREDICTION_AT = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
RECORDED_AT = datetime(2026, 10, 21, 9, 0, 30, tzinfo=UTC)


def payload(**overrides) -> dict:
    base = {
        "prediction_id": "3f2a1c9e-7b6d-4e5f-8a1b-2c3d4e5f6a7b",
        "target": "final_chart_cnf",
        "prediction_at": PREDICTION_AT.isoformat(),
        "model_version": "no_model_v0",
        "registry_status": "no_active_version",
        "evidence_coverage": "insufficient",
        "is_supported": False,
        "passenger_count": 2,
        "passenger_outcomes": [
            {
                "passenger_ref": "1",
                "original_status": "GNWL/41",
                "current_status": "GNWL/38",
                "p_cnf": None,
                "abstention_reason": "no_trained_model",
            },
            {
                "passenger_ref": "2",
                "original_status": "GNWL/41",
                "current_status": "GNWL/38",
                "p_cnf": None,
                "abstention_reason": "no_trained_model",
            },
        ],
        "limitations": ["No trained model is available."],
    }
    base.update(overrides)
    return base


@pytest.fixture
def store(tmp_path: Path) -> PredictionStore:
    instance = PredictionStore(tmp_path / "history" / "predictions.sqlite3")
    yield instance
    instance.close()


def save(
    store: PredictionStore,
    *,
    prediction_id: str | None = None,
    model_version: str = "no_model_v0",
    recorded_at: datetime | None = None,
    prediction_at: datetime = PREDICTION_AT,
    payload_body: dict | None = None,
) -> None:
    identifier = prediction_id or str(payload()["prediction_id"])
    store.save(
        prediction_id=identifier,
        payload=(
            payload_body
            if payload_body is not None
            else {**payload(), "prediction_id": identifier}
        ),
        target="final_chart_cnf",
        model_version=model_version,
        prediction_at=prediction_at,
        recorded_at=recorded_at or RECORDED_AT,
    )


def test_a_saved_report_reads_back_with_its_bookkeeping(store: PredictionStore) -> None:
    save(store)
    stored = store.get(payload()["prediction_id"], now=RECORDED_AT)
    assert stored is not None
    assert stored.payload["passenger_count"] == 2
    assert stored.target == "final_chart_cnf"
    assert stored.model_version == "no_model_v0"
    assert stored.schema_version == SCHEMA_VERSION
    assert stored.recorded_at == RECORDED_AT
    assert stored.expires_at == RECORDED_AT + timedelta(days=30)
    assert store.size == 1


def test_an_unknown_id_is_absent_rather_than_an_error(store: PredictionStore) -> None:
    assert store.get("0f0f0f0f-0000-4000-8000-000000000000") is None


def test_saving_the_same_id_twice_replaces_the_row(store: PredictionStore) -> None:
    save(store)
    save(store, model_version="baseline_v1")
    assert store.size == 1
    stored = store.get(payload()["prediction_id"], now=RECORDED_AT)
    assert stored is not None
    assert stored.model_version == "baseline_v1"


def test_retention_hides_a_report_before_it_is_purged(store: PredictionStore) -> None:
    save(store)
    later = RECORDED_AT + timedelta(days=30, seconds=1)
    assert store.get(payload()["prediction_id"], now=later) is None
    # Still on disk until a purge runs — hiding and deleting are different acts.
    assert store.size == 1
    assert store.purge_expired(now=later) == 1
    assert store.size == 0


def test_purge_leaves_rows_still_inside_retention(store: PredictionStore) -> None:
    save(store, prediction_id="aaaaaaaa-0000-4000-8000-000000000001")
    save(
        store,
        prediction_id="bbbbbbbb-0000-4000-8000-000000000002",
        recorded_at=RECORDED_AT + timedelta(days=20),
    )
    # 35 days on: the first row (expires +30) is gone, the second expires +50.
    assert store.purge_expired(now=RECORDED_AT + timedelta(days=35)) == 1
    assert store.ids() == ["bbbbbbbb-0000-4000-8000-000000000002"]


def test_rows_written_from_different_offsets_still_purge_in_time_order(store: PredictionStore) -> None:
    """Retention compares stored text, so that text must be one normalised shape.

    A 09:00+05:30 row is earlier than a 09:00Z row; comparing the raw strings would
    delete the wrong one.
    """
    istanbul = timezone(timedelta(hours=5, minutes=30))
    asked = datetime(2026, 10, 21, 0, 0, tzinfo=UTC)
    save(
        store,
        prediction_id="earlier-0000-4000-8000-000000000001",
        prediction_at=asked,
        recorded_at=datetime(2026, 10, 21, 9, 0, tzinfo=istanbul),
    )
    save(
        store,
        prediction_id="later-0000-4000-8000-000000000002",
        prediction_at=asked,
        recorded_at=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
    )
    boundary = datetime(2026, 11, 20, 4, 0, tzinfo=UTC)
    assert store.purge_expired(now=boundary) == 1
    assert store.ids() == ["later-0000-4000-8000-000000000002"]


def test_ids_are_listed_without_listing_contents(store: PredictionStore) -> None:
    save(store)
    save(store, prediction_id="cccccccc-0000-4000-8000-000000000003")
    listed = store.ids()
    assert len(listed) == 2
    assert all(isinstance(identifier, str) for identifier in listed)
    assert "GNWL/41" not in json.dumps(listed)


def test_a_denied_key_blocks_the_write(store: PredictionStore) -> None:
    body = payload()
    body["passenger_outcomes"][0]["name"] = "R. Sharma"
    with pytest.raises(PredictionStorageError, match="denied key"):
        store.save(
            prediction_id=body["prediction_id"],
            payload=body,
            target="final_chart_cnf",
            model_version="no_model_v0",
            prediction_at=PREDICTION_AT,
            recorded_at=RECORDED_AT,
        )
    assert store.size == 0


def test_a_pnr_shaped_value_blocks_the_write(store: PredictionStore) -> None:
    body = payload()
    body["passenger_outcomes"][0]["current_status"] = "2748391056"
    with pytest.raises(PredictionStorageError, match="PNR-shaped"):
        store.save(
            prediction_id=body["prediction_id"],
            payload=body,
            target="final_chart_cnf",
            model_version="no_model_v0",
            prediction_at=PREDICTION_AT,
            recorded_at=RECORDED_AT,
        )
    assert store.size == 0


def test_a_nested_denied_key_is_found_at_any_depth() -> None:
    with pytest.raises(PredictionStorageError, match="passenger_name"):
        assert_storeable({"a": [{"b": {"passenger_name": "x"}}]})


def test_the_ordinary_payload_is_storeable() -> None:
    assert_storeable(payload())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recorded_at", datetime(2026, 10, 21, 9, 0, 30)),  # noqa: DTZ001
        ("prediction_at", datetime(2026, 10, 21, 9, 0)),  # noqa: DTZ001
    ],
)
def test_a_naive_timestamp_is_refused(store: PredictionStore, field: str, value: datetime) -> None:
    arguments = {
        "prediction_id": payload()["prediction_id"],
        "payload": payload(),
        "target": "final_chart_cnf",
        "model_version": "no_model_v0",
        "prediction_at": PREDICTION_AT,
        "recorded_at": RECORDED_AT,
    }
    arguments[field] = value
    with pytest.raises(PredictionStorageError, match="offset-aware"):
        store.save(**arguments)


def test_an_estimate_about_a_later_moment_is_storable(tmp_path: Path) -> None:
    """The as-of moment may be in the future; the record is still created now.

    The form defaults "estimating as of" to 24 hours ahead, so refusing to store a
    report whose prediction timestamp is later than the server clock would reject
    every ordinary save. Retention therefore runs from the save, not from the as-of
    time — the alternative would hide a fresh report behind a future date.
    """
    store = PredictionStore(tmp_path / "future.sqlite3", retention_days=7)
    try:
        stored = store.save(
            prediction_id=payload()["prediction_id"],
            payload=payload(),
            target="final_chart_cnf",
            model_version="no_model_v0",
            prediction_at=RECORDED_AT + timedelta(days=1),
            recorded_at=RECORDED_AT,
        )
        assert stored.expires_at == RECORDED_AT + timedelta(days=7)
        assert store.get(stored.prediction_id, now=RECORDED_AT) is not None
    finally:
        store.close()


def test_an_empty_id_is_refused(store: PredictionStore) -> None:
    with pytest.raises(PredictionStorageError, match="non-empty internal id"):
        store.save(
            prediction_id="  ",
            payload=payload(),
            target="final_chart_cnf",
            model_version="no_model_v0",
            prediction_at=PREDICTION_AT,
            recorded_at=RECORDED_AT,
        )


def test_a_retention_floor_below_one_day_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PredictionStorageError, match="retention_days"):
        PredictionStore(tmp_path / "x.sqlite3", retention_days=0)


def test_retention_days_are_honoured(tmp_path: Path) -> None:
    short = PredictionStore(tmp_path / "short.sqlite3", retention_days=3)
    try:
        short.save(
            prediction_id=payload()["prediction_id"],
            payload=payload(),
            target="final_chart_cnf",
            model_version="no_model_v0",
            prediction_at=PREDICTION_AT,
            recorded_at=RECORDED_AT,
        )
        stored = short.get(payload()["prediction_id"], now=RECORDED_AT)
        assert stored is not None
        assert stored.expires_at == RECORDED_AT + timedelta(days=3)
        assert short.purge_expired(now=RECORDED_AT + timedelta(days=4)) == 1
    finally:
        short.close()


def _mutate(store: PredictionStore, statement: str, parameters: tuple) -> None:
    """Change a stored row behind the store's back, as a corrupt or stale file would.

    The connection is closed here: an unclosed handle turns into a ResourceWarning that
    pytest reports as a test warning, which is how leaked database handles get missed.
    """
    with closing(sqlite3.connect(str(store.path))) as connection:
        connection.execute(statement, parameters)
        connection.commit()


def test_a_future_schema_version_is_refused_rather_than_guessed(
    store: PredictionStore,
) -> None:
    save(store)
    _mutate(store, "UPDATE predictions SET schema_version = ?", (SCHEMA_VERSION + 1,))
    with pytest.raises(PredictionStorageError, match="schema v"):
        store.get(payload()["prediction_id"], now=RECORDED_AT)


def test_corrupt_stored_json_is_refused(store: PredictionStore) -> None:
    save(store)
    _mutate(store, "UPDATE predictions SET payload_json = ?", ("not json {",))
    with pytest.raises(PredictionStorageError, match="not valid JSON"):
        store.get(payload()["prediction_id"], now=RECORDED_AT)


def test_a_stored_array_is_refused(store: PredictionStore) -> None:
    save(store)
    _mutate(store, "UPDATE predictions SET payload_json = ?", ("[1, 2]",))
    with pytest.raises(PredictionStorageError, match="expected an object"):
        store.get(payload()["prediction_id"], now=RECORDED_AT)


@pytest.mark.parametrize(
    ("column", "value", "match"),
    [
        ("recorded_at", "2026-10-21T09:00:30", "offset-aware"),
        ("expires_at", "2026-11-20T09:00:30", "offset-aware"),
        ("expires_at", "2026-10-21T09:00:00+00:00", "expires at"),
    ],
)
def test_untrustworthy_timestamps_in_a_row_are_refused(
    store: PredictionStore, column: str, value: str, match: str
) -> None:
    save(store)
    _mutate(store, f"UPDATE predictions SET {column} = ?", (value,))
    with pytest.raises(PredictionStorageError, match=match):
        store.get(payload()["prediction_id"], now=RECORDED_AT)


def test_the_database_file_is_created_under_the_requested_directory(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested" / "deep" / "predictions.sqlite3"
    instance = PredictionStore(path)
    try:
        assert path.exists()
    finally:
        instance.close()
    assert instance.path == path


def test_concurrent_saves_from_other_threads_are_written_not_lost(tmp_path: Path) -> None:
    """FastAPI serves routes on threads other than the one that opened the store."""
    from concurrent.futures import ThreadPoolExecutor

    store = PredictionStore(tmp_path / "threads.sqlite3", retention_days=7)
    count = 12

    def write(index: int) -> str:
        identifier = f"thread-{index:04d}-0000-4000-8000-000000000000"
        store.save(
            prediction_id=identifier,
            payload={**payload(), "prediction_id": identifier},
            target="final_chart_cnf",
            model_version=f"thread_v{index}",
            prediction_at=PREDICTION_AT,
            recorded_at=RECORDED_AT + timedelta(seconds=index),
        )
        return identifier

    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            written = list(pool.map(write, range(count)))
        assert store.size == count
        assert set(store.ids()) == set(written)
        # Every row is readable, so no commit overwrote another thread's work.
        for identifier in written:
            assert store.get(identifier, now=RECORDED_AT) is not None
    finally:
        store.close()


def test_context_manager_closes_the_store(tmp_path: Path) -> None:
    with PredictionStore(tmp_path / "ctx.sqlite3") as instance:
        save(instance)
        assert instance.size == 1
