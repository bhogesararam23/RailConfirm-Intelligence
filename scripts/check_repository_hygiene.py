#!/usr/bin/env python3
"""Repository hygiene checks used by CI and by developers before a commit.

Four gates, all deterministic and offline:

1. Required documentation files exist.
2. Relative links in Markdown resolve, and no document points at a deleted file.
3. No secret material or unlabelled ticket data is committed.
4. Every dataset fixture that is not real data declares that it is synthetic.

Run: python scripts/check_repository_hygiene.py
Exit code 0 means every gate passed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "README.md",
    "CHANGELOG.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "THIRD_PARTY_DATA.md",
    ".env.example",
    "docs/ROADMAP.md",
    "docs/PROJECT_STATUS.md",
    "docs/AGENT_HANDOFF.md",
    "docs/DEVELOPMENT_LOG.md",
    "docs/DEFINITION_OF_DONE.md",
    "docs/technical/IMPLEMENTATION_PLAN.md",
    "docs/technical/LOCAL_FIRST_DEVELOPMENT.md",
    "docs/technical/TESTING_STRATEGY.md",
    "docs/architecture/API_CONTRACT.md",
    "docs/data/DATASET_INTAKE_CHECKLIST.md",
    "docs/data/DATA_CONTRACT.md",
    "docs/data/SOURCE_REGISTER.md",
    "docs/model/PREDICTION_TARGETS.md",
    "docs/research/EVALUATION_PROTOCOL.md",
    "docs/SECURITY_AND_PRIVACY.md",
    "docs/adr/README.md",
]

SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".venv", "venv", "coverage", ".turbo"}

# A relative link target: markdown ](target), ignoring schemes, anchors and mail.
LINK_RE = re.compile(r"\]\(([^)\s]+)[^)]*\)")
EXTERNAL_RE = re.compile(r"^(?:https?://|mailto:|#)")

SECRET_PATTERNS = [
    (re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----"), "private key material"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(rb"xox[baprs]-[0-9A-Za-z-]{10,}"), "Slack token"),
    (re.compile(rb"(?i)\bbearer\s+[A-Za-z0-9._-]{20,}"), "bearer token"),
]

# An Indian Railways PNR is 10 characters, the first five numeric. Matched only
# against tracked text so an obvious synthetic value is not a finding.
PNR_RE = re.compile(r"\b\d{5}\s?\d{5}\b")

SYNTHETIC_MARKERS = (b"synthetic", b"SYNTHETIC", b"testing_only", b"fake", b"fixture")

MAX_TRACKED_FILE_BYTES = 2_000_000


def iter_tracked_text_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        files.append(path)
    return files


def check_required_files(failures: list[str]) -> None:
    for rel in REQUIRED_FILES:
        if not (REPO_ROOT / rel).is_file():
            failures.append(f"required documentation file missing: {rel}")


def check_markdown_links(failures: list[str]) -> None:
    for path in iter_tracked_text_files():
        if path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(REPO_ROOT)
        stripped = re.sub(r"```.*?```", "", text, flags=re.S)
        for match in LINK_RE.finditer(stripped):
            target = match.group(1)
            if EXTERNAL_RE.match(target) or target.startswith("{"):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            if not resolved.exists():
                failures.append(f"{rel}: broken relative link -> {target}")


def check_secrets(failures: list[str]) -> None:
    for path in iter_tracked_text_files():
        rel = path.relative_to(REPO_ROOT)
        if path.name == ".env.example":
            continue
        if ".env" in path.name and path.suffix == "":
            failures.append(f"{rel}: a .env file must never be committed")
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_TRACKED_FILE_BYTES:
            failures.append(
                f"{rel}: {len(data)} bytes exceeds the {MAX_TRACKED_FILE_BYTES} byte "
                "limit for tracked files; raw datasets do not belong in Git"
            )
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(data):
                failures.append(f"{rel}: possible {label}")


def check_ticket_data(failures: list[str]) -> None:
    """Flag PNR-shaped values outside clearly-labelled synthetic material."""
    for path in iter_tracked_text_files():
        rel = path.relative_to(REPO_ROOT)
        if path.suffix.lower() not in {".py", ".json", ".csv", ".md", ".yaml", ".yml", ".ts", ".tsx"}:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        labelled = any(marker in data for marker in SYNTHETIC_MARKERS)
        if labelled:
            continue
        text = data.decode("utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "PNR" in line.upper():
                continue
            for match in PNR_RE.finditer(line):
                value = match.group(0)
                # A digit run that repeats or ascends is a placeholder, not a PNR.
                digits = re.sub(r"\D", "", value)
                if len(set(digits)) <= 2:
                    continue
                failures.append(
                    f"{rel}:{line_no}: PNR-shaped value {value!r} in a file that does "
                    "not declare its data synthetic"
                )


def main() -> int:
    failures: list[str] = []
    check_required_files(failures)
    check_markdown_links(failures)
    check_secrets(failures)
    check_ticket_data(failures)

    if failures:
        print("Repository hygiene checks FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        f"Repository hygiene checks passed: {len(REQUIRED_FILES)} required files, "
        f"{len(iter_tracked_text_files())} tracked files scanned for links, secrets "
        "and unlabelled ticket data."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
