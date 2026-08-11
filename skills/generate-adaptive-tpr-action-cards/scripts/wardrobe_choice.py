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


LIBRARY_VERSION = "2026.08.1"
LEGACY_LIBRARY_VERSION = "2026.08"
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
    "style_groups",
]
LEGACY_LIBRARY_FIELDS = LIBRARY_FIELDS[:-1]
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
STYLE_GROUPS = {
    "shared",
    "child-masculine",
    "child-feminine",
    "adult-masculine",
    "adult-feminine",
}
CHILD_AGE_BANDS = {"infant", "toddler", "child", "teen", "juvenile"}
ADULT_AGE_BANDS = {"young-adult", "adult", "mature", "older-adult"}
GROUP_CONFIDENCES = {"medium", "high"}
STYLE_GROUP_UNCERTAIN_FIELDS = {
    "character_kind",
    "age",
    "apparent_age_band",
    "age_confidence",
    "gender",
    "gender_presentation",
    "gender_confidence",
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
    parser.add_argument(
        "--recommendation-method",
        choices=["model-curated", "user-specified"],
        default="model-curated",
    )
    parser.add_argument("--selected-color-label")
    parser.add_argument("--selected-style-label")
    parser.add_argument("--custom-override")
    return parser.parse_args()


def split_ids(value: str) -> set[str]:
    return {item.strip().upper() for item in value.split(";") if item.strip()}


def split_style_groups(value: str) -> list[str]:
    """Return normalized style groups in their authored order."""
    return [item.strip().casefold() for item in value.split(";") if item.strip()]


def resolve_style_group(profile: dict[str, str]) -> str:
    """Resolve a visual styling group from approved, sufficiently certain evidence."""
    character_kind = profile.get("character_kind", "").casefold()
    capabilities = {
        item.strip().casefold()
        for item in profile.get("render_capabilities", "").split(";")
        if item.strip()
    }
    is_human_like = character_kind == "human" or (
        character_kind == "stylized-figure" and "human-biped" in capabilities
    )
    if not is_human_like:
        return "shared"

    uncertain_fields = {
        item.strip().casefold()
        for item in profile.get("uncertain_fields", "").split(";")
        if item.strip()
    }
    if uncertain_fields.intersection(STYLE_GROUP_UNCERTAIN_FIELDS):
        return "shared"
    if profile.get("age_confidence", "").casefold() not in GROUP_CONFIDENCES:
        return "shared"
    if profile.get("gender_confidence", "").casefold() not in GROUP_CONFIDENCES:
        return "shared"

    age_band = profile.get("apparent_age_band", "").casefold()
    presentation = profile.get("gender_presentation", "").casefold()
    if presentation not in {"masculine", "feminine"}:
        return "shared"
    if age_band in CHILD_AGE_BANDS:
        return f"child-{presentation}"
    if age_band in ADULT_AGE_BANDS:
        return f"adult-{presentation}"
    return "shared"


def resolve_age_domain(profile: dict[str, str]) -> str:
    """Resolve the strict wardrobe safety domain without inferring identity."""
    uncertain_fields = {
        item.strip().casefold()
        for item in profile.get("uncertain_fields", "").split(";")
        if item.strip()
    }
    if uncertain_fields.intersection({"age", "apparent_age_band", "age_confidence"}):
        return "uncertain"
    age_band = profile.get("apparent_age_band", "").casefold()
    if age_band in CHILD_AGE_BANDS:
        return "child"
    if (
        age_band in ADULT_AGE_BANDS
        and profile.get("age_confidence", "").casefold() in GROUP_CONFIDENCES
    ):
        return "adult"
    return "uncertain"


def eligible_style_groups(resolved_style_group: str) -> list[str]:
    if resolved_style_group == "shared":
        return ["shared"]
    if resolved_style_group not in STYLE_GROUPS:
        raise ValueError(f"Unsupported resolved style group {resolved_style_group!r}")
    return [resolved_style_group, "shared"]


def style_row_is_eligible(row: dict[str, str], resolved_style_group: str) -> bool:
    groups = set(split_style_groups(row.get("style_groups", "")))
    return bool(groups.intersection(eligible_style_groups(resolved_style_group)))


def style_row_age_domains(row: dict[str, str]) -> set[str]:
    groups = set(split_style_groups(row.get("style_groups", "")))
    if "shared" in groups:
        return {"child", "adult", "uncertain"}
    domains: set[str] = set()
    if any(group.startswith("child-") for group in groups):
        domains.add("child")
    if any(group.startswith("adult-") for group in groups):
        domains.add("adult")
    return domains


def load_library(
    path: Path, *, allow_legacy_schema: bool = False
) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        legacy_schema = fieldnames == LEGACY_LIBRARY_FIELDS
        if fieldnames != LIBRARY_FIELDS and fieldnames != LEGACY_LIBRARY_FIELDS:
            raise ValueError(
                "Wardrobe library must contain the current fields or the "
                f"legacy verify-only fields {LEGACY_LIBRARY_FIELDS}"
            )
        if legacy_schema and not allow_legacy_schema:
            raise ValueError(
                "Legacy wardrobe library schema is verify-only and cannot be used "
                "for current recommendations or finalization"
            )
        rows: dict[str, dict[str, str]] = {}
        color_labels: set[str] = set()
        style_label_groups: dict[str, list[frozenset[str]]] = {}
        for line, raw in enumerate(reader, start=2):
            row = {key: (value or "").strip() for key, value in raw.items()}
            option_id = row["id"].upper()
            stage = row["stage"]
            if legacy_schema:
                row["style_groups"] = (
                    "not-applicable" if stage == "color" else "shared"
                )
            expected = r"C\d{2}" if stage == "color" else r"S\d{2}"
            if stage not in {"color", "style"} or not re.fullmatch(expected, option_id):
                raise ValueError(f"Invalid wardrobe option ID/stage on line {line}")
            if option_id in rows:
                raise ValueError(f"Duplicate wardrobe option ID {option_id!r}")
            if not row["label_cn"]:
                raise ValueError(f"Empty label on line {line}")

            authored_groups = split_style_groups(row["style_groups"])
            if len(authored_groups) != len(set(authored_groups)):
                raise ValueError(f"{option_id}: style_groups contains duplicate values")
            group_set = frozenset(authored_groups)
            if stage == "color":
                if authored_groups != ["not-applicable"]:
                    raise ValueError(
                        f"{option_id}: color rows must set style_groups to not-applicable"
                    )
                label_key = row["label_cn"].casefold()
                if label_key in color_labels:
                    raise ValueError(f"Duplicate color label on line {line}")
                color_labels.add(label_key)
            else:
                unknown_groups = group_set - STYLE_GROUPS
                if not group_set or unknown_groups:
                    raise ValueError(
                        f"{option_id}: invalid style_groups {sorted(unknown_groups)}"
                    )
                if "shared" in group_set and len(group_set) != 1:
                    raise ValueError(
                        f"{option_id}: shared must be the only value in style_groups"
                    )
                has_child_group = any(
                    group.startswith("child-") for group in group_set
                )
                has_adult_group = any(
                    group.startswith("adult-") for group in group_set
                )
                if has_child_group and has_adult_group:
                    raise ValueError(
                        f"{option_id}: style_groups cannot mix child and adult age domains"
                    )
                label_key = row["label_cn"].casefold()
                prior_group_sets = style_label_groups.setdefault(label_key, [])
                for prior_groups in prior_group_sets:
                    if group_set.intersection(prior_groups):
                        raise ValueError(
                            f"Duplicate style label has overlapping groups on line {line}"
                        )
                prior_group_sets.append(group_set)

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


def user_specified_selection_core(
    row: dict[str, str], profile: dict[str, str]
) -> dict[str, object]:
    return {
        "library_version": row.get("wardrobe_library_version", ""),
        "recommendation_method": "user-specified",
        "character_id": row.get("character_id", ""),
        "profile_version": row.get("character_profile_version", ""),
        "character_profile_sha256": row.get("character_profile_sha256", ""),
        "color_direction_id": row.get("color_direction_id", "").upper(),
        "color_direction_label": row.get("color_direction_label", ""),
        "style_family_id": row.get("style_family_id", "").upper(),
        "style_family_label": row.get("style_family_label", ""),
        "wardrobe_custom_override": row.get("wardrobe_custom_override", ""),
        "wardrobe_evidence_basis": row.get("wardrobe_evidence_basis", ""),
        "resolved_age_domain": resolve_age_domain(profile),
    }


def validate_user_specified_binding(
    row: dict[str, str],
    library: dict[str, dict[str, str]],
    profile: dict[str, str] | None = None,
) -> list[str]:
    """Validate library IDs and the non-bypassable age domain for custom choices."""
    identifier = row.get("number", "?")
    errors: list[str] = []
    color_id = row.get("color_direction_id", "").upper()
    style_id = row.get("style_family_id", "").upper()

    if color_id != "CUSTOM":
        color = library.get(color_id)
        if color is None or color.get("stage") != "color":
            errors.append(f"{identifier}: user-specified color ID is absent from wardrobe library")
        elif color.get("label_cn") != row.get("color_direction_label"):
            errors.append(f"{identifier}: user-specified color label does not match wardrobe library")

    style: dict[str, str] | None = None
    if style_id != "CUSTOM":
        style = library.get(style_id)
        if style is None or style.get("stage") != "style":
            errors.append(f"{identifier}: user-specified style ID is absent from wardrobe library")
        elif style.get("label_cn") != row.get("style_family_label"):
            errors.append(f"{identifier}: user-specified style label does not match wardrobe library")

    if profile is None:
        return errors

    age_domain = resolve_age_domain(profile)
    evidence_basis = {
        item.strip().casefold()
        for item in row.get("wardrobe_evidence_basis", "").split(";")
        if item.strip()
    }
    if age_domain in {"child", "uncertain"}:
        errors.append(
            f"{identifier}: user-specified wardrobe is not permitted for a child or "
            "age-uncertain profile; use a model-curated minor-safe library style or "
            "obtain clear adult confirmation"
        )
    if style is not None:
        allowed_domains = style_row_age_domains(style)
        if age_domain not in allowed_domains:
            errors.append(
                f"{identifier}: user-specified style crosses the {age_domain} age domain"
            )
    library_version = row.get("wardrobe_library_version", "")
    if library_version not in {LIBRARY_VERSION, LEGACY_LIBRARY_VERSION}:
        errors.append(
            f"{identifier}: user-specified wardrobe_library_version is unsupported"
        )
    elif library_version == LEGACY_LIBRARY_VERSION:
        errors.append(
            f"{identifier}: legacy user-specified fingerprints cannot be verified; "
            f"re-finalize under wardrobe library {LIBRARY_VERSION}"
        )
        legacy_color_match = re.fullmatch(r"C(\d{2})", color_id)
        if color_id != "CUSTOM" and (
            legacy_color_match is None
            or not 1 <= int(legacy_color_match.group(1)) <= 18
        ):
            errors.append(
                f"{identifier}: legacy wardrobe version supports only color IDs "
                "C01-C18 or CUSTOM"
            )
        legacy_style_match = re.fullmatch(r"S(\d{2})", style_id)
        if style_id != "CUSTOM" and (
            legacy_style_match is None
            or not 1 <= int(legacy_style_match.group(1)) <= 24
        ):
            errors.append(
                f"{identifier}: legacy wardrobe version supports only style IDs "
                "S01-S24 or CUSTOM"
            )
    elif library_version == LIBRARY_VERSION:
        selection_core = user_specified_selection_core(row, profile)
        if row.get("wardrobe_recommendation_fingerprint") != fingerprint(selection_core):
            errors.append(
                f"{identifier}: user-specified wardrobe fingerprint does not match selection"
            )
    return errors


def validate_model_curated_binding(
    row: dict[str, str],
    library: dict[str, dict[str, str]],
    profile: dict[str, str] | None = None,
) -> list[str]:
    """Bind a model-curated manifest record to this exact library and profile."""
    method = row.get("wardrobe_recommendation_method")
    if method == "user-specified":
        return validate_user_specified_binding(row, library, profile)
    if method != "model-curated":
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

    library_version = row.get("wardrobe_library_version", "")
    if library_version not in {LIBRARY_VERSION, LEGACY_LIBRARY_VERSION}:
        errors.append(
            f"{identifier}: wardrobe_library_version is not active or supported legacy"
        )
        return errors

    if library_version == LEGACY_LIBRARY_VERSION:
        color_id = row.get("color_direction_id", "").upper()
        legacy_color_match = re.fullmatch(r"C(\d{2})", color_id)
        if (
            legacy_color_match is None
            or not 1 <= int(legacy_color_match.group(1)) <= 18
        ):
            errors.append(
                f"{identifier}: legacy wardrobe version supports only color IDs C01-C18"
            )
        style_id = row.get("style_family_id", "").upper()
        legacy_style_match = re.fullmatch(r"S(\d{2})", style_id)
        if (
            legacy_style_match is None
            or not 1 <= int(legacy_style_match.group(1)) <= 24
        ):
            errors.append(
                f"{identifier}: legacy wardrobe version supports only style IDs S01-S24"
            )
        if color is not None and style is not None:
            selection_core = {
                "library_version": library_version,
                "recommendation_method": "model-curated",
                "character_id": row.get("character_id", ""),
                "profile_version": row.get("character_profile_version", ""),
                "character_profile_sha256": row.get("character_profile_sha256", ""),
                "color_direction_id": color["id"],
                "color_direction_label": color["label_cn"],
                "style_family_id": style["id"],
                "style_family_label": style["label_cn"],
            }
            if row.get("wardrobe_recommendation_fingerprint") != fingerprint(
                selection_core
            ):
                errors.append(
                    f"{identifier}: wardrobe recommendation fingerprint does not match selection"
                )
        return errors

    # Current manifests can only be fully group-bound when the approved profile
    # is supplied.  Callers without the profile still get exact ID/label/version
    # checks, while profile-aware callers additionally enforce and fingerprint
    # the resolved group.
    if profile is not None and color is not None and style is not None:
        resolved_style_group = resolve_style_group(profile)
        if not style_row_is_eligible(style, resolved_style_group):
            errors.append(
                f"{identifier}: selected style is outside resolved style group "
                f"{resolved_style_group}"
            )
        selection_core = {
            "library_version": library_version,
            "recommendation_method": "model-curated",
            "character_id": row.get("character_id", ""),
            "profile_version": row.get("character_profile_version", ""),
            "character_profile_sha256": row.get("character_profile_sha256", ""),
            "color_direction_id": color["id"],
            "color_direction_label": color["label_cn"],
            "style_family_id": style["id"],
            "style_family_label": style["label_cn"],
            "resolved_style_group": resolved_style_group,
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
    resolved_style_group: str = "shared",
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
    if stage == "style":
        ineligible_exclusions = sorted(
            option_id
            for option_id in excluded_ids
            if option_id in library
            and library[option_id].get("stage") == "style"
            and not style_row_is_eligible(library[option_id], resolved_style_group)
        )
        if ineligible_exclusions:
            raise ValueError(
                "Excluded style IDs are outside the resolved style group: "
                f"{ineligible_exclusions}"
            )

    rows: list[dict[str, str]] = []
    for option_id in ids:
        row = library.get(option_id)
        if row is None or row["stage"] != stage:
            raise ValueError(f"{option_id!r} is not a valid {stage} option")
        if stage == "style" and not style_row_is_eligible(
            row, resolved_style_group
        ):
            raise ValueError(
                f"{option_id!r} is outside resolved style group "
                f"{resolved_style_group}"
            )
        rows.append(row)

    if stage == "style" and resolved_style_group != "shared":
        exact_group_count = sum(
            resolved_style_group in split_style_groups(row["style_groups"])
            for row in rows
        )
        if exact_group_count < 2:
            raise ValueError(
                "Specific style recommendations must include at least two options "
                f"from exact group {resolved_style_group}"
            )

    if stage == "style" and len({row["label_cn"].casefold() for row in rows}) != 3:
        raise ValueError("The three style recommendations must use distinct visible labels")

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
        "style_groups": split_style_groups(row["style_groups"]),
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

    resolved_style_group = resolve_style_group(profile)
    eligible_groups = eligible_style_groups(resolved_style_group)
    library = load_library(args.library)
    selected_color = library.get((args.selected_color_id or "").upper())
    selected_style = library.get((args.selected_style_id or "").upper())

    if args.stage == "finalize":
        if args.recommendation_method == "user-specified":
            basis = validate_basis("color", args.basis)
            custom_override = (args.custom_override or "").strip()
            if not custom_override:
                raise ValueError("User-specified finalization requires --custom-override")
            age_domain = resolve_age_domain(profile)
            if age_domain in {"child", "uncertain"}:
                raise ValueError(
                    "User-specified wardrobe is not permitted for a child or "
                    "age-uncertain profile; use a model-curated minor-safe library "
                    "style or obtain clear adult confirmation"
                )

            color_id = (args.selected_color_id or "").upper()
            if color_id == "CUSTOM":
                color_label = (args.selected_color_label or "").strip()
                if not color_label:
                    raise ValueError("CUSTOM color requires --selected-color-label")
            elif selected_color and selected_color["stage"] == "color":
                color_label = selected_color["label_cn"]
                if args.selected_color_label and args.selected_color_label != color_label:
                    raise ValueError("--selected-color-label does not match the library")
            else:
                raise ValueError(
                    "--selected-color-id must identify one color option or CUSTOM"
                )

            style_id = (args.selected_style_id or "").upper()
            if style_id == "CUSTOM":
                style_label = (args.selected_style_label or "").strip()
                if not style_label:
                    raise ValueError("CUSTOM style requires --selected-style-label")
            elif selected_style and selected_style["stage"] == "style":
                style_label = selected_style["label_cn"]
                if args.selected_style_label and args.selected_style_label != style_label:
                    raise ValueError("--selected-style-label does not match the library")
                if age_domain not in style_row_age_domains(selected_style):
                    raise ValueError(
                        "--selected-style-id crosses the "
                        f"{age_domain} age domain"
                    )
            else:
                raise ValueError(
                    "--selected-style-id must identify one style option or CUSTOM"
                )

            row_core = {
                "wardrobe_library_version": LIBRARY_VERSION,
                "character_id": profile["character_id"],
                "character_profile_version": profile["profile_version"],
                "character_profile_sha256": profile["_profile_sha256"],
                "color_direction_id": color_id,
                "color_direction_label": color_label,
                "style_family_id": style_id,
                "style_family_label": style_label,
                "wardrobe_custom_override": custom_override,
                "wardrobe_evidence_basis": ";".join(basis),
            }
            selection_core = user_specified_selection_core(row_core, profile)
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
                            "boundary": "maximize diversity without leaving the explicit user-specified direction",
                        },
                    },
                    ensure_ascii=True,
                    indent=2,
                )
            )
            return 0

        if not selected_color or selected_color["stage"] != "color":
            raise ValueError("--selected-color-id must identify one color option")
        if not selected_style or selected_style["stage"] != "style":
            raise ValueError("--selected-style-id must identify one style option")
        if not style_row_is_eligible(selected_style, resolved_style_group):
            raise ValueError(
                "--selected-style-id is outside resolved style group "
                f"{resolved_style_group}"
            )
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
            "resolved_style_group": resolved_style_group,
        }
        print(
            json.dumps(
                {
                    "choice_type": "wardrobe_selection",
                    **selection_core,
                    "eligible_style_groups": eligible_groups,
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

    if args.recommendation_method != "model-curated":
        raise ValueError("User-specified mode is supported only with --stage finalize")

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
        resolved_style_group,
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
    if args.stage == "style":
        recommendation_core["resolved_style_group"] = resolved_style_group
    options = [
        option_payload(row, reason, index, args.stage, args.round)
        for index, (row, reason) in enumerate(zip(rows, args.reason), start=1)
    ]
    print(
        json.dumps(
            {
                "choice_type": "color_direction" if args.stage == "color" else "wardrobe_style",
                **recommendation_core,
                "eligible_style_groups": eligible_groups if args.stage == "style" else [],
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
                    "preserves_style_group": args.stage == "style",
                },
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
