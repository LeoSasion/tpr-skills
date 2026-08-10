#!/usr/bin/env python3
"""Validate and format model-curated two-round wardrobe recommendations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from character_profile import load_profiles


LIBRARY_VERSION = "2026.08"
DEFAULT_LIBRARY = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "wardrobe-option-library.csv"
)
LIBRARY_FIELDS = [
    "id",
    "stage",
    "label_cn",
    "family_cn",
    "default_tier",
    "visual_direction",
    "recommend_when",
    "within_range_diversity",
    "do_not_infer",
    "near_neighbors",
]
EVIDENCE_BASIS = {
    "visible-appearance",
    "visible-contrast",
    "neutral-proportions",
    "apparent-life-stage-safety",
    "character-anatomy",
    "print-readability",
    "user-preference",
    "selected-color-direction",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_csv", type=Path)
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--stage", choices=["color", "style", "finalize"], required=True)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--option-id", action="append", default=[])
    parser.add_argument("--reason", action="append", default=[])
    parser.add_argument("--exclude-id", action="append", default=[])
    parser.add_argument("--basis", action="append", default=[])
    parser.add_argument("--selected-color-id")
    parser.add_argument("--selected-style-id")
    return parser.parse_args()


def split_ids(value: str) -> set[str]:
    return {item.strip().upper() for item in value.split(";") if item.strip()}


def load_library(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != LIBRARY_FIELDS:
            raise ValueError(f"Wardrobe library must contain exactly {LIBRARY_FIELDS}")
        rows: dict[str, dict[str, str]] = {}
        labels: set[tuple[str, str]] = set()
        for line, raw in enumerate(reader, start=2):
            row = {key: (value or "").strip() for key, value in raw.items()}
            option_id = row["id"].upper()
            stage = row["stage"]
            expected = r"C\d{2}" if stage == "color" else r"S\d{2}"
            if stage not in {"color", "style"} or not re.fullmatch(expected, option_id):
                raise ValueError(f"Invalid wardrobe option ID/stage on line {line}")
            if option_id in rows:
                raise ValueError(f"Duplicate wardrobe option ID {option_id!r}")
            label_key = (stage, row["label_cn"].casefold())
            if not row["label_cn"] or label_key in labels:
                raise ValueError(f"Empty or duplicate label on line {line}")
            if row["default_tier"] not in {"core", "extended", "special"}:
                raise ValueError(f"Invalid default_tier for {option_id}")
            for required in (
                "family_cn",
                "visual_direction",
                "recommend_when",
                "within_range_diversity",
                "do_not_infer",
            ):
                if not row[required]:
                    raise ValueError(f"{option_id}: {required} is empty")
            row["id"] = option_id
            rows[option_id] = row
            labels.add(label_key)

    known = set(rows)
    for option_id, row in rows.items():
        unknown = split_ids(row["near_neighbors"]) - known
        if unknown:
            raise ValueError(f"{option_id}: unknown near_neighbors {sorted(unknown)}")
    return rows


def fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_model_curated_binding(
    row: dict[str, str], library: dict[str, dict[str, str]]
) -> list[str]:
    """Bind a model-curated manifest record to this exact library and profile."""
    if row.get("wardrobe_recommendation_method") != "model-curated":
        return []
    identifier = row.get("number", "?")
    errors: list[str] = []
    color = library.get(row.get("color_direction_id", "").upper())
    style = library.get(row.get("style_family_id", "").upper())
    if color is None or color.get("stage") != "color":
        errors.append(f"{identifier}: selected color ID is absent from wardrobe library")
    elif color.get("label_cn") != row.get("color_direction_label"):
        errors.append(f"{identifier}: selected color label does not match wardrobe library")
    if style is None or style.get("stage") != "style":
        errors.append(f"{identifier}: selected style ID is absent from wardrobe library")
    elif style.get("label_cn") != row.get("style_family_label"):
        errors.append(f"{identifier}: selected style label does not match wardrobe library")
    if row.get("wardrobe_library_version") != LIBRARY_VERSION:
        errors.append(f"{identifier}: wardrobe_library_version does not match active library")
    if color is not None and style is not None:
        selection_core = {
            "library_version": row.get("wardrobe_library_version", ""),
            "recommendation_method": "model-curated",
            "character_id": row.get("character_id", ""),
            "profile_version": row.get("character_profile_version", ""),
            "character_profile_sha256": row.get("character_profile_sha256", ""),
            "color_direction_id": color["id"],
            "color_direction_label": color["label_cn"],
            "style_family_id": style["id"],
            "style_family_label": style["label_cn"],
        }
        if row.get("wardrobe_recommendation_fingerprint") != fingerprint(selection_core):
            errors.append(
                f"{identifier}: wardrobe recommendation fingerprint does not match selection"
            )
    return errors


def validate_basis(stage: str, basis: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(value.strip() for value in basis if value.strip()))
    invalid = sorted(set(normalized) - EVIDENCE_BASIS)
    if invalid:
        raise ValueError(f"Unsupported recommendation basis values: {invalid}")
    if not normalized:
        raise ValueError("At least one --basis value is required for model-curated recommendations")
    if stage == "style" and "selected-color-direction" not in normalized:
        raise ValueError("Style recommendations must include --basis selected-color-direction")
    return normalized


def validate_candidates(
    stage: str,
    option_ids: list[str],
    reasons: list[str],
    excluded_ids: set[str],
    library: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    ids = [value.strip().upper() for value in option_ids]
    if len(ids) != 3 or len(set(ids)) != 3:
        raise ValueError("Model curation must provide exactly three distinct --option-id values")
    if len(reasons) != 3 or any(len(value.strip()) < 4 for value in reasons):
        raise ValueError("Provide exactly three non-empty --reason values in option order")
    if excluded_ids.intersection(ids):
        raise ValueError(
            f"Model recommendations repeat excluded IDs {sorted(excluded_ids.intersection(ids))}"
        )

    rows: list[dict[str, str]] = []
    for option_id in ids:
        row = library.get(option_id)
        if row is None or row["stage"] != stage:
            raise ValueError(f"{option_id!r} is not a valid {stage} option")
        rows.append(row)

    if len({row["family_cn"] for row in rows}) < 2:
        raise ValueError("The three recommendations must span at least two library families")
    for index, left in enumerate(rows):
        left_neighbors = split_ids(left["near_neighbors"])
        for right in rows[index + 1 :]:
            right_neighbors = split_ids(right["near_neighbors"])
            if right["id"] in left_neighbors or left["id"] in right_neighbors:
                raise ValueError(
                    f"Recommendations {left['id']} and {right['id']} are near-neighbors; "
                    "choose a more materially different option"
                )
    return rows


def option_payload(
    row: dict[str, str], reason: str, index: int, stage: str, round_number: int
) -> dict[str, object]:
    return {
        "index": index,
        "option_id": row["id"],
        "interaction_id": f"{stage}-round-{round_number}-option-{index}",
        "label": row["label_cn"],
        "reason": reason.strip(),
        "family": row["family_cn"],
        "default_tier": row["default_tier"],
        "visual_direction": row["visual_direction"],
        "within_range_diversity": row["within_range_diversity"],
        "do_not_infer": row["do_not_infer"],
    }


def main() -> int:
    args = parse_args()
    if args.round < 1:
        raise ValueError("--round must be at least 1")
    profiles, errors = load_profiles(args.profile_csv)
    if errors:
        raise RuntimeError("Character profile validation failed:\n- " + "\n- ".join(errors))
    profile = profiles.get(args.character_id)
    if profile is None:
        raise ValueError(f"Unknown character_id {args.character_id!r}")
    if profile["wardrobe_policy"] in {"fixed", "none"}:
        raise ValueError("Two-round wardrobe selection is not applicable to fixed or no-clothing profiles")

    library = load_library(args.library)
    selected_color = library.get((args.selected_color_id or "").upper())
    selected_style = library.get((args.selected_style_id or "").upper())

    if args.stage == "finalize":
        if not selected_color or selected_color["stage"] != "color":
            raise ValueError("--selected-color-id must identify one color option")
        if not selected_style or selected_style["stage"] != "style":
            raise ValueError("--selected-style-id must identify one style option")
        selection_core = {
            "library_version": LIBRARY_VERSION,
            "recommendation_method": "model-curated",
            "character_id": profile["character_id"],
            "profile_version": profile["profile_version"],
            "character_profile_sha256": profile["_profile_sha256"],
            "color_direction_id": selected_color["id"],
            "color_direction_label": selected_color["label_cn"],
            "style_family_id": selected_style["id"],
            "style_family_label": selected_style["label_cn"],
        }
        print(
            json.dumps(
                {
                    "choice_type": "wardrobe_selection",
                    **selection_core,
                    "recommendation_fingerprint": fingerprint(selection_core),
                    "expansion_contract": {
                        "minimum_sub_palettes": 4,
                        "minimum_silhouettes": 4,
                        "minimum_substyles": 4,
                        "reuse_rule": "cover-each-approved-pool-before-reuse",
                        "boundary": "maximize diversity without leaving selected color direction or style family",
                    },
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    basis = validate_basis(args.stage, args.basis)
    if args.stage == "style":
        if not selected_color or selected_color["stage"] != "color":
            raise ValueError("Style recommendations require --selected-color-id")
    elif args.selected_color_id:
        raise ValueError("Color-stage recommendations must not preselect a color")

    excluded_ids = {value.strip().upper() for value in args.exclude_id if value.strip()}
    invalid_exclusions = sorted(
        option_id
        for option_id in excluded_ids
        if option_id not in library or library[option_id]["stage"] != args.stage
    )
    if invalid_exclusions:
        raise ValueError(
            f"Excluded IDs do not belong to the {args.stage} stage: {invalid_exclusions}"
        )
    rows = validate_candidates(
        args.stage,
        args.option_id,
        args.reason,
        excluded_ids,
        library,
    )
    recommendation_core: dict[str, object] = {
        "library_version": LIBRARY_VERSION,
        "recommendation_method": "model-curated",
        "stage": args.stage,
        "round": args.round,
        "character_id": profile["character_id"],
        "profile_version": profile["profile_version"],
        "character_profile_sha256": profile["_profile_sha256"],
        "evidence_basis": basis,
        "selected_color_id": selected_color["id"] if selected_color else "",
        "option_ids": [row["id"] for row in rows],
        "reasons": [value.strip() for value in args.reason],
    }
    options = [
        option_payload(row, reason, index, args.stage, args.round)
        for index, (row, reason) in enumerate(zip(rows, args.reason), start=1)
    ]
    print(
        json.dumps(
            {
                "choice_type": "color_direction" if args.stage == "color" else "wardrobe_style",
                **recommendation_core,
                "recommendation_fingerprint": fingerprint(recommendation_core),
                "selected_color": (
                    {
                        "id": selected_color["id"],
                        "label": selected_color["label_cn"],
                        "visual_direction": selected_color["visual_direction"],
                    }
                    if selected_color
                    else None
                ),
                "options": options,
                "more_option": {
                    "index": 4,
                    "option_id": f"{args.stage}-round-{args.round}-more",
                    "label": "更多其他",
                    "next_round": args.round + 1,
                    "preserves_selected_color": args.stage == "style",
                },
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
