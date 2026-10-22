"""Tests for manifest generation, determinism, approval guards and verification."""

import hashlib
from pathlib import Path

import pytest
import yaml

from railconfirm.data.manifest import (
    DEFAULT_MANIFEST_DIR,
    MANIFEST_TEMPLATE_PATH,
    AllowedUses,
    CoverageRecord,
    DatasetManifest,
    DecisionRecord,
    FileRecord,
    ManifestError,
    PrivacyRecord,
    QualityRecord,
    SourceRecord,
    compute_sha256,
    generate_manifest,
    manifest_output_path,
    parse_manifest,
    verify_manifest,
    write_manifest,
)

RETRIEVED = "2026-10-18"


def manifest(**overrides) -> DatasetManifest:
    base = {
        "dataset_id": "fixture-set",
        "title": "Fixture candidate set",
        "status": "candidate",
        "source": SourceRecord(retrieved_on=RETRIEVED),
        "file": FileRecord(
            format="csv",
            sha256="a" * 64,
            size_bytes=128,
        ),
        "coverage": CoverageRecord(row_count=6),
        "quality": QualityRecord(duplicate_count=0),
        "privacy": PrivacyRecord(),
        "decision": DecisionRecord(),
    }
    base.update(overrides)
    return DatasetManifest(**base)


# ── Determinism ────────────────────────────────────────────────────────────────


def test_yaml_is_byte_identical_across_calls():
    first = manifest().to_yaml()
    second = manifest().to_yaml()
    assert first == second
    assert manifest().digest() == manifest().digest()


def test_no_wall_clock_in_the_output():
    """The old manifest stamped datetime.now(), so two runs never matched."""
    text = manifest().to_yaml()
    today = __import__("datetime").date.today().isoformat()
    assert today not in text
    assert "created_at" not in text


def test_round_trip_through_yaml():
    original = manifest(
        source=SourceRecord(
            retrieved_on=RETRIEVED,
            publisher="Fixture Producer",
            licence_name="CC BY 4.0",
            allowed_uses=AllowedUses(local_inspection="permitted", model_training="restricted"),
            licence_review_status="restricted",
        ),
        quality=QualityRecord(duplicate_count=2, rejection_reasons={"censored_label": 1}),
    )
    assert parse_manifest(original.to_yaml()) == original


def test_digest_changes_when_provenance_changes():
    assert manifest().digest() != manifest(status="quarantined").digest()


# ── Approval cannot be manufactured ────────────────────────────────────────────


def test_status_approved_requires_an_approved_decision():
    with pytest.raises(ManifestError, match="requires decision.decision"):
        manifest(status="approved")


def test_decision_approved_requires_a_named_reviewer():
    with pytest.raises(ManifestError, match="reviewed_by and reviewed_on"):
        DecisionRecord(decision="approved")


def test_decision_approved_requires_a_rationale():
    with pytest.raises(ManifestError, match="rationale"):
        DecisionRecord(decision="approved", reviewed_by="R. Bhogesara", reviewed_on=RETRIEVED)


def test_restricted_decision_also_needs_attribution():
    with pytest.raises(ManifestError, match="reviewed_by"):
        DecisionRecord(decision="restricted")


def test_licence_approved_while_training_use_is_unknown_is_rejected():
    """The exact contradiction that lets data slip into a model."""
    with pytest.raises(ManifestError, match="allowed_uses.model_training"):
        SourceRecord(retrieved_on=RETRIEVED, licence_review_status="approved")


def test_licence_approved_needs_a_citable_source():
    with pytest.raises(ManifestError, match="terms_url or canonical_url"):
        SourceRecord(
            retrieved_on=RETRIEVED,
            licence_review_status="approved",
            allowed_uses=AllowedUses(model_training="permitted"),
        )


def test_raw_pnr_permission_is_refused():
    with pytest.raises(ManifestError, match="contains_raw_pnr"):
        PrivacyRecord(contains_raw_pnr="permitted")


@pytest.mark.parametrize("status", ["usable", "approved_for_training", "APPROVED", ""])
def test_status_vocabulary_is_closed(status):
    with pytest.raises(ManifestError, match="status must be one of"):
        manifest(status=status)


def test_unknown_outcome_of_the_old_approval_vocabulary_is_rejected():
    """approved_for_training / metadata_only / synthetic_test_only are not the template's states."""
    for stale in ("approved_for_training", "metadata_only", "synthetic_test_only"):
        with pytest.raises(ManifestError):
            manifest(status=stale)


# ── Structural validation ──────────────────────────────────────────────────────


def test_malformed_sha256_is_rejected():
    with pytest.raises(ManifestError, match="64 hexadecimal"):
        FileRecord(sha256="deadbeef")


def test_negative_size_is_rejected():
    with pytest.raises(ManifestError, match="size_bytes"):
        FileRecord(size_bytes=-1)


def test_dataset_id_and_title_are_required():
    with pytest.raises(ManifestError, match="required"):
        manifest(dataset_id="  ")


def test_schema_version_must_match_the_module():
    with pytest.raises(ManifestError, match="manifest_schema_version"):
        manifest(manifest_schema_version="0.0.1")


def test_parse_rejects_unknown_keys():
    payload = yaml.safe_load(manifest().to_yaml())
    payload["source"]["licence"] = "CC0"
    with pytest.raises(ManifestError, match="unrecognised keys"):
        yaml.safe_dump(payload)
        parse_manifest(yaml.safe_dump(payload))


def test_parse_rejects_non_mapping_root():
    with pytest.raises(ManifestError, match="must be a mapping"):
        parse_manifest("- a\n- b\n")


# ── Template parity ────────────────────────────────────────────────────────────


def test_manifest_covers_every_template_section():
    """The generated file must satisfy docs/data/DATASET_MANIFEST_TEMPLATE.yaml."""
    template = yaml.safe_load(MANIFEST_TEMPLATE_PATH.read_text(encoding="utf-8"))
    produced = manifest().to_dict()
    assert set(template) <= set(produced), set(template) - set(produced)
    for section in ("source", "file", "coverage", "quality", "privacy", "decision"):
        assert set(template[section]) <= set(produced[section]), section


def test_template_defaults_are_the_pending_ones():
    produced = manifest().to_dict()
    assert produced["status"] == "candidate"
    assert produced["decision"]["decision"] == "under_review"
    assert produced["source"]["licence_review_status"] == "pending"
    assert produced["source"]["allowed_uses"]["model_training"] == "unknown"


# ── Generation from a real file ────────────────────────────────────────────────


def test_generate_manifest_hashes_the_actual_file(synthetic_dataset_path: Path):
    produced = generate_manifest(
        synthetic_dataset_path,
        dataset_id="synthetic-fixture",
        title="Synthetic test fixture",
        retrieved_on=RETRIEVED,
    )
    expected = hashlib.sha256(synthetic_dataset_path.read_bytes()).hexdigest()
    assert produced.file.sha256 == expected
    assert produced.file.size_bytes == synthetic_dataset_path.stat().st_size
    assert produced.coverage.row_count == 6
    assert produced.coverage.start_date == "2026-10-01"
    assert produced.coverage.end_date == "2026-10-05"
    assert produced.status == "candidate"
    assert produced.decision.decision == "under_review"
    assert "censored_label" not in produced.quality.rejection_reasons


def test_generate_manifest_records_rejection_reasons(tmp_path: Path):
    csv = tmp_path / "candidate.csv"
    csv.write_text(
        "train_number,journey_date,class_code,quota_code,initial_status,final_chart_status,observation_date\n"
        "12301,2026-10-01,SL,GN,GNWL/10,CNF,2026-09-20\n"
        "12301,2026-10-02,SL,GN,GNWL/11,CENSORED,2026-09-21\n"
        "bad,2026-10-03,SL,GN,GNWL/12,CNF,2026-09-22\n",
        encoding="utf-8",
    )
    produced = generate_manifest(
        csv, dataset_id="mixed", title="Mixed fixture", retrieved_on=RETRIEVED
    )
    assert produced.quality.censored_or_unverified_outcome_count == 1
    assert produced.quality.rejection_reasons["invalid_train_number"] == 1
    assert produced.quality.exclusions_and_reasons


def test_retrieved_on_is_required(synthetic_dataset_path: Path):
    with pytest.raises(ManifestError, match="retrieved_on"):
        generate_manifest(
            synthetic_dataset_path,
            dataset_id="x",
            title="x",
            retrieved_on="  ",
        )


def test_missing_dataset_file_is_reported(tmp_path: Path):
    with pytest.raises(Exception, match="not found"):
        generate_manifest(
            tmp_path / "absent.csv", dataset_id="x", title="x", retrieved_on=RETRIEVED
        )


# ── Verification ───────────────────────────────────────────────────────────────


def test_verify_passes_for_an_unchanged_file(synthetic_dataset_path: Path, tmp_path: Path):
    produced = generate_manifest(
        synthetic_dataset_path,
        dataset_id="synthetic-fixture",
        title="Synthetic test fixture",
        retrieved_on=RETRIEVED,
    )
    path = write_manifest(produced, tmp_path / "m.yaml")
    result = verify_manifest(path, synthetic_dataset_path)
    assert result.ok, result.summary()
    assert any("file.sha256 matches" in check for check in result.checks)
    assert any("row_count matches" in check for check in result.checks)


def test_verify_detects_content_drift(synthetic_dataset_path: Path, tmp_path: Path):
    produced = generate_manifest(
        synthetic_dataset_path,
        dataset_id="synthetic-fixture",
        title="Synthetic test fixture",
        retrieved_on=RETRIEVED,
    )
    path = write_manifest(produced, tmp_path / "m.yaml")

    edited = tmp_path / "edited.csv"
    edited.write_text(synthetic_dataset_path.read_text(encoding="utf-8").rstrip("\n") + "\n", encoding="utf-8")
    result = verify_manifest(path, edited)
    assert not result.ok
    assert any("content changed" in finding for finding in result.findings)


def test_verify_detects_row_count_drift_without_a_hash_change(tmp_path: Path):
    """A manifest can be internally stale: row_count is recounted, not trusted."""
    csv = tmp_path / "two.csv"
    csv.write_text(
        "train_number,journey_date,class_code,quota_code,initial_status,final_chart_status,observation_date\n"
        "12301,2026-10-01,SL,GN,GNWL/10,CNF,2026-09-20\n"
        "12301,2026-10-02,SL,GN,GNWL/11,WL/4,2026-09-21\n",
        encoding="utf-8",
    )
    stale = manifest(
        dataset_id="two",
        title="Two rows",
        file=FileRecord(format="csv", sha256=compute_sha256(csv), size_bytes=csv.stat().st_size),
        coverage=CoverageRecord(row_count=40000),
    )
    path = write_manifest(stale, tmp_path / "stale.yaml")
    result = verify_manifest(path, csv)
    assert any("coverage.row_count records 40000" in finding for finding in result.findings)


def test_verify_without_a_dataset_file_still_checks_self_consistency(tmp_path: Path):
    path = write_manifest(manifest(), tmp_path / "m.yaml")
    result = verify_manifest(path)
    assert result.ok
    assert any("sha256 is well-formed" in check for check in result.checks)


def test_verify_reports_a_missing_dataset_file(tmp_path: Path):
    path = write_manifest(manifest(), tmp_path / "m.yaml")
    result = verify_manifest(path, tmp_path / "absent.csv")
    assert not result.ok
    assert any("not found" in finding for finding in result.findings)


def test_parse_rejects_a_broken_manifest_file(tmp_path: Path):
    path = tmp_path / "broken.yaml"
    path.write_text("dataset_id: x\n\tbad indent", encoding="utf-8")
    with pytest.raises(ManifestError, match="not valid YAML"):
        verify_manifest(path)


# ── Safe output paths ──────────────────────────────────────────────────────────


def test_manifest_name_must_be_yaml():
    with pytest.raises(ManifestError, match="must end in .yaml"):
        manifest_output_path("notes.txt")


@pytest.mark.parametrize("name", ["../outside.yaml", "sub/dir/x.yaml", "..\\escape.yaml"])
def test_paths_cannot_escape_the_manifests_directory(name):
    with pytest.raises(ManifestError):
        manifest_output_path(name, DEFAULT_MANIFEST_DIR)


def test_output_path_resolves_inside_the_given_directory(tmp_path: Path):
    target = manifest_output_path("ok.yaml", tmp_path)
    assert target.parent == tmp_path.resolve()


def test_write_refuses_to_clobber_a_different_manifest(tmp_path: Path):
    path = tmp_path / "m.yaml"
    write_manifest(manifest(dataset_id="first"), path)
    with pytest.raises(ManifestError, match="already holds a different manifest"):
        write_manifest(manifest(dataset_id="second"), path)


def test_write_is_idempotent_for_identical_content(tmp_path: Path):
    path = tmp_path / "m.yaml"
    write_manifest(manifest(), path)
    before = path.read_text(encoding="utf-8")
    write_manifest(manifest(), path)
    assert path.read_text(encoding="utf-8") == before


def test_overwrite_flag_replaces_explicitly(tmp_path: Path):
    path = tmp_path / "m.yaml"
    write_manifest(manifest(dataset_id="first"), path)
    write_manifest(manifest(dataset_id="second"), path, overwrite=True)
    assert parse_manifest(path.read_text(encoding="utf-8")).dataset_id == "second"


def test_manifest_yaml_is_human_readable_and_orders_sections():
    text = manifest().to_yaml()
    assert text.index("dataset_id:") < text.index("source:") < text.index("decision:")
    assert "decision:" in text and "privacy:" in text
