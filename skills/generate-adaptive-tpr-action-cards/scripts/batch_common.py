#!/usr/bin/env python3
"""Shared manifest and file helpers for the adaptive TPR card workflow."""

from __future__ import annotations

import csv
import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable


DELIVERY_CHOICES = {"zip", "word", "both"}
WORD_IDENTIFIER_VISIBILITIES = {"hidden", "shown"}
DEFAULT_WORD_IDENTIFIER_VISIBILITY = "hidden"
SUBAGENT_PARALLELISM_CHOICES = {"enabled", "disabled", "custom"}
DEFAULT_SUBAGENT_CONCURRENCY = 4
BACKGROUND_MODES = {"auto-varied", "pure-white"}
EXECUTION_BACKGROUND_FIELDS = (
    "subagent_parallelism",
    "subagent_concurrency",
    "background_mode",
    "background_treatment",
)
GENERATION_BACKEND_MODES = {"recommended", "custom"}
RECOMMENDED_GENERATION_INTERFACE = "imagegen"
RECOMMENDED_GENERATION_MODEL = "Codex 5.6 Luna Max"
GENERATION_BACKEND_FIELDS = (
    "generation_backend_mode",
    "generation_interface",
    "generation_model",
)
WARDROBE_SELECTION_FIELDS = (
    "wardrobe_library_version",
    "wardrobe_recommendation_method",
    "wardrobe_recommendation_fingerprint",
    "wardrobe_evidence_basis",
    "color_direction_id",
    "color_direction_label",
    "color_choice_round",
    "color_choice_option",
    "style_family_id",
    "style_family_label",
    "style_choice_round",
    "style_choice_option",
    "wardrobe_custom_override",
)
WARDROBE_RECOMMENDATION_METHODS = {
    "model-curated",
    "user-specified",
    "not-applicable",
}


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
        wardrobe_fields = set(WARDROBE_SELECTION_FIELDS)
        present_wardrobe_fields = wardrobe_fields & set(fieldnames)
        if present_wardrobe_fields and present_wardrobe_fields != wardrobe_fields:
            raise ValueError(
                "Manifest has a partial two-round wardrobe schema; missing "
                f"{sorted(wardrobe_fields - present_wardrobe_fields)}"
            )
        execution_background_fields = set(EXECUTION_BACKGROUND_FIELDS)
        present_execution_background_fields = execution_background_fields & set(fieldnames)
        if (
            present_execution_background_fields
            and present_execution_background_fields != execution_background_fields
        ):
            raise ValueError(
                "Manifest has a partial execution/background schema; missing "
                f"{sorted(execution_background_fields - present_execution_background_fields)}"
            )
        generation_backend_fields = set(GENERATION_BACKEND_FIELDS)
        present_generation_backend_fields = generation_backend_fields & set(fieldnames)
        if (
            present_generation_backend_fields
            and present_generation_backend_fields != generation_backend_fields
        ):
            raise ValueError(
                "Manifest has a partial generation-backend schema; missing "
                f"{sorted(generation_backend_fields - present_generation_backend_fields)}"
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
                *WARDROBE_SELECTION_FIELDS,
                *EXECUTION_BACKGROUND_FIELDS,
                *GENERATION_BACKEND_FIELDS,
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


def validate_wardrobe_provenance(row: dict[str, str]) -> list[str]:
    """Validate one row's two-round selection record without inferring aesthetics."""
    errors: list[str] = []
    policy = row.get("wardrobe_policy", "")
    method = row.get("wardrobe_recommendation_method", "")
    identifier = row.get("number", "?")
    if method not in WARDROBE_RECOMMENDATION_METHODS:
        return [f"{identifier}: invalid wardrobe_recommendation_method {method!r}"]

    if policy in {"fixed", "none"}:
        expected_na = (
            "wardrobe_library_version",
            "wardrobe_evidence_basis",
            "color_direction_id",
            "color_direction_label",
            "style_family_id",
            "style_family_label",
            "wardrobe_custom_override",
        )
        if method != "not-applicable":
            errors.append(f"{identifier}: {policy} wardrobe must use not-applicable recommendation method")
        for field in expected_na:
            if row.get(field, "").casefold() != "not-applicable":
                errors.append(f"{identifier}: {policy} wardrobe requires {field}=not-applicable")
        for field in ("color_choice_round", "color_choice_option", "style_choice_round", "style_choice_option"):
            if row.get(field, "") != "0":
                errors.append(f"{identifier}: {policy} wardrobe requires {field}=0")
        if row.get("wardrobe_recommendation_fingerprint", "") != "0" * 64:
            errors.append(f"{identifier}: {policy} wardrobe requires a zero recommendation fingerprint")
        return errors

    if method == "not-applicable":
        errors.append(f"{identifier}: varied wardrobe requires a selected color and style direction")
        return errors
    if not row.get("wardrobe_library_version", ""):
        errors.append(f"{identifier}: wardrobe_library_version is empty")
    digest = row.get("wardrobe_recommendation_fingerprint", "").casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append(f"{identifier}: wardrobe_recommendation_fingerprint is invalid")
    if not row.get("wardrobe_evidence_basis", ""):
        errors.append(f"{identifier}: wardrobe_evidence_basis is empty")
    if not row.get("color_direction_label", "") or not row.get("style_family_label", ""):
        errors.append(f"{identifier}: color/style labels must be recorded")

    color_id = row.get("color_direction_id", "").upper()
    style_id = row.get("style_family_id", "").upper()
    if method == "model-curated":
        if not re.fullmatch(r"C\d{2}", color_id):
            errors.append(f"{identifier}: model-curated color_direction_id is invalid")
        if not re.fullmatch(r"S\d{2}", style_id):
            errors.append(f"{identifier}: model-curated style_family_id is invalid")
        if row.get("wardrobe_custom_override", ""):
            errors.append(f"{identifier}: model-curated selection must leave wardrobe_custom_override empty")
        numeric_constraints = {
            "color_choice_round": (1, None),
            "color_choice_option": (1, 3),
            "style_choice_round": (1, None),
            "style_choice_option": (1, 3),
        }
    else:
        if color_id != "CUSTOM" and not re.fullmatch(r"C\d{2}", color_id):
            errors.append(f"{identifier}: user-specified color_direction_id is invalid")
        if style_id != "CUSTOM" and not re.fullmatch(r"S\d{2}", style_id):
            errors.append(f"{identifier}: user-specified style_family_id is invalid")
        if not row.get("wardrobe_custom_override", ""):
            errors.append(f"{identifier}: user-specified selection must record wardrobe_custom_override")
        numeric_constraints = {
            "color_choice_round": (0, None),
            "color_choice_option": (0, 3),
            "style_choice_round": (0, None),
            "style_choice_option": (0, 3),
        }

    for field, (minimum, maximum) in numeric_constraints.items():
        try:
            value = int(row.get(field, ""))
        except ValueError:
            errors.append(f"{identifier}: {field} is not an integer")
            continue
        if value < minimum or (maximum is not None and value > maximum):
            errors.append(f"{identifier}: {field} is outside its allowed range")
    return errors


def validate_execution_background_rows(rows: list[dict[str, str]]) -> list[str]:
    """Validate the user-selected concurrency policy and background mode."""
    errors: list[str] = []
    for row in rows:
        identifier = row.get("number", "?")
        subagent_policy = row.get("subagent_parallelism", "").strip().casefold()
        if subagent_policy not in SUBAGENT_PARALLELISM_CHOICES:
            errors.append(
                f"{identifier}: subagent_parallelism must be enabled, disabled, or custom"
            )
        concurrency_text = row.get("subagent_concurrency", "").strip()
        try:
            concurrency = int(concurrency_text)
        except ValueError:
            errors.append(f"{identifier}: subagent_concurrency must be a positive integer")
            concurrency = None
        if concurrency is not None:
            if concurrency < 1:
                errors.append(
                    f"{identifier}: subagent_concurrency must be a positive integer"
                )
            elif subagent_policy == "enabled" and concurrency != DEFAULT_SUBAGENT_CONCURRENCY:
                errors.append(
                    f"{identifier}: enabled requires "
                    f"subagent_concurrency={DEFAULT_SUBAGENT_CONCURRENCY}"
                )
            elif subagent_policy == "disabled" and concurrency != 1:
                errors.append(
                    f"{identifier}: disabled requires subagent_concurrency=1"
                )

        background_mode = row.get("background_mode", "").strip().casefold()
        treatment = " ".join(
            row.get("background_treatment", "").strip().casefold().split()
        )
        if background_mode not in BACKGROUND_MODES:
            errors.append(
                f"{identifier}: background_mode must be auto-varied or pure-white"
            )
        elif background_mode == "pure-white":
            if treatment != "pure-white":
                errors.append(
                    f"{identifier}: pure-white mode requires background_treatment=pure-white"
                )
        elif not treatment or treatment == "pure-white":
            errors.append(
                f"{identifier}: auto-varied mode requires a non-white recorded background_treatment"
            )

    subagent_policies = {
        row.get("subagent_parallelism", "").strip().casefold() for row in rows
    }
    if len(subagent_policies) > 1:
        errors.append(
            "Batch contains multiple subagent_parallelism values: "
            f"{sorted(subagent_policies)}"
        )
    subagent_concurrencies = {
        row.get("subagent_concurrency", "").strip() for row in rows
    }
    if len(subagent_concurrencies) > 1:
        errors.append(
            "Batch contains multiple subagent_concurrency values: "
            f"{sorted(subagent_concurrencies)}"
        )

    background_modes = {
        row.get("background_mode", "").strip().casefold() for row in rows
    }
    if len(background_modes) > 1:
        errors.append(
            f"Batch contains multiple background_mode values: {sorted(background_modes)}"
        )
    elif background_modes == {"auto-varied"}:
        treatments = [
            " ".join(row.get("background_treatment", "").strip().casefold().split())
            for row in rows
        ]
        for left, right, left_row, right_row in zip(
            treatments,
            treatments[1:],
            rows,
            rows[1:],
        ):
            if left == right:
                errors.append(
                    f"{left_row['number']}/{right_row['number']}: consecutive auto-varied "
                    "background treatments repeat"
                )
        if len(rows) < 4 and len(treatments) != len(set(treatments)):
            errors.append("Short auto-varied batch must use a distinct background per card")
        for offset in range(0, len(rows) - 3):
            window = treatments[offset : offset + 4]
            if len(set(window)) < 4:
                errors.append(
                    f"{rows[offset]['number']}-{rows[offset + 3]['number']}: four-card "
                    "window must use four distinct auto-varied background treatments"
                )
    return errors


def validate_generation_backend_rows(rows: list[dict[str, str]]) -> list[str]:
    """Validate one explicit, stable generation model/interface choice."""
    errors: list[str] = []
    for row in rows:
        identifier = row.get("number", "?")
        mode = row.get("generation_backend_mode", "").strip().casefold()
        interface = row.get("generation_interface", "").strip()
        model = row.get("generation_model", "").strip()
        if mode not in GENERATION_BACKEND_MODES:
            errors.append(
                f"{identifier}: generation_backend_mode must be recommended or custom"
            )
        if not interface:
            errors.append(f"{identifier}: generation_interface is empty")
        if not model:
            errors.append(f"{identifier}: generation_model is empty")
        if mode == "recommended":
            if interface != RECOMMENDED_GENERATION_INTERFACE:
                errors.append(
                    f"{identifier}: recommended backend requires "
                    f"generation_interface={RECOMMENDED_GENERATION_INTERFACE}"
                )
            if model != RECOMMENDED_GENERATION_MODEL:
                errors.append(
                    f"{identifier}: recommended backend requires "
                    f"generation_model={RECOMMENDED_GENERATION_MODEL}"
                )

    for field in GENERATION_BACKEND_FIELDS:
        values = {row.get(field, "").strip() for row in rows}
        if len(values) > 1:
            errors.append(f"Batch contains multiple {field} values: {sorted(values)}")
    return errors


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
