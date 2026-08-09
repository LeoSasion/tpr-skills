#!/usr/bin/env python3
"""Validate action semantics, traceability, and planned batch diversity."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from batch_common import (
    DELIVERY_CHOICES,
    WORD_IDENTIFIER_VISIBILITIES,
    atomic_write_csv,
    read_manifest,
    select_rows,
)
from character_profile import load_profiles, split_values, validate_manifest_profiles
from validate_action_library import load_validated_library, load_validated_suitability


REQUIRED_PLAN_FIELDS = [
    "character_id",
    "character_profile_version",
    "character_profile_sha256",
    "adaptation_mode",
    "persona",
    "wardrobe_policy",
    "required_render_capabilities",
    "action_risk_tags",
    "suitability_handling",
    "adaptation_status",
    "adaptation_reason",
    "reference_photo",
    "reference_sha256",
    "semantic_id",
    "semantic_version",
    "body_action",
    "key_joints",
    "weight_shift",
    "head_angle",
    "gaze",
    "expression",
    "outfit",
    "outfit_color",
    "outfit_silhouette",
    "outfit_style",
    "word_identifier_visibility",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--character-profile", type=Path, required=True)
    parser.add_argument("--library", type=Path)
    parser.add_argument("--suitability", type=Path)
    parser.add_argument("--semantics", type=Path)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--id", dest="identifiers", action="append", default=[])
    parser.add_argument("--write-status", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def load_semantics(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"semantic_id", "english", "chinese", "version", "status"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Semantics library must contain {sorted(required)}")
        result: dict[str, dict[str, str]] = {}
        for line, raw in enumerate(reader, start=2):
            row = {key: (value or "") for key, value in raw.items()}
            semantic_id = row["semantic_id"]
            if not semantic_id or semantic_id in result:
                raise ValueError(f"Invalid or duplicate semantic_id on line {line}: {semantic_id!r}")
            result[semantic_id] = row
        return result


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_suitability_binding(
    identifier: str,
    row: dict[str, str],
    preset_number: str,
    suitability: dict[str, dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    risk_tags = {
        normalized(value)
        for value in split_values(row.get("action_risk_tags", ""))
    }
    rule = suitability.get(preset_number)
    if rule is None:
        if risk_tags != {"none"}:
            errors.append(
                f"{identifier}: unlisted preset action must use action_risk_tags=none"
            )
        if row.get("suitability_handling") != "none":
            errors.append(
                f"{identifier}: unlisted preset action must use suitability_handling=none"
            )
        return errors

    required_tags = {
        normalized(value)
        for value in split_values(rule.get("context_tags", ""))
    }
    missing_tags = sorted(required_tags - risk_tags)
    if missing_tags:
        errors.append(
            f"{identifier}: action_risk_tags omits suitability tags {missing_tags}"
        )
    expected_handling = rule.get("default_handling", "")
    if row.get("suitability_handling") != expected_handling:
        errors.append(
            f"{identifier}: suitability_handling must be {expected_handling!r} "
            f"for preset {preset_number}"
        )
    if row.get("adaptation_status") != "fallback" or row.get(
        "adaptation_reason"
    ) != "safe-override":
        errors.append(
            f"{identifier}: special-context preset {preset_number} requires "
            "adaptation_status=fallback and adaptation_reason=safe-override"
        )
    return errors


def validate_rows(
    rows: list[dict[str, str]],
    semantics: dict[str, dict[str, str]],
    library: dict[str, dict[str, str]],
    suitability: dict[str, dict[str, str]] | None,
    profiles: dict[str, dict[str, str]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    output_names: dict[str, str] = {}

    for row in rows:
        identifier = row["number"]
        if library:
            source_row = row.get("source_row", "")
            if not source_row.isdigit():
                errors.append(f"{identifier}: source_row is not numeric for preset lookup")
            else:
                preset_number = f"{int(source_row):03d}"
                preset = library.get(preset_number)
                if preset is None:
                    errors.append(
                        f"{identifier}: source_row {source_row!r} is outside the 200-action library"
                    )
                else:
                    if row.get("english") != preset["english"]:
                        errors.append(
                            f"{identifier}: English does not match preset row {preset_number}"
                        )
                    if row.get("chinese") != preset["chinese"]:
                        errors.append(
                            f"{identifier}: Chinese does not match preset row {preset_number}"
                        )
                    if suitability is not None:
                        errors.extend(
                            validate_suitability_binding(
                                identifier,
                                row,
                                preset_number,
                                suitability,
                            )
                        )
        for field in REQUIRED_PLAN_FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"{identifier}: {field} is empty")
        choice = row.get("delivery_format", "").strip().casefold()
        if choice not in DELIVERY_CHOICES:
            errors.append(
                f"{identifier}: delivery_format is not confirmed as zip, word, or both"
            )
        word_visibility = row.get("word_identifier_visibility", "").strip().casefold()
        if word_visibility not in WORD_IDENTIFIER_VISIBILITIES:
            errors.append(
                f"{identifier}: word_identifier_visibility must be hidden or shown"
            )
        output_name = Path(row.get("output_path", "")).name.casefold()
        if not output_name:
            errors.append(f"{identifier}: output_path is empty")
        elif output_name in output_names:
            errors.append(
                f"{identifier}: output_path collides with {output_names[output_name]}"
            )
        else:
            output_names[output_name] = identifier

        semantic_id = row.get("semantic_id", "")
        if semantics:
            semantic = semantics.get(semantic_id)
            if semantic is None:
                warnings.append(
                    f"{identifier}: semantic_id {semantic_id!r} is batch-local, not yet in library"
                )
            else:
                if semantic.get("status") != "approved":
                    errors.append(f"{identifier}: semantic {semantic_id} is not approved")
                if semantic.get("english") != row.get("english"):
                    errors.append(f"{identifier}: semantic English does not exactly match manifest")
                if semantic.get("chinese") != row.get("chinese"):
                    errors.append(f"{identifier}: semantic Chinese does not exactly match manifest")
                if semantic.get("version") != row.get("semantic_version"):
                    errors.append(f"{identifier}: semantic version does not match library")

        profile = profiles.get(row.get("character_id", ""))
        if profile is not None:
            policy = profile.get("wardrobe_policy")
            mode = row.get("adaptation_mode")
            outfit_values = {
                "outfit_color": row.get("outfit_color", ""),
                "outfit_silhouette": row.get("outfit_silhouette", ""),
                "outfit_style": row.get("outfit_style", ""),
            }
            if policy == "none":
                for field, value in {"outfit": row.get("outfit", ""), **outfit_values}.items():
                    if normalized(value) != "not-applicable":
                        errors.append(
                            f"{identifier}: no-clothing policy requires {field}=not-applicable"
                        )
            elif policy == "fixed":
                if row.get("outfit") != profile.get("signature_outfit"):
                    errors.append(f"{identifier}: fixed outfit does not match signature_outfit")
                for field, value in outfit_values.items():
                    if normalized(value) != "fixed":
                        errors.append(f"{identifier}: fixed wardrobe requires {field}=fixed")
            else:
                if policy == "signature-variants" and normalized(
                    profile.get("signature_outfit", "")
                ) not in normalized(row.get("outfit", "")):
                    errors.append(
                        f"{identifier}: signature-variant outfit omits signature_outfit"
                    )
                if mode in {"recommend", "random"}:
                    pools = {
                        "outfit_color": split_values(profile.get("outfit_palette_options", "")),
                        "outfit_silhouette": split_values(
                            profile.get("outfit_silhouette_options", "")
                        ),
                        "outfit_style": split_values(profile.get("outfit_style_options", "")),
                    }
                    for field, values in pools.items():
                        if normalized(row.get(field, "")) not in {
                            normalized(value) for value in values
                        }:
                            errors.append(
                                f"{identifier}: {field} is outside the approved character-profile pool"
                            )

    character_ids = {row.get("character_id", "") for row in rows}
    if len(character_ids) > 1:
        errors.append(
            f"Batch contains multiple primary characters: {sorted(character_ids)}"
        )

    word_visibilities = {
        row.get("word_identifier_visibility", "").strip().casefold() for row in rows
    }
    if len(word_visibilities) > 1:
        errors.append(
            "Batch contains multiple Word identifier visibility values: "
            f"{sorted(word_visibilities)}"
        )

    varied_rows = [
        row
        for row in rows
        if row.get("wardrobe_policy") in {"varied", "signature-variants"}
    ]
    outfit_seen: dict[str, str] = {}
    for row in varied_rows:
        key = normalized(row.get("outfit", ""))
        if key in outfit_seen:
            errors.append(f"{row['number']}: full outfit repeats {outfit_seen[key]}")
        else:
            outfit_seen[key] = row["number"]

    for left, right in zip(rows, rows[1:]):
        left_combo = (normalized(left.get("head_angle", "")), normalized(left.get("gaze", "")))
        right_combo = (normalized(right.get("head_angle", "")), normalized(right.get("gaze", "")))
        if left_combo == right_combo:
            errors.append(
                f"{left['number']}/{right['number']}: consecutive head-angle and gaze repeat"
            )
        if left.get("wardrobe_policy") in {"varied", "signature-variants"}:
            outfit_dimensions = [
                normalized(left.get(field, "")) != normalized(right.get(field, ""))
                for field in ("outfit_color", "outfit_silhouette", "outfit_style")
            ]
            if sum(outfit_dimensions) < 2:
                errors.append(
                    f"{left['number']}/{right['number']}: consecutive outfits differ in fewer than two dimensions"
                )

    for offset in range(0, len(rows) - 3):
        window = rows[offset : offset + 4]
        combos = {
            (normalized(row.get("head_angle", "")), normalized(row.get("gaze", "")))
            for row in window
        }
        expressions = {normalized(row.get("expression", "")) for row in window}
        label = f"{window[0]['number']}-{window[-1]['number']}"
        if len(combos) < 3:
            errors.append(f"{label}: four-card window has fewer than three head/gaze combinations")
        if len(expressions) < 4:
            errors.append(f"{label}: four-card window does not have four distinct expressions")

    if len(rows) < 4:
        expressions = [normalized(row.get("expression", "")) for row in rows]
        if len(expressions) != len(set(expressions)):
            errors.append("Short batch must use a distinct expression for every card")
    return errors, warnings


def main() -> int:
    args = parse_args()
    fieldnames, all_rows = read_manifest(args.manifest)
    rows = select_rows(
        all_rows,
        start=args.start,
        end=args.end,
        identifiers=args.identifiers,
    )
    semantics = load_semantics(args.semantics)
    library = load_validated_library(args.library) if args.library else {}
    suitability_path = args.suitability
    if args.library and suitability_path is None:
        candidate = args.library.with_name("action-suitability.csv")
        if candidate.is_file():
            suitability_path = candidate
        elif args.library.name == "preset-actions-200.csv":
            raise ValueError(
                "The built-in preset library requires action-suitability.csv; "
                "pass --suitability when it is stored elsewhere"
            )
    suitability = (
        load_validated_suitability(suitability_path, list(library.values()))
        if suitability_path and library
        else None
    )
    profiles, profile_errors = load_profiles(args.character_profile)
    errors, warnings = validate_rows(rows, semantics, library, suitability, profiles)
    if args.suitability and not args.library:
        warnings.append("--suitability has no effect without --library")
    elif args.library and not suitability_path:
        warnings.append("No action-suitability rules were found for this custom library")
    errors = (
        profile_errors
        + validate_manifest_profiles(profiles, args.manifest, selected_rows=rows)
        + errors
    )

    if args.write_status:
        if "diversity_plan_status" not in fieldnames:
            raise ValueError("Manifest is missing diversity_plan_status")
        selected_ids = {row["number"] for row in rows}
        status = "fail" if errors else "pass"
        for row in all_rows:
            if row["number"] in selected_ids:
                row["diversity_plan_status"] = status
        atomic_write_csv(args.manifest, fieldnames, all_rows)

    report = {"status": "failed" if errors else "passed", "errors": errors, "warnings": warnings}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        print("BATCH PLAN CHECK FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"BATCH PLAN CHECK PASSED: {len(rows)} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
