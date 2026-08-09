#!/usr/bin/env python3
"""Shared manifest and file helpers for the adaptive TPR card workflow."""

from __future__ import annotations

import csv
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Iterable


DELIVERY_CHOICES = {"zip", "word", "both"}
WORD_IDENTIFIER_VISIBILITIES = {"hidden", "shown"}
DEFAULT_WORD_IDENTIFIER_VISIBILITY = "hidden"


def read_manifest(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        required = {
            "source_row",
            "raw_identifier",
            "number",
            "english",
            "chinese",
            "output_path",
        }
        if not required.issubset(fieldnames):
            raise ValueError(f"Manifest must contain {sorted(required)}")
        rows: list[dict[str, str]] = []
        profile_fields = {
            "character_id",
            "character_profile_version",
            "character_profile_sha256",
        }
        present_profile_fields = profile_fields & set(fieldnames)
        if present_profile_fields and present_profile_fields != profile_fields:
            raise ValueError(
                "Manifest has a partial character-profile schema; missing "
                f"{sorted(profile_fields - present_profile_fields)}"
            )
        seen: dict[str, int] = {}
        seen_casefold: dict[str, tuple[str, int]] = {}
        seen_numeric: dict[int, tuple[str, int]] = {}
        for source_line, raw_row in enumerate(reader, start=2):
            row = {key: (value or "") for key, value in raw_row.items() if key}
            for exact_field in (
                "source_row",
                "raw_identifier",
                "number",
                "english",
                "chinese",
                "character_id",
                "character_profile_version",
                "character_profile_sha256",
            ):
                value = row.get(exact_field, "")
                if value != value.strip():
                    raise ValueError(
                        f"Manifest line {source_line} field {exact_field!r} has leading or trailing whitespace"
                    )
            identifier = row.get("number", "")
            if not identifier:
                raise ValueError(f"Manifest line {source_line} has an empty normalized identifier")
            if not row.get("source_row", "").isdigit():
                raise ValueError(f"Manifest line {source_line} has an invalid source_row")
            if not row.get("english", "") or not row.get("chinese", ""):
                raise ValueError(f"Manifest line {source_line} has empty English or Chinese text")
            if present_profile_fields:
                if not row.get("character_id", ""):
                    raise ValueError(f"Manifest line {source_line} has an empty character_id")
                if not row.get("character_profile_version", "").isdigit():
                    raise ValueError(
                        f"Manifest line {source_line} has an invalid character_profile_version"
                    )
                profile_hash = row.get("character_profile_sha256", "")
                if len(profile_hash) != 64 or any(
                    character not in "0123456789abcdef" for character in profile_hash.casefold()
                ):
                    raise ValueError(
                        f"Manifest line {source_line} has an invalid character_profile_sha256"
                    )
            if identifier in seen:
                raise ValueError(
                    f"Duplicate manifest identifier {identifier!r} on lines "
                    f"{seen[identifier]} and {source_line}"
                )
            seen[identifier] = source_line
            folded = identifier.casefold()
            if folded in seen_casefold:
                other, other_line = seen_casefold[folded]
                raise ValueError(
                    f"Case-insensitive identifier collision {other!r}/{identifier!r} "
                    f"on lines {other_line} and {source_line}"
                )
            seen_casefold[folded] = (identifier, source_line)
            if identifier.isdigit():
                numeric = int(identifier)
                if numeric in seen_numeric:
                    other, other_line = seen_numeric[numeric]
                    raise ValueError(
                        f"Numeric-equivalent identifiers {other!r}/{identifier!r} "
                        f"on lines {other_line} and {source_line}"
                    )
                seen_numeric[numeric] = (identifier, source_line)
            row["_source_line"] = str(source_line)
            rows.append(row)
    return fieldnames, rows


def select_rows(
    rows: list[dict[str, str]],
    *,
    start: int | None = None,
    end: int | None = None,
    identifiers: Iterable[str] = (),
) -> list[dict[str, str]]:
    requested = list(identifiers)
    if (start is None) != (end is None):
        raise ValueError("--start and --end must be supplied together")
    if requested and start is not None:
        raise ValueError("Use either --id or --start/--end, not both")

    if requested:
        wanted = set(requested)
        selected = [row for row in rows if row["number"] in wanted]
        selected_ids = {row["number"] for row in selected}
        missing = [identifier for identifier in requested if identifier not in selected_ids]
        if missing:
            raise ValueError(f"Manifest is missing requested identifiers: {missing}")
        return selected

    if start is not None and end is not None:
        if start > end:
            raise ValueError("--start must not exceed --end")
        numeric: dict[int, dict[str, str]] = {}
        for row in rows:
            identifier = row["number"]
            if not identifier.isdigit():
                continue
            value = int(identifier)
            if start <= value <= end:
                if value in numeric:
                    raise ValueError(
                        f"Numeric-equivalent identifiers in selection: "
                        f"{numeric[value]['number']!r} and {identifier!r}"
                    )
                numeric[value] = row
        missing = [value for value in range(start, end + 1) if value not in numeric]
        if missing:
            raise ValueError(f"Manifest is missing numeric identifiers: {missing}")
        return [numeric[value] for value in range(start, end + 1)]

    return list(rows)


def resolve_card_path(cards_dir: Path, row: dict[str, str]) -> Path:
    configured = row.get("output_path", "").strip()
    if configured:
        candidate = cards_dir / Path(configured).name
        if candidate.suffix.lower() != ".png":
            raise ValueError(
                f"Manifest output_path for {row['number']} is not a PNG: {configured}"
            )
        return candidate

    identifier = row["number"]
    matches = sorted(
        path
        for path in cards_dir.glob("*.png")
        if path.name.startswith(identifier + "_") and path.name.lower().endswith("_a4.png")
    )
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one PNG beginning {identifier!r} and ending '_A4.png'; "
            f"found {len(matches)}"
        )
    return matches[0]


def expected_card_map(
    cards_dir: Path, rows: list[dict[str, str]]
) -> dict[str, tuple[Path, dict[str, str]]]:
    result: dict[str, tuple[Path, dict[str, str]]] = {}
    for row in rows:
        path = resolve_card_path(cards_dir, row)
        if path.name in result:
            other = result[path.name][1]["number"]
            raise ValueError(
                f"Manifest identifiers {other!r} and {row['number']!r} resolve to {path.name!r}"
            )
        result[path.name] = (path, row)
    return result


def require_delivery_choice(rows: list[dict[str, str]], target: str) -> None:
    if target not in {"zip", "word"}:
        raise ValueError(f"Unknown delivery target: {target}")
    problems: list[str] = []
    for row in rows:
        choice = row.get("delivery_format", "").strip().casefold()
        if choice not in DELIVERY_CHOICES:
            problems.append(f"{row['number']}: delivery_format is not zip, word, or both")
        elif target == "zip" and choice not in {"zip", "both"}:
            problems.append(f"{row['number']}: user selected {choice}, not ZIP")
        elif target == "word" and choice not in {"word", "both"}:
            problems.append(f"{row['number']}: user selected {choice}, not Word")
    if problems:
        raise ValueError("Delivery choice is not confirmed:\n- " + "\n- ".join(problems))


def resolve_word_identifier_visibility(
    rows: list[dict[str, str]], override: str | None = None
) -> str:
    """Resolve one batch-wide Word identifier policy, defaulting legacy rows to hidden."""
    declared = {
        row.get("word_identifier_visibility", "").strip().casefold()
        for row in rows
        if row.get("word_identifier_visibility", "").strip()
    }
    invalid = sorted(declared - WORD_IDENTIFIER_VISIBILITIES)
    if invalid:
        raise ValueError(f"Invalid Word identifier visibility values: {invalid}")
    if len(declared) > 1:
        raise ValueError(
            f"Selected rows mix Word identifier visibility values: {sorted(declared)}"
        )

    requested = override.strip().casefold() if override else ""
    if requested and requested not in WORD_IDENTIFIER_VISIBILITIES:
        raise ValueError(f"Invalid Word identifier visibility override: {override!r}")
    recorded = next(iter(declared), DEFAULT_WORD_IDENTIFIER_VISIBILITY)
    if requested and declared and requested != recorded:
        raise ValueError(
            f"Word identifier visibility override {requested!r} conflicts with "
            f"manifest value {recorded!r}"
        )
    return requested or recorded


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
