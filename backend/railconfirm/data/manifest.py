"""Dataset manifest generation, validation and verification.

A manifest is the durable provenance record for one candidate dataset file. It
follows docs/data/DATASET_MANIFEST_TEMPLATE.yaml, and two properties are enforced
in code rather than hoped for:

* **Deterministic output.** Nothing here reads the wall clock. Every date comes
  from the caller, so the same inputs produce the same bytes and a manifest can be
  hashed and compared.
* **Approval cannot be manufactured.** A mechanical validation report is not a
  licensing decision, so a manifest cannot be written that records an approval
  without a named reviewer and a date, or that marks a dataset usable while its
  licence review is still pending.

Raw dataset files stay outside Git; manifests are the publishable half.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from railconfirm.config import REPO_ROOT
from railconfirm.data.loader import load_dataset_file
from railconfirm.data.validator import DatasetValidationReport, validate_dataset

MANIFEST_SCHEMA_VERSION = "1.0.0"
"""Bump when the manifest layout changes, so older files can be interpreted."""

DEFAULT_MANIFEST_DIR = REPO_ROOT / "data" / "manifests"

MANIFEST_TEMPLATE_PATH = REPO_ROOT / "docs" / "data" / "DATASET_MANIFEST_TEMPLATE.yaml"
"""The published template a generated manifest is checked against by test."""

STATUS_VALUES = ("candidate", "approved", "restricted", "quarantined", "rejected")
DECISION_VALUES = ("under_review", "approved", "restricted", "quarantined", "rejected")
REVIEW_VALUES = ("pending", "approved", "restricted", "rejected")
USE_VALUES = ("unknown", "permitted", "prohibited", "restricted")


class ManifestError(ValueError):
    """A manifest is malformed, contradictory, or refuses to claim more than it may."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def _one_of(value: str, allowed: tuple[str, ...], label: str) -> str:
    cleaned = str(value).strip()
    _require(
        cleaned in allowed,
        f"{label} must be one of {list(allowed)}, got {value!r}.",
    )
    return cleaned


@dataclass(frozen=True)
class AllowedUses:
    """What the source's terms permit. Unknown is the default and stays unknown."""

    local_inspection: str = "unknown"
    transformation: str = "unknown"
    model_training: str = "unknown"
    aggregate_metric_publication: str = "unknown"
    commercial_deployment: str = "unknown"
    redistribution: str = "unknown"

    def __post_init__(self) -> None:
        for use in fields(self):
            _one_of(
                getattr(self, use.name),
                USE_VALUES,
                f"source.allowed_uses.{use.name}",
            )


@dataclass(frozen=True)
class SourceRecord:
    publisher: str = "unknown"
    canonical_url: str | None = None
    received_from: str | None = None
    retrieved_on: str | None = None
    source_register_entry: str | None = None
    terms_url: str | None = None
    licence_name: str = "unknown"
    licence_review_status: str = "pending"
    allowed_uses: AllowedUses = field(default_factory=AllowedUses)
    attribution_requirements: str = "unknown"

    def __post_init__(self) -> None:
        _one_of(
            self.licence_review_status, REVIEW_VALUES, "source.licence_review_status"
        )
        _require(
            str(self.publisher).strip() != "",
            "source.publisher must be named, or left as the literal 'unknown'.",
        )
        # A licence review recorded as approved while the training use is still
        # unknown is the contradiction that lets data leak into a model.
        if self.licence_review_status == "approved":
            _require(
                self.allowed_uses.model_training in {"permitted", "restricted"},
                "source.licence_review_status cannot be 'approved' while "
                "allowed_uses.model_training is still "
                f"{self.allowed_uses.model_training!r}; record the review or mark it "
                "restricted.",
            )
            _require(
                bool(str(self.terms_url or "").strip())
                or bool(str(self.canonical_url or "").strip()),
                "An approved licence needs a terms_url or canonical_url to cite.",
            )


@dataclass(frozen=True)
class FileRecord:
    local_path: str | None = None
    format: str = "unknown"
    sha256: str | None = None
    schema_version: str = "0.1"
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.sha256 is not None:
            digest = str(self.sha256).strip().lower()
            _require(
                len(digest) == 64 and all(character in "0123456789abcdef" for character in digest),
                f"file.sha256 must be 64 hexadecimal characters, got {self.sha256!r}.",
            )
        if self.size_bytes is not None:
            _require(
                isinstance(self.size_bytes, int)
                and not isinstance(self.size_bytes, bool)
                and self.size_bytes >= 0,
                f"file.size_bytes must be a non-negative integer, got {self.size_bytes!r}.",
            )


@dataclass(frozen=True)
class CoverageRecord:
    row_count: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    train_coverage_summary: str = "unknown"
    class_coverage_summary: str = "unknown"
    quota_coverage_summary: str = "unknown"
    status_coverage_summary: str = "unknown"
    final_outcome_label_definition: str = "unknown"
    label_verification_method: str = "unknown"
    observation_timestamp_semantics: str = "unknown"


@dataclass(frozen=True)
class QualityRecord:
    missingness_report: dict[str, int] = field(default_factory=dict)
    duplicate_count: int | None = None
    contradictory_record_count: int | None = None
    censored_or_unverified_outcome_count: int | None = None
    known_biases: list[str] = field(default_factory=list)
    cleaning_script_revision: str | None = None
    validation_report_path: str | None = None
    exclusions_and_reasons: list[str] = field(default_factory=list)
    rejection_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PrivacyRecord:
    contains_personal_data: str = "unknown"
    contains_raw_pnr: str = "unknown"
    contains_passenger_names: str = "unknown"
    minimization_review: str = "pending"
    retention_policy: str = "unknown"
    approval_notes: str | None = None

    def __post_init__(self) -> None:
        for name in ("contains_personal_data", "contains_raw_pnr", "contains_passenger_names"):
            _one_of(getattr(self, name), (*USE_VALUES, "none"), f"privacy.{name}")
        if self.contains_raw_pnr == "permitted":
            raise ManifestError(
                "privacy.contains_raw_pnr cannot be 'permitted'. A dataset carrying "
                "raw PNRs is quarantined until a privacy review is recorded (ADR-0005); "
                "use 'prohibited' or leave it unknown."
            )


@dataclass(frozen=True)
class DecisionRecord:
    reviewed_by: str | None = None
    reviewed_on: str | None = None
    decision: str = "under_review"
    rationale: str | None = None
    unresolved_questions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _one_of(self.decision, DECISION_VALUES, "decision.decision")
        if self.decision in {"approved", "restricted"}:
            _require(
                bool(str(self.reviewed_by or "").strip())
                and bool(str(self.reviewed_on or "").strip()),
                f"decision.decision={self.decision!r} requires reviewed_by and "
                "reviewed_on. A script cannot grant approval; a named person did.",
            )
            _require(
                bool(str(self.rationale or "").strip()),
                f"decision.decision={self.decision!r} requires a written rationale.",
            )


@dataclass(frozen=True)
class DatasetManifest:
    """One candidate dataset: provenance, quality, privacy and decision."""

    dataset_id: str
    title: str
    status: str
    source: SourceRecord
    file: FileRecord
    coverage: CoverageRecord
    quality: QualityRecord
    privacy: PrivacyRecord
    decision: DecisionRecord
    manifest_schema_version: str = MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require(
            bool(str(self.dataset_id).strip()) and bool(str(self.title).strip()),
            "dataset_id and title are required.",
        )
        _one_of(self.status, STATUS_VALUES, "status")
        _require(
            self.manifest_schema_version == MANIFEST_SCHEMA_VERSION,
            f"manifest_schema_version must be {MANIFEST_SCHEMA_VERSION}.",
        )
        # `status` is the review state of the dataset; it may not run ahead of the
        # recorded decision.
        if self.status == "approved":
            _require(
                self.decision.decision == "approved",
                "status='approved' requires decision.decision='approved' with a named "
                "reviewer.",
            )
            _require(
                self.source.licence_review_status == "approved"
                and self.source.allowed_uses.model_training == "permitted",
                "status='approved' requires an approved licence review that permits "
                "model training.",
            )

    # ── Serialisation ──────────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return _plain(asdict(self))

    def to_yaml(self) -> str:
        """Deterministic YAML: same inputs, same bytes."""
        return yaml.safe_dump(
            self.to_dict(), sort_keys=False, default_flow_style=False, width=100
        )

    def digest(self) -> str:
        return hashlib.sha256(self.to_yaml().encode("utf-8")).hexdigest()


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _section(cls: type, payload: Any, label: str) -> Any:
    _require(
        isinstance(payload, dict),
        f"Manifest section {label!r} must be a mapping, got {type(payload).__name__}."
    )
    allowed = {item.name for item in fields(cls)}
    unknown = [key for key in payload if key not in allowed]
    _require(
        not unknown,
        f"Manifest section {label!r} has unrecognised keys {unknown}; expected {sorted(allowed)}.",
    )
    if cls is SourceRecord and "allowed_uses" in payload:
        payload = {**payload, "allowed_uses": AllowedUses(**payload["allowed_uses"])}
    try:
        return cls(**payload)
    except TypeError as exc:
        raise ManifestError(f"Manifest section {label!r} is invalid: {exc}") from exc


def parse_manifest(text: str) -> DatasetManifest:
    """Read manifest YAML back into the typed model, rejecting unknown keys."""
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"Manifest is not valid YAML: {exc}") from exc
    _require(isinstance(payload, dict), "Manifest root must be a mapping.")
    for name in ("dataset_id", "title", "status"):
        _require(name in payload, f"Manifest is missing '{name}'.")
    try:
        return DatasetManifest(
            dataset_id=payload["dataset_id"],
            title=payload["title"],
            status=payload["status"],
            source=_section(SourceRecord, payload.get("source", {}), "source"),
            file=_section(FileRecord, payload.get("file", {}), "file"),
            coverage=_section(CoverageRecord, payload.get("coverage", {}), "coverage"),
            quality=_section(QualityRecord, payload.get("quality", {}), "quality"),
            privacy=_section(PrivacyRecord, payload.get("privacy", {}), "privacy"),
            decision=_section(DecisionRecord, payload.get("decision", {}), "decision"),
            manifest_schema_version=payload.get(
                "manifest_schema_version", MANIFEST_SCHEMA_VERSION
            ),
        )
    except TypeError as exc:
        raise ManifestError(f"Manifest is invalid: {exc}") from exc


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def report_to_quality(report: DatasetValidationReport) -> QualityRecord:
    """Carry observed validation numbers into the manifest's quality section."""
    return QualityRecord(
        missingness_report=dict(report.null_counts),
        duplicate_count=report.duplicate_rows,
        contradictory_record_count=report.contradictory_label_rows,
        censored_or_unverified_outcome_count=(
            report.censored_label_rows + report.rejection_reasons.get("unknown_final_status", 0)
        ),
        cleaning_script_revision=None,
        validation_report_path=None,
        exclusions_and_reasons=[
            f"{reason}: {count}" for reason, count in sorted(report.rejection_reasons.items())
        ],
        rejection_reasons=dict(report.rejection_reasons),
    )


def generate_manifest(
    file_path: Path,
    *,
    dataset_id: str,
    title: str,
    retrieved_on: str,
    status: str = "candidate",
    source: SourceRecord | None = None,
    privacy: PrivacyRecord | None = None,
    decision: DecisionRecord | None = None,
    coverage_extra: dict[str, str] | None = None,
    report: DatasetValidationReport | None = None,
) -> DatasetManifest:
    """Build a manifest from a real file and a validation pass.

    ``retrieved_on`` is required rather than defaulted to today: a manifest dated
    by the clock cannot be regenerated byte-for-byte, and "when did we get this"
    is a fact about the file, not about when the script ran.
    """
    path = Path(file_path)
    _require(path.is_file(), f"Dataset file not found: {path}")
    _require(
        str(retrieved_on).strip() != "",
        "generate_manifest needs retrieved_on (YYYY-MM-DD from the source record).",
    )

    existing = report
    if existing is None:
        existing = validate_dataset(
            load_dataset_file(path), source_name=path.name
        )

    frame_dates = getattr(existing, "journey_date_range", None)
    coverage = CoverageRecord(
        row_count=existing.total_rows,
        start_date=frame_dates[0] if frame_dates else None,
        end_date=frame_dates[1] if frame_dates else None,
        train_coverage_summary=(existing.summary().splitlines() or ["unknown"])[0],
        class_coverage_summary=f"initial statuses seen: {sorted(existing.initial_status_distribution)}",
        quota_coverage_summary="not recorded",
        status_coverage_summary=f"final outcomes: {sorted(existing.final_status_distribution)}",
        final_outcome_label_definition="final_chart_status column, normalized via status mapping",
        label_verification_method="unknown",
        observation_timestamp_semantics="observation_date is an ISO calendar date",
    )
    if coverage_extra:
        coverage = CoverageRecord(**{**_plain(coverage), **coverage_extra})

    manifest = DatasetManifest(
        dataset_id=dataset_id,
        title=title,
        status=status,
        source=source or SourceRecord(retrieved_on=retrieved_on),
        file=FileRecord(
            local_path=None,  # a local path is not publishable provenance
            format=path.suffix.lstrip(".").lower() or "unknown",
            sha256=compute_sha256(path),
            size_bytes=path.stat().st_size,
        ),
        coverage=coverage,
        quality=report_to_quality(existing),
        privacy=privacy or PrivacyRecord(),
        decision=decision or DecisionRecord(),
    )
    _require(
        manifest.source.retrieved_on == retrieved_on,
        "source.retrieved_on must be recorded.",
    )
    return manifest


@dataclass(frozen=True)
class ManifestVerification:
    """Result of checking a manifest against the file it describes."""

    manifest_digest: str
    checks: list[str]
    findings: list[str]

    @property
    def ok(self) -> bool:
        return not self.findings

    def summary(self) -> str:
        lines = [f"Manifest digest {self.manifest_digest}", f"Checks: {len(self.checks)}"]
        lines += [f"  ok      {check}" for check in self.checks]
        lines += [f"  FAIL    {finding}" for finding in self.findings]
        return "\n".join(lines)


def verify_manifest(
    manifest_path: Path,
    dataset_path: Path | None = None,
) -> ManifestVerification:
    """Re-check a manifest's own claims, optionally against the dataset file.

    Row counts are recounted rather than trusted: a manifest that still asserts
    40,000 rows after the file lost half its rows must fail here, not in a report.
    """
    path = Path(manifest_path)
    _require(path.is_file(), f"Manifest not found: {path}")
    manifest = parse_manifest(path.read_text(encoding="utf-8"))

    checks: list[str] = []
    findings: list[str] = []

    checks.append(f"manifest_schema_version {manifest.manifest_schema_version}")
    checks.append(f"status {manifest.status} / decision {manifest.decision.decision}")

    if manifest.file.sha256:
        checks.append("file.sha256 is well-formed")
    else:
        findings.append("file.sha256 is missing, so the dataset cannot be identified.")

    if dataset_path is not None:
        data_path = Path(dataset_path)
        if not data_path.is_file():
            findings.append(f"dataset file not found at {data_path}")
            return ManifestVerification(manifest.digest(), checks, findings)

        actual_digest = compute_sha256(data_path)
        if manifest.file.sha256 is None:
            findings.append("manifest records no sha256 to compare against.")
        elif actual_digest != manifest.file.sha256:
            findings.append(
                f"content changed: file hashes {actual_digest[:12]}… but the manifest "
                f"records {manifest.file.sha256[:12]}…"
            )
        else:
            checks.append("file.sha256 matches the dataset")

        actual_size = data_path.stat().st_size
        if manifest.file.size_bytes not in (None, actual_size):
            findings.append(
                f"file.size_bytes records {manifest.file.size_bytes}, file is {actual_size}."
            )
        elif manifest.file.size_bytes is not None:
            checks.append("file.size_bytes matches")

        try:
            frame = load_dataset_file(data_path)
        except (ValueError, OSError) as exc:
            findings.append(f"dataset file cannot be read: {exc}")
            return ManifestVerification(manifest.digest(), checks, findings)

        if manifest.coverage.row_count is not None:
            if int(manifest.coverage.row_count) != len(frame):
                findings.append(
                    f"coverage.row_count records {manifest.coverage.row_count}, "
                    f"file has {len(frame)} rows."
                )
            else:
                checks.append("coverage.row_count matches")

        recount = validate_dataset(frame, source_name=data_path.name)
        if manifest.quality.duplicate_count is not None:
            if int(manifest.quality.duplicate_count) != recount.duplicate_rows:
                findings.append(
                    f"quality.duplicate_count records {manifest.quality.duplicate_count}, "
                    f"recount found {recount.duplicate_rows}."
                )
            else:
                checks.append("quality.duplicate_count matches a fresh recount")

    return ManifestVerification(manifest.digest(), checks, findings)


def manifest_output_path(name: str, directory: Path | None = None) -> Path:
    """Resolve a safe write target directly inside the manifests directory.

    The name is a bare filename on purpose: a separator means something different
    on each platform (``..\\x.yaml`` traverses on Windows and is an ordinary
    filename on Linux), so rejecting separators rather than pattern-matching one
    flavour of path keeps the guard identical everywhere it runs.
    """
    base = Path(directory) if directory is not None else DEFAULT_MANIFEST_DIR
    cleaned = str(name).strip()
    _require(cleaned.endswith(".yaml"), f"Manifest file name must end in .yaml, got {name!r}.")
    _require(
        not any(sep in cleaned for sep in ("/", "\\", os.sep, os.altsep or "")),
        f"Manifest name {name!r} must be a bare filename without path separators; "
        "the directory is chosen with --output.",
    )
    _require(".." not in cleaned, f"Manifest name {name!r} must not contain '..'.")
    candidate = (base / cleaned).resolve()
    root = base.resolve()
    _require(
        candidate.is_relative_to(root),
        f"Manifest path {candidate} escapes the intended directory {root}.",
    )
    _require(
        candidate.parent == root,
        f"Manifests are written directly into {root}, not into subdirectories.",
    )
    return candidate


def write_manifest(
    manifest: DatasetManifest,
    path: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write manifest YAML, refusing to clobber a different file by accident."""
    target = Path(path)
    text = manifest.to_yaml()
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if existing == text:
            return target
        if not overwrite:
            raise ManifestError(
                f"{target} already holds a different manifest. Pass overwrite to "
                "replace it, or write a new dataset_id."
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target
