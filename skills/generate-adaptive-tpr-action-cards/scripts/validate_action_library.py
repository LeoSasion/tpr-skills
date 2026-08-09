#!/usr/bin/env python3
"""Validate the canonical bilingual 200-action preset library."""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path


REQUIRED_FIELDS = {"number", "english", "chinese"}
SUITABILITY_HANDLING = {
    "confirm-or-neutralize",
    "partial-cue-only",
    "explicit-context-only",
    "symbolic-safe-only",
    "layered-safe-only",
}
SUITABILITY_FIELDS = {"number", "context_tags", "default_handling", "adaptation_note"}


def normalize_english(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def normalize_chinese(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(character for character in normalized if character.isalnum())


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_FIELDS.issubset(reader.fieldnames or []):
            raise ValueError(f"Action library must contain {sorted(REQUIRED_FIELDS)}")
        return [
            {key: (value or "") for key, value in raw.items() if key}
            for raw in reader
        ]


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    if len(rows) != 200:
        errors.append(f"Expected 200 action rows; found {len(rows)}")

    seen_english: dict[str, tuple[str, int]] = {}
    seen_chinese: dict[str, tuple[str, int]] = {}
    for index, row in enumerate(rows, start=1):
        line = index + 1
        expected_number = f"{index:03d}"
        number = row.get("number", "")
        english = row.get("english", "")
        chinese = row.get("chinese", "")

        if number != expected_number:
            errors.append(
                f"Line {line}: expected number {expected_number!r}; found {number!r}"
            )
        for field, value in (("english", english), ("chinese", chinese)):
            if not value:
                errors.append(f"Line {line}: {field} is empty")
            elif value != value.strip():
                errors.append(f"Line {line}: {field} has leading or trailing whitespace")

        english_key = normalize_english(english)
        if english_key:
            if english_key in seen_english:
                other_number, other_line = seen_english[english_key]
                errors.append(
                    f"Lines {other_line}/{line}: normalized English repeats for "
                    f"{other_number}/{number}: {english!r}"
                )
            else:
                seen_english[english_key] = (number, line)

        chinese_key = normalize_chinese(chinese)
        if chinese_key:
            if chinese_key in seen_chinese:
                other_number, other_line = seen_chinese[chinese_key]
                errors.append(
                    f"Lines {other_line}/{line}: Chinese label repeats for "
                    f"{other_number}/{number}: {chinese!r}"
                )
            else:
                seen_chinese[chinese_key] = (number, line)
    return errors


def load_validated_library(path: Path) -> dict[str, dict[str, str]]:
    rows = read_rows(path)
    errors = validate_rows(rows)
    if errors:
        raise ValueError("Invalid action library:\n- " + "\n- ".join(errors))
    return {row["number"]: row for row in rows}


def validate_semantics(
    path: Path, library_rows: list[dict[str, str]]
) -> list[str]:
    errors: list[str] = []
    canonical_pairs = {
        (row["english"], row["chinese"]): row["number"] for row in library_rows
    }
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"semantic_id", "english", "chinese", "status"}
        if not required.issubset(reader.fieldnames or []):
            return [f"Semantics library must contain {sorted(required)}"]
        seen_ids: dict[str, int] = {}
        seen_english: dict[str, tuple[str, int]] = {}
        for line, raw in enumerate(reader, start=2):
            row = {key: (value or "") for key, value in raw.items() if key}
            semantic_id = row["semantic_id"]
            if not semantic_id:
                errors.append(f"Semantics line {line}: semantic_id is empty")
            elif semantic_id in seen_ids:
                errors.append(
                    f"Semantics lines {seen_ids[semantic_id]}/{line}: "
                    f"duplicate semantic_id {semantic_id!r}"
                )
            else:
                seen_ids[semantic_id] = line

            pair = (row["english"], row["chinese"])
            if pair not in canonical_pairs:
                errors.append(
                    f"Semantics line {line}: {semantic_id!r} does not exactly match "
                    "any canonical English-Chinese pair"
                )
            if row["status"] != "approved":
                errors.append(
                    f"Semantics line {line}: {semantic_id!r} is not approved"
                )

            english_key = normalize_english(row["english"])
            if english_key in seen_english:
                other_id, other_line = seen_english[english_key]
                errors.append(
                    f"Semantics lines {other_line}/{line}: normalized English repeats "
                    f"for {other_id!r}/{semantic_id!r}"
                )
            else:
                seen_english[english_key] = (semantic_id, line)
    return errors


def read_suitability(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) != SUITABILITY_FIELDS:
            return [], [f"Action suitability must contain exactly {sorted(SUITABILITY_FIELDS)}"]
        for line, raw in enumerate(reader, start=2):
            if raw.get(None):
                errors.append(f"Suitability line {line}: unexpected extra CSV columns")
            row = {key: (value or "") for key, value in raw.items() if key}
            row["_source_line"] = str(line)
            rows.append(row)
    return rows, errors


def validate_suitability_rows(
    rows: list[dict[str, str]], library_rows: list[dict[str, str]]
) -> list[str]:
    errors: list[str] = []
    valid_numbers = {row["number"] for row in library_rows}
    seen: dict[str, int] = {}
    for row in rows:
        line = int(row.get("_source_line", "0"))
        number = row.get("number", "")
        if number not in valid_numbers:
            errors.append(f"Suitability line {line}: unknown action number {number!r}")
        elif number in seen:
            errors.append(
                f"Suitability lines {seen[number]}/{line}: duplicate action {number}"
            )
        else:
            seen[number] = line
        if not row.get("context_tags"):
            errors.append(f"Suitability line {line}: context_tags is empty")
        if row.get("default_handling") not in SUITABILITY_HANDLING:
            errors.append(
                f"Suitability line {line}: unsupported default_handling "
                f"{row.get('default_handling')!r}"
            )
        if not row.get("adaptation_note"):
            errors.append(f"Suitability line {line}: adaptation_note is empty")
    return errors


def validate_suitability(
    path: Path, library_rows: list[dict[str, str]]
) -> list[str]:
    rows, errors = read_suitability(path)
    return errors + validate_suitability_rows(rows, library_rows)


def load_validated_suitability(
    path: Path, library_rows: list[dict[str, str]]
) -> dict[str, dict[str, str]]:
    rows, errors = read_suitability(path)
    errors.extend(validate_suitability_rows(rows, library_rows))
    if errors:
        raise ValueError("Invalid action suitability rules:\n- " + "\n- ".join(errors))
    return {row["number"]: row for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--semantics", type=Path)
    parser.add_argument("--suitability", type=Path)
    args = parser.parse_args()

    rows = read_rows(args.library)
    errors = validate_rows(rows)
    if args.semantics:
        errors.extend(validate_semantics(args.semantics, rows))
    if args.suitability:
        errors.extend(validate_suitability(args.suitability, rows))
    if errors:
        print("ACTION LIBRARY CHECK FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    validated_extras = []
    if args.semantics:
        validated_extras.append("semantics")
    if args.suitability:
        validated_extras.append("suitability rules")
    extras_note = f" and all {' and '.join(validated_extras)}" if validated_extras else ""
    print(
        f"ACTION LIBRARY CHECK PASSED: 200 unique English and Chinese rows{extras_note}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
