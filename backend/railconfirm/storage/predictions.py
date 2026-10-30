"""Local prediction history.

Nothing is stored unless the operator enables it *and* the caller asks for it. The default
is off, because the product's privacy claim is that a query stays inside the user's own
session; an always-on history table would quietly invalidate that.

The store keeps the serialised response the caller already received, so a saved report is
exactly what was shown — including the model version, registry state and limitations that
made it honest. Payload shape is the API layer's business; this layer treats it as JSON and
enforces only what must hold regardless of schema: no denied keys, no PNR-shaped values, an
offset-aware clock, and a retention floor.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from railconfirm.domain.exceptions import RailConfirmError

SCHEMA_VERSION = 1

# Keys that must never reach storage. The domain model has no field for these today; the
# check exists so that adding one fails here instead of silently persisting it.
DENIED_KEYS = frozenset(
    {
        "pnr",
        "pnr_number",
        "passenger_name",
        "passenger_names",
        "name",
        "names",
        "birth_date",
        "dob",
        "mobile",
        "phone",
        "email",
        "aadhaar",
        "id_proof",
    }
)

_PNR_SHAPE = re.compile(r"^[1-9][0-9]{9}$")
# A timestamp kept as text must carry an offset, or "expired" becomes a guess about
# whichever timezone happened to read it.
_AWARE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id  TEXT PRIMARY KEY,
    recorded_at    TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    target         TEXT NOT NULL,
    model_version  TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload_json   TEXT NOT NULL
)
"""
_CREATE_INDEX_SQL = "CREATE INDEX IF NOT EXISTS predictions_expires_at ON predictions (expires_at)"


class PredictionStorageError(RailConfirmError):
    """Storage refused the write, or the stored row cannot be trusted."""


def _walk_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _walk_keys(nested)


def _walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_strings(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _walk_strings(nested)
    elif isinstance(value, str):
        yield value


def assert_storeable(payload: dict[str, Any]) -> None:
    """Refuse a payload carrying an identifier the product has no right to keep."""
    offenders = sorted({key.lower() for key in _walk_keys(payload) if key.lower() in DENIED_KEYS})
    if offenders:
        raise PredictionStorageError(
            f"Prediction payload carries denied key(s) {offenders}. Passenger identity is "
            "not required for a confirmation estimate and is never stored (ADR-0005). "
            "Remove the field or record a privacy decision before widening this."
        )
    pnr_shaped = [value for value in _walk_strings(payload) if _PNR_SHAPE.match(value)]
    if pnr_shaped:
        raise PredictionStorageError(
            f"Prediction payload contains PNR-shaped value(s) {pnr_shaped[:3]}. Store the "
            "internal prediction id instead."
        )


def _aware(value: datetime, name: str) -> datetime:
    """Reject a naive timestamp before it becomes a retention calculation."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise PredictionStorageError(
            f"{name} must be offset-aware before it is stored; retention against a naive "
            "time is a guess about whichever clock wrote it."
        )
    return value


def _instant(value: datetime) -> str:
    """Fixed-shape UTC text: lexicographic order equals chronological order."""
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _normalise(value: datetime) -> datetime:
    """Second precision in UTC — the same instant the database will hand back."""
    return value.astimezone(UTC).replace(microsecond=0)


def _parse_instant(name: str, raw: str) -> datetime:
    if not _AWARE_ISO.match(raw):
        raise PredictionStorageError(
            f"Stored {name} {raw!r} is not an offset-aware ISO-8601 timestamp; retention "
            "cannot be evaluated against a naive time."
        )
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


@dataclass(frozen=True)
class StoredPrediction:
    """One stored report plus the bookkeeping needed to render and expire it."""

    prediction_id: str
    recorded_at: datetime
    expires_at: datetime
    target: str
    model_version: str
    schema_version: int
    payload: dict[str, Any]

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class StoredSummary:
    """What a history list may say about a report without saying what it says.

    Id, clock and provenance only: a list that carried probabilities would put ticket
    detail in a place nobody agreed to look, and the whole point of the reopen route is
    that the report itself is fetched deliberately.
    """

    prediction_id: str
    recorded_at: datetime
    expires_at: datetime
    target: str
    model_version: str

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


class PredictionStore:
    """SQLite-backed history of prediction reports."""

    def __init__(self, path: Path, *, retention_days: int = 30) -> None:
        if retention_days < 1:
            raise PredictionStorageError(
                f"retention_days must be at least 1, got {retention_days}. History without "
                "a retention floor is just an accumulation of other people's ticket data."
            )
        self.path = Path(path)
        self.retention_days = retention_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # One connection, guarded by a lock, shared across threads. FastAPI serves async
        # routes on the event loop and sync routes on a worker thread, so a connection
        # created at startup is routinely used from a different thread than the one that
        # opened it — sqlite3's default ownership check would raise in the request path.
        # WAL lets readers proceed while a writer commits; the lock keeps this process's
        # own writes and commits from interleaving.
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._connection.execute("PRAGMA foreign_keys = ON")
        # A deleted row's bytes would otherwise stay in a free page until SQLite reused
        # it. This is accident-proofing, not a cryptographic erase: the WAL side files and
        # any filesystem-level snapshot can still hold older bytes.
        self._connection.execute("PRAGMA secure_delete = ON")
        self._connection.execute(_CREATE_SQL)
        self._connection.execute(_CREATE_INDEX_SQL)
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> PredictionStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def size(self) -> int:
        with self._lock:
            row = self._connection.execute("SELECT COUNT(*) AS n FROM predictions").fetchone()
        assert row is not None
        return int(row["n"])

    def save(
        self,
        *,
        prediction_id: str,
        payload: dict[str, Any],
        target: str,
        model_version: str,
        prediction_at: datetime,
        recorded_at: datetime | None = None,
    ) -> StoredPrediction:
        """Persist one report. A repeated id overwrites rather than duplicating a row."""
        if not prediction_id.strip():
            raise PredictionStorageError("prediction_id must be a non-empty internal id.")
        stamp = recorded_at or datetime.now(UTC)
        # Checked before any conversion: astimezone() would silently assume a naive
        # value was local time, which is exactly the guess this store must not make.
        _aware(stamp, "recorded_at")
        _aware(prediction_at, "prediction_at")
        stamp = _normalise(stamp)
        assert_storeable(payload)
        # Both bookkeeping columns are written as UTC with a fixed shape, so a text
        # comparison in SQLite is also a chronological one. Comparing ISO strings from
        # mixed offsets would silently order them wrongly. The value is rounded through
        # that same format here, so what this call returns is what a later read finds —
        # otherwise a report's expiry would differ between the write and the reopen.
        expires_at = stamp + timedelta(days=self.retention_days)
        with self._lock:
            self._connection.execute(
                "INSERT INTO predictions (prediction_id, recorded_at, expires_at, target, "
            "model_version, schema_version, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(prediction_id) DO UPDATE SET "
            "recorded_at = excluded.recorded_at, expires_at = excluded.expires_at, "
            "target = excluded.target, model_version = excluded.model_version, "
            "schema_version = excluded.schema_version, "
                "payload_json = excluded.payload_json",
                (
                    prediction_id,
                    _instant(stamp),
                    _instant(expires_at),
                    target,
                    model_version,
                    SCHEMA_VERSION,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            self._connection.commit()
        return StoredPrediction(
            prediction_id=prediction_id,
            recorded_at=stamp,
            expires_at=expires_at,
            target=target,
            model_version=model_version,
            schema_version=SCHEMA_VERSION,
            payload=payload,
        )

    def get(self, prediction_id: str, *, now: datetime | None = None) -> StoredPrediction | None:
        """Return a stored report, or None when it is absent or past retention.

        Expiry hides rather than deletes: the row waits for a purge, but an id whose
        retention window has closed must not keep serving a report.
        """
        if not prediction_id.strip():
            return None
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM predictions WHERE prediction_id = ?", (prediction_id,)
            ).fetchone()
        if row is None:
            return None
        stored = self._hydrate(row)
        if stored.is_expired(now or datetime.now(UTC)):
            return None
        return stored

    def _hydrate(self, row: sqlite3.Row) -> StoredPrediction:
        version = int(row["schema_version"])
        if version != SCHEMA_VERSION:
            raise PredictionStorageError(
                f"Stored prediction {row['prediction_id']} uses schema v{version}; this "
                f"build reads v{SCHEMA_VERSION}. Write a migration instead of guessing."
            )
        recorded_at = _parse_instant("recorded_at", str(row["recorded_at"]))
        expires_at = _parse_instant("expires_at", str(row["expires_at"]))
        if expires_at <= recorded_at:
            raise PredictionStorageError(
                f"Stored prediction {row['prediction_id']} expires at "
                f"{expires_at.isoformat()}, before it was recorded at "
                f"{recorded_at.isoformat()}."
            )
        try:
            payload = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError as exc:
            raise PredictionStorageError(
                f"Stored prediction {row['prediction_id']} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise PredictionStorageError(
                f"Stored prediction {row['prediction_id']} holds a "
                f"{type(payload).__name__}, expected an object."
            )
        return StoredPrediction(
            prediction_id=str(row["prediction_id"]),
            recorded_at=recorded_at,
            expires_at=expires_at,
            target=str(row["target"]),
            model_version=str(row["model_version"]),
            schema_version=version,
            payload=payload,
        )

    def purge_expired(self, *, now: datetime) -> int:
        """Delete rows past retention and report how many went."""
        _aware(now, "purge instant")
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM predictions WHERE expires_at <= ?",
                (_instant(now.astimezone(UTC)),),
            )
            self._connection.commit()
        return cursor.rowcount

    def delete(self, prediction_id: str) -> bool:
        """Remove one report outright, and report whether anything was removed.

        Expiry hides; this is the user asking for it back, so the row goes. SQLite's
        ``secure_delete`` zeroes freed pages on the way, which stops a casual read of the
        file finding a deleted report — it does not reach the WAL side files or a
        filesystem snapshot, and the difference is stated in docs/SECURITY_AND_PRIVACY.md
        rather than oversold here.
        """
        if not prediction_id.strip():
            return False
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM predictions WHERE prediction_id = ?", (prediction_id,)
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def delete_live(self, prediction_id: str, *, now: datetime) -> bool:
        """Remove a report only while retention still serves it (ADR-0040).

        The condition and the delete are one statement, so a report cannot expire between
        deciding it is available and removing it. An expired row is deliberately left for
        `purge_expired` or an unconfirmed call to `delete`; a route that cleared it and
        answered 204 would confirm an id the read route already treats as absent.
        """
        _aware(now, "delete instant")
        if not prediction_id.strip():
            return False
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM predictions WHERE prediction_id = ? AND expires_at > ?",
                (prediction_id, _instant(now.astimezone(UTC))),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def summaries(self, *, now: datetime | None = None) -> list[StoredSummary]:
        """Every report a reopen would still serve, newest first, without its contents.

        A report past its retention is left out rather than listed as available: the list
        and the read route must agree about what exists, or a click on the list becomes an
        unexplained 404.
        """
        instant = _normalise(_aware(now or datetime.now(UTC), "now"))
        with self._lock:
            rows = self._connection.execute(
                "SELECT prediction_id, recorded_at, expires_at, target, model_version "
                "FROM predictions WHERE expires_at > ? "
                # Retention is second-precise, so two saves can share a timestamp; the id
                # breaks the tie so a user's list does not reorder between page loads.
                "ORDER BY recorded_at DESC, prediction_id DESC",
                (_instant(instant),),
            ).fetchall()
        summaries: list[StoredSummary] = []
        for row in rows:
            recorded_at = _parse_instant("recorded_at", str(row["recorded_at"]))
            expires_at = _parse_instant("expires_at", str(row["expires_at"]))
            if expires_at <= recorded_at:
                raise PredictionStorageError(
                    f"Stored prediction {row['prediction_id']} expires at "
                    f"{expires_at.isoformat()}, before it was recorded at "
                    f"{recorded_at.isoformat()}."
                )
            summaries.append(
                StoredSummary(
                    prediction_id=str(row["prediction_id"]),
                    recorded_at=recorded_at,
                    expires_at=expires_at,
                    target=str(row["target"]),
                    model_version=str(row["model_version"]),
                )
            )
        return summaries
