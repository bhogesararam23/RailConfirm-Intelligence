"""Tests for the training data gate: what may and may not be fitted on."""

from pathlib import Path

import pytest

from railconfirm.training.dataset import TrainingDataError, load_approved_dataset
from tests.support.datasets import (
    GATE_ROW_COUNT,
    approved_decision,
    approved_source,
    gate_defects,
    write_approved_manifest,
    write_dataset,
    write_gate_dataset,
)

CLEAN_IDS = {f"P{index:04d}" for index in range(GATE_ROW_COUNT)}
TOTAL_GATE_ROWS = GATE_ROW_COUNT + len(gate_defects())


# ── Technical eligibility and rejected rows ────────────────────────────────────


def test_rows_the_validator_rejected_never_reach_the_training_frame(tmp_path):
    """Regression: the gate checked a verdict and then handed over the whole file.

    Every defect shape is counted in the report, and none of them may appear in the
    frame the fitter and the scorer read."""
    csv = write_gate_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="defects")
    loaded = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)

    for reason in gate_defects():
        assert loaded.report.rejection_reasons.get(reason), (
            reason,
            loaded.report.rejection_reasons,
        )

    # P0001 goes too: its label now contradicts itself, and the gate keeps neither
    # side of a contradiction.
    assert set(loaded.frame["passenger_record_id"]) == CLEAN_IDS - {"P0001"}
    assert len(loaded.frame) == loaded.report.valid_rows
    assert loaded.rejected_rows == TOTAL_GATE_ROWS - loaded.report.valid_rows


def test_rejected_rows_are_removed_from_both_fit_and_score_inputs(tmp_path):
    """A label the report calls censored must not be scored as a negative."""
    csv = write_gate_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="defects")
    loaded = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)

    assert "CENSORED" not in set(loaded.frame["final_chart_status"])
    assert "MYSTERY/4" not in set(loaded.frame["initial_status"])
    assert "AB1234" not in set(loaded.frame["train_number"])
    assert "" not in set(loaded.frame["class_code"])


def test_a_technically_ineligible_dataset_is_refused_for_real_training(tmp_path):
    """Regression: structural validity was the whole gate.

    24 parseable rows are structurally fine and nowhere near enough to evaluate a
    probability. Only the labelled synthetic pipeline path may fit them."""
    csv = write_gate_dataset(tmp_path, synthetic="false")
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="too-small")
    with pytest.raises(TrainingDataError, match="not technically eligible") as exc:
        load_approved_dataset(csv, manifest)
    message = str(exc.value)
    assert "provisional minimum" in message
    assert "structurally valid" in message


def test_a_real_dataset_is_not_rescued_by_the_synthetic_opt_in(tmp_path):
    """Without is_synthetic there is no relaxation, whatever else the caller passes."""
    csv = write_gate_dataset(tmp_path, synthetic="false")
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="real-small")
    with pytest.raises(TrainingDataError, match="not technically eligible"):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def test_the_pipeline_test_relaxation_is_recorded_on_the_dataset(tmp_path):
    csv = write_gate_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="relaxed")
    loaded = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    assert loaded.eligibility_relaxed is True
    assert loaded.report.technically_eligible is False


def test_an_eligible_dataset_is_never_marked_relaxed(dataset):
    csv, manifest = dataset
    loaded = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    assert loaded.report.technically_eligible is True
    assert loaded.eligibility_relaxed is False


def test_a_synthetic_marker_on_a_rejected_row_still_marks_the_file(tmp_path):
    """Detection reads the file, not the surviving rows, so it cannot be laundered.

    The only row declaring is_synthetic is one the validator drops for observing
    after the journey. Reading the verdict from the kept frame would hand a frame
    that looks entirely real to whoever fits it."""
    csv = write_gate_dataset(tmp_path, synthetic="false", defects=False)
    laundered = Path(csv).with_name("laundered.csv")
    laundered.write_text(
        csv.read_text(encoding="utf-8").rstrip("\n")
        + "\n12301,2026-04-01,SL,GN,GNWL/90,CNF,2026-04-05,B9100,P9100,true\n",
        encoding="utf-8",
    )
    manifest = write_approved_manifest(laundered, tmp_path, dataset_id="laundered")

    with pytest.raises(TrainingDataError, match="is_synthetic"):
        load_approved_dataset(laundered, manifest)

    loaded = load_approved_dataset(laundered, manifest, allow_synthetic_for_testing=True)
    assert loaded.report.rejection_reasons["observation_after_journey"] == 1
    assert loaded.is_synthetic is True
    assert not any(
        str(value).strip().lower() in {"true", "1", "yes"}
        for value in loaded.frame["is_synthetic"]
    )


def test_eligibility_is_checked_after_the_permission_rules(tmp_path):
    """A rejected licence stays the headline reason even when intake also fails."""
    csv = write_gate_dataset(tmp_path, synthetic="false")
    manifest = write_approved_manifest(
        csv, tmp_path, dataset_id="both-bad", decision=approved_decision(decision="rejected")
    )
    with pytest.raises(TrainingDataError, match="rejected"):
        load_approved_dataset(csv, manifest)


@pytest.fixture
def dataset(tmp_path: Path):
    csv = write_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    return csv, manifest


def test_approved_dataset_loads(dataset):
    csv, manifest = dataset
    loaded = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    assert loaded.report.valid_rows > 0
    assert loaded.is_synthetic is True
    assert len(loaded.sha256) == 64


def test_synthetic_rows_are_blocked_without_an_explicit_opt_in(dataset):
    """The gate's whole purpose: pipeline testing must not become a real claim."""
    csv, manifest = dataset
    with pytest.raises(TrainingDataError, match="is_synthetic"):
        load_approved_dataset(csv, manifest)


def test_unverified_manifest_is_refused(dataset, tmp_path):
    csv, manifest = dataset
    tampered = tmp_path / "tampered.yaml"
    text = manifest.read_text(encoding="utf-8").replace("row_count: 240", "row_count: 999")
    tampered.write_text(text, encoding="utf-8")
    with pytest.raises(TrainingDataError, match="row_count"):
        load_approved_dataset(
            csv, tampered, allow_synthetic_for_testing=True
        )


def test_changed_file_content_is_refused(dataset, tmp_path):
    csv, manifest = dataset
    edited = tmp_path / "edited.csv"
    edited.write_bytes(csv.read_bytes() + b"12301,2026-07-01,SL,GN,GNWL/9,CNF,2026-06-01,B9,P9,true\n")
    with pytest.raises(TrainingDataError, match="content changed"):
        load_approved_dataset(edited, manifest, allow_synthetic_for_testing=True)


@pytest.mark.parametrize(
    "decision_kwargs,fragment",
    [
        ({"decision": "under_review", "reviewed_by": None, "reviewed_on": None}, "requires an explicit"),
        ({"decision": "quarantined", "reviewed_by": "R.", "reviewed_on": "2026-04-02"}, "quarantined"),
        ({"decision": "rejected", "reviewed_by": "R.", "reviewed_on": "2026-04-02"}, "rejected"),
        ({"decision": "restricted", "reviewed_by": "R.", "reviewed_on": "2026-04-02"}, "restricted"),
    ],
)
def test_non_approved_decision_is_refused(dataset, tmp_path, decision_kwargs, fragment):
    csv, _ = dataset
    manifest = write_approved_manifest(
        csv, tmp_path, dataset_id="scenario", decision=approved_decision(**decision_kwargs)
    )
    with pytest.raises(TrainingDataError, match=fragment):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def test_approval_without_a_named_reviewer_is_refused(dataset, tmp_path):
    """The manifest model rejects this on construction, before training is reached."""
    csv, _ = dataset
    from railconfirm.data.manifest import ManifestError

    with pytest.raises(ManifestError, match="reviewed_by"):
        write_approved_manifest(
            csv,
            tmp_path,
            dataset_id="no-reviewer",
            decision=approved_decision(reviewed_by=None),
        )


@pytest.mark.parametrize(
    "source_overrides,fragment",
    [
        ({"licence_review_status": "pending"}, "licence_review_status"),
        ({"licence_review_status": "restricted"}, "licence_review_status"),
    ],
)
def test_unreviewed_licence_is_refused(dataset, tmp_path, source_overrides, fragment):
    csv, _ = dataset
    manifest = write_approved_manifest(
        csv, tmp_path, dataset_id="licence-case", source=approved_source(**source_overrides)
    )
    with pytest.raises(TrainingDataError, match=fragment):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def test_licence_approved_without_training_permission_is_refused(dataset, tmp_path):
    """The manifest cannot even express this contradiction, so the gate is two-layered."""
    csv, _ = dataset
    from railconfirm.data.manifest import AllowedUses, ManifestError

    with pytest.raises(ManifestError, match="model_training"):
        approved_source(
            allowed_uses=AllowedUses(model_training="unknown"),
            licence_review_status="approved",
        )


def test_restricted_training_use_is_refused_even_with_an_approved_licence(dataset, tmp_path):
    """A licence reviewed as "approved" but permitting only restricted training is not
    a training permission; the two fields are checked separately on purpose."""
    csv, _ = dataset
    from railconfirm.data.manifest import AllowedUses

    manifest = write_approved_manifest(
        csv,
        tmp_path,
        dataset_id="use-restricted",
        source=approved_source(allowed_uses=AllowedUses(model_training="restricted")),
        decision=approved_decision(),
    )
    with pytest.raises(TrainingDataError, match="model_training"):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


@pytest.mark.parametrize("status", ["pending", "restricted", "rejected"])
def test_licence_review_order_is_checked_before_training_use(dataset, tmp_path, status):
    """Both are blockers; the message names the first one so a reviewer fixes in order."""
    csv, _ = dataset
    manifest = write_approved_manifest(
        csv,
        tmp_path,
        dataset_id=f"licence-{status}",
        source=approved_source(
            licence_review_status=status,
            allowed_uses=approved_source().allowed_uses,
        ),
    )
    with pytest.raises(TrainingDataError, match="licence_review_status"):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def test_missing_files_are_reported(tmp_path):
    with pytest.raises(TrainingDataError, match="Dataset file not found"):
        load_approved_dataset(tmp_path / "nope.csv", tmp_path / "nope.yaml")
    csv = write_dataset(tmp_path)
    with pytest.raises(TrainingDataError, match="Manifest file not found"):
        load_approved_dataset(csv, tmp_path / "nope.yaml")


def test_structurally_invalid_dataset_is_refused(tmp_path):
    path = tmp_path / "broken.csv"
    path.write_text(
        "train_number,journey_date\n12301,2026-04-01\n", encoding="utf-8"
    )
    manifest = write_approved_manifest(path, tmp_path, dataset_id="broken")
    with pytest.raises(TrainingDataError, match="structurally valid|Schema incomplete"):
        load_approved_dataset(path, manifest, allow_synthetic_for_testing=True)
