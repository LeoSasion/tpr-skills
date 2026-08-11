#!/usr/bin/env python3
"""Validate and format model-curated two-round wardrobe recommendations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
import unicodedata
from pathlib import Path

from character_profile import load_profiles


LIBRARY_VERSION = "2026.08.1"
LEGACY_LIBRARY_VERSION = "2026.08"
SELECTION_SCHEMA_VERSION = "2"
ASSIGNMENT_STRATEGY = "balanced-scattered-v1"
WARDROBE_SELECTION_GUIDANCE = (
    "请回复 1、2、3 或 4；也可使用 1+2、2+3+4 这样的组合，或直接输入一个范围名称。"
    "组合表示扩大逐张随机范围，每张图在同一维度只使用其中一个范围，不进行同图混搭。"
)
CUSTOM_RANGE_UNION_RE = re.compile(r"[+/]")
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
    parser.add_argument("--selected-color-id", action="append", default=[])
    parser.add_argument("--selected-style-id", action="append", default=[])
    parser.add_argument(
        "--recommendation-method",
        choices=["model-curated", "user-specified", "mixed"],
        default="model-curated",
    )
    parser.add_argument("--selected-color-label", action="append", default=[])
    parser.add_argument("--selected-style-label", action="append", default=[])
    parser.add_argument("--selected-color-round", action="append", type=int, default=[])
    parser.add_argument("--selected-color-option", action="append", type=int, default=[])
    parser.add_argument("--selected-style-round", action="append", type=int, default=[])
    parser.add_argument("--selected-style-option", action="append", type=int, default=[])
    parser.add_argument(
        "--selection-schema-version",
        choices=["auto", "1", SELECTION_SCHEMA_VERSION],
        default="auto",
    )
    parser.add_argument("--selection-expression")
    parser.add_argument("--retained-selection-json", default="[]")
    parser.add_argument("--assignment-count", type=int)
    parser.add_argument("--assignment-seed")
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


def compact_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def normalize_custom_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().split())


def custom_selection_key(stage: str, label: str) -> str:
    prefix = "C" if stage == "color" else "S"
    normalized = normalize_custom_label(label).casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16].upper()
    return f"CUSTOM-{prefix}-{digest}"


def selection_item(
    stage: str,
    *,
    option_id: str,
    label: str,
    round_number: int,
    option_number: int,
    source: str,
) -> dict[str, object]:
    normalized_label = normalize_custom_label(label)
    if not normalized_label or any(character in normalized_label for character in "\r\n;"):
        raise ValueError("Selection labels must be non-empty, single-line, and omit semicolons")
    if source == "library":
        key = option_id.strip().upper()
        expected = r"C\d{2}" if stage == "color" else r"S\d{2}"
        if not re.fullmatch(expected, key):
            raise ValueError(f"Invalid {stage} library selection ID {option_id!r}")
        if not (
            (round_number >= 1 and option_number in {1, 2, 3})
            or (round_number == 0 and option_number == 0)
        ):
            raise ValueError(
                "Library selections require round >= 1 and option 1-3, or 0/0 "
                "for an exact user-entered library name"
            )
        item_id = key
    elif source == "user-custom":
        if round_number != 0 or option_number != 0:
            raise ValueError("Custom selections require round=0 and option=0")
        if CUSTOM_RANGE_UNION_RE.search(normalized_label):
            raise ValueError(
                "A custom range label must describe exactly one range; split '+' "
                "or '/' unions into separate custom selections"
            )
        key = custom_selection_key(stage, normalized_label)
        item_id = ""
    else:
        raise ValueError(f"Unsupported selection source {source!r}")
    return {
        "key": key,
        "source": source,
        "id": item_id,
        "label": normalized_label,
        "round": round_number,
        "option": option_number,
    }


def canonicalize_selection_items(
    items: list[dict[str, object]], stage: str
) -> list[dict[str, object]]:
    canonical: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    seen_positions: set[tuple[int, int]] = set()
    for raw in items:
        required = {"key", "source", "id", "label", "round", "option"}
        if set(raw) != required:
            raise ValueError(
                f"{stage} selection items must contain exactly {sorted(required)}"
            )
        source = str(raw["source"])
        option_id = str(raw["id"])
        label = str(raw["label"])
        try:
            round_number = int(raw["round"])
            option_number = int(raw["option"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Selection round and option must be integers") from exc
        item = selection_item(
            stage,
            option_id=option_id,
            label=label,
            round_number=round_number,
            option_number=option_number,
            source=source,
        )
        if str(raw["key"]) != item["key"]:
            raise ValueError(f"{stage} selection key does not match its source and label")
        key = str(item["key"])
        if key in seen_keys:
            raise ValueError(f"Duplicate {stage} selection key {key!r}")
        seen_keys.add(key)
        position = (round_number, option_number)
        if source == "library" and round_number > 0:
            if position in seen_positions:
                raise ValueError(
                    f"Duplicate {stage} selection round/option {position!r}"
                )
            seen_positions.add(position)
        canonical.append(item)
    if not canonical:
        raise ValueError(f"At least one {stage} range must be selected")
    return sorted(canonical, key=lambda item: str(item["key"]))


def canonical_selection_payload(
    colors: list[dict[str, object]], styles: list[dict[str, object]]
) -> dict[str, list[dict[str, object]]]:
    return {
        "colors": canonicalize_selection_items(colors, "color"),
        "styles": canonicalize_selection_items(styles, "style"),
    }


def merge_selection_items(
    retained: list[dict[str, object]],
    added: list[dict[str, object]],
    stage: str,
) -> list[dict[str, object]]:
    """Accumulate a stage selection while keeping first-seen provenance."""
    merged: list[dict[str, object]] = []
    by_key: dict[str, dict[str, object]] = {}
    for raw in [*retained, *added]:
        item = canonicalize_selection_items([raw], stage)[0]
        key = str(item["key"])
        prior = by_key.get(key)
        if prior is not None:
            stable_fields = ("source", "id", "label")
            if any(
                str(prior[field]).casefold() != str(item[field]).casefold()
                for field in stable_fields
            ):
                raise ValueError(
                    f"Conflicting duplicate {stage} selection key {key!r}"
                )
            continue
        by_key[key] = item
        merged.append(item)
    return canonicalize_selection_items(merged, stage)


def parse_selection_payload(value: str) -> dict[str, list[dict[str, object]]]:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("wardrobe_selected_ranges_json is not valid JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {"colors", "styles"}:
        raise ValueError(
            "wardrobe_selected_ranges_json must contain exactly colors and styles"
        )
    if not isinstance(raw["colors"], list) or not isinstance(raw["styles"], list):
        raise ValueError("wardrobe selected colors/styles must be JSON arrays")
    payload = canonical_selection_payload(raw["colors"], raw["styles"])
    if value != compact_json(payload):
        raise ValueError("wardrobe_selected_ranges_json is not canonical compact JSON")
    return payload


def selection_method(payload: dict[str, list[dict[str, object]]]) -> str:
    origins = {
        "curated"
        if item["source"] == "library" and int(item["round"]) >= 1
        else "specified"
        for stage in ("colors", "styles")
        for item in payload[stage]
    }
    if origins == {"curated"}:
        return "model-curated"
    if origins == {"specified"}:
        return "user-specified"
    return "mixed"


def selection_custom_override(
    payload: dict[str, list[dict[str, object]]]
) -> str:
    labels = [
        str(item["label"])
        for stage in ("colors", "styles")
        for item in payload[stage]
        if item["source"] == "user-custom"
    ]
    return ";".join(labels)


def v2_selection_core(
    row: dict[str, str],
    profile: dict[str, str],
    payload: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    basis = sorted(
        {
            item.strip()
            for item in row.get("wardrobe_evidence_basis", "").split(";")
            if item.strip()
        }
    )
    return {
        "selection_schema_version": SELECTION_SCHEMA_VERSION,
        "library_version": row.get("wardrobe_library_version", ""),
        "recommendation_method": selection_method(payload),
        "character_id": row.get("character_id", ""),
        "profile_version": row.get("character_profile_version", ""),
        "character_profile_sha256": row.get("character_profile_sha256", ""),
        "selected_ranges": payload,
        "evidence_basis": basis,
        "resolved_style_group": resolve_style_group(profile),
        "resolved_age_domain": resolve_age_domain(profile),
    }


def validate_v2_selection_binding(
    row: dict[str, str],
    library: dict[str, dict[str, str]],
    profile: dict[str, str] | None,
) -> list[str]:
    identifier = row.get("number", "?")
    errors: list[str] = []
    try:
        payload = parse_selection_payload(row.get("wardrobe_selected_ranges_json", ""))
    except ValueError as exc:
        return [f"{identifier}: {exc}"]

    expected_method = selection_method(payload)
    if row.get("wardrobe_recommendation_method") != expected_method:
        errors.append(
            f"{identifier}: wardrobe_recommendation_method must be derived as {expected_method}"
        )
    if row.get("wardrobe_assignment_strategy") != ASSIGNMENT_STRATEGY:
        errors.append(
            f"{identifier}: wardrobe_assignment_strategy must be {ASSIGNMENT_STRATEGY}"
        )
    if row.get("wardrobe_library_version") != LIBRARY_VERSION:
        errors.append(
            f"{identifier}: v2 wardrobe selection requires library {LIBRARY_VERSION}"
        )

    resolved_group = resolve_style_group(profile) if profile is not None else None
    age_domain = resolve_age_domain(profile) if profile is not None else None
    for stage_name, library_stage in (("colors", "color"), ("styles", "style")):
        for item in payload[stage_name]:
            if item["source"] == "user-custom":
                if profile is not None and age_domain != "adult":
                    errors.append(
                        f"{identifier}: custom wardrobe ranges require a clearly adult profile"
                    )
                continue
            option_id = str(item["id"])
            option = library.get(option_id)
            if option is None or option.get("stage") != library_stage:
                errors.append(
                    f"{identifier}: selected {library_stage} ID {option_id!r} is absent from wardrobe library"
                )
                continue
            if option.get("label_cn") != item["label"]:
                errors.append(
                    f"{identifier}: selected {library_stage} label does not match {option_id}"
                )
            if (
                library_stage == "style"
                and resolved_group is not None
                and not style_row_is_eligible(option, resolved_group)
                and not (
                    age_domain == "adult"
                    and expected_method in {"user-specified", "mixed"}
                    and "adult" in style_row_age_domains(option)
                )
            ):
                errors.append(
                    f"{identifier}: selected style {option_id} is outside resolved style group {resolved_group}"
                )

    custom_override = selection_custom_override(payload)
    if row.get("wardrobe_custom_override", "") != custom_override:
        errors.append(
            f"{identifier}: wardrobe_custom_override does not match custom selected ranges"
        )

    scalar_specs = (
        (
            payload["colors"],
            "color_direction_id",
            "color_direction_label",
            "color_choice_round",
            "color_choice_option",
        ),
        (
            payload["styles"],
            "style_family_id",
            "style_family_label",
            "style_choice_round",
            "style_choice_option",
        ),
    )
    for items, id_field, label_field, round_field, option_field in scalar_specs:
        if len(items) == 1:
            item = items[0]
            expected_id = (
                str(item["id"]) if item["source"] == "library" else "CUSTOM"
            )
            expected_values = {
                id_field: expected_id,
                label_field: str(item["label"]),
                round_field: str(item["round"]),
                option_field: str(item["option"]),
            }
        else:
            expected_values = {
                id_field: "not-applicable",
                label_field: "not-applicable",
                round_field: "0",
                option_field: "0",
            }
        for field, expected in expected_values.items():
            if row.get(field, "") != expected:
                errors.append(
                    f"{identifier}: v2 compatibility field {field} must be {expected!r}"
                )

    color_keys = {str(item["key"]) for item in payload["colors"]}
    style_keys = {str(item["key"]) for item in payload["styles"]}
    assigned_color = row.get("assigned_color_direction_key", "")
    assigned_style = row.get("assigned_style_family_key", "")
    for field, value, allowed in (
        ("assigned_color_direction_key", assigned_color, color_keys),
        ("assigned_style_family_key", assigned_style, style_keys),
    ):
        if any(delimiter in value for delimiter in (";", "+", "/", ",")):
            errors.append(f"{identifier}: {field} must contain one scalar range key")
        elif value not in allowed:
            errors.append(f"{identifier}: {field} is outside the selected range set")

    if profile is not None:
        core = v2_selection_core(row, profile, payload)
        if row.get("wardrobe_recommendation_fingerprint") != fingerprint(core):
            errors.append(
                f"{identifier}: v2 wardrobe recommendation fingerprint does not match selection"
            )
    return errors


def build_balanced_scattered_assignments(
    payload: dict[str, list[dict[str, object]]],
    count: int,
    seed: str,
) -> list[dict[str, object]]:
    if count < 1:
        raise ValueError("Assignment count must be at least 1")
    if not seed.strip():
        raise ValueError("Multi-range assignment requires a non-empty stable seed")
    colors = [str(item["key"]) for item in payload["colors"]]
    styles = [str(item["key"]) for item in payload["styles"]]
    pairs = list(itertools.product(colors, styles))
    result: list[tuple[str, str]] = []
    cycle_index = 0
    while len(result) < count:
        remaining = list(pairs)
        color_counts = {key: 0 for key in colors}
        style_counts = {key: 0 for key in styles}
        cycle: list[tuple[str, str]] = []
        while remaining and len(result) + len(cycle) < count:
            def candidate_score(pair: tuple[str, str]) -> tuple[object, ...]:
                next_color_counts = dict(color_counts)
                next_style_counts = dict(style_counts)
                next_color_counts[pair[0]] += 1
                next_style_counts[pair[1]] += 1
                color_spread = max(next_color_counts.values()) - min(
                    next_color_counts.values()
                )
                style_spread = max(next_style_counts.values()) - min(
                    next_style_counts.values()
                )
                tie = hashlib.sha256(
                    f"{seed}|{cycle_index}|{pair[0]}|{pair[1]}".encode("utf-8")
                ).hexdigest()
                return (
                    color_spread + style_spread,
                    max(next_color_counts.values()) + max(next_style_counts.values()),
                    tie,
                )

            chosen = min(remaining, key=candidate_score)
            remaining.remove(chosen)
            cycle.append(chosen)
            color_counts[chosen[0]] += 1
            style_counts[chosen[1]] += 1
        result.extend(cycle)
        cycle_index += 1
    return [
        {
            "index": index,
            "assigned_color_direction_key": pair[0],
            "assigned_style_family_key": pair[1],
        }
        for index, pair in enumerate(result, start=1)
    ]


def parse_retained_items(value: str, stage: str) -> list[dict[str, object]]:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("--retained-selection-json is not valid JSON") from exc
    if not isinstance(raw, list):
        raise ValueError("--retained-selection-json must be a JSON array")
    if not raw:
        return []
    return canonicalize_selection_items(raw, stage)


def resolve_selection_expression(
    expression: str,
    rows: list[dict[str, str]],
    stage: str,
    round_number: int,
    profile: dict[str, str],
    library: dict[str, dict[str, str]],
    retained_items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if "\n" in expression or "\r" in expression:
        raise ValueError("Selection expression must be a single line")
    raw = expression.strip()
    if not raw:
        raise ValueError("Selection expression is empty")
    tokens = [token.strip() for token in raw.split("+")]
    if any(not token for token in tokens) or len(tokens) != len(set(tokens)):
        raise ValueError("Selection expression contains an empty or duplicate token")
    if any(token.isdigit() and token not in {"1", "2", "3", "4"} for token in tokens):
        raise ValueError("Numeric selection options must be 1, 2, 3, or 4")
    numeric = all(re.fullmatch(r"[1-4]", token) for token in tokens)
    labels = {normalize_custom_label(row["label_cn"]).casefold(): index for index, row in enumerate(rows, start=1)}
    label_mode = all(
        normalize_custom_label(token).casefold() in labels
        or normalize_custom_label(token) == "更多其他"
        for token in tokens
    )
    if not numeric and not label_mode:
        if any(re.fullmatch(r"[1-4]", token) for token in tokens):
            raise ValueError(
                "Do not mix numeric choices with custom range names"
            )
        added: list[dict[str, object]] = []
        for token in tokens:
            custom_label = normalize_custom_label(token)
            matches = [
                row
                for row in library.values()
                if row.get("stage") == stage
                and normalize_custom_label(row.get("label_cn", "")).casefold()
                == custom_label.casefold()
                and (
                    stage == "color"
                    or style_row_is_eligible(row, resolve_style_group(profile))
                )
            ]
            if len(matches) > 1:
                raise ValueError("Range name is ambiguous in the eligible library scope")
            if len(matches) == 1:
                matched = matches[0]
                added.append(
                    selection_item(
                        stage,
                        option_id=matched["id"],
                        label=matched["label_cn"],
                        round_number=0,
                        option_number=0,
                        source="library",
                    )
                )
                continue
            if resolve_age_domain(profile) != "adult":
                raise ValueError(
                    "Unknown custom wardrobe names require a clearly adult profile; "
                    "choose an eligible minor-safe library direction"
                )
            added.append(
                selection_item(
                    stage,
                    option_id="",
                    label=custom_label,
                    round_number=0,
                    option_number=0,
                    source="user-custom",
                )
            )
        selected = merge_selection_items(
            list(retained_items or []), added, stage
        )
        return {
            "selected": selected,
            "refresh_requested": False,
            "finalizable": True,
        }
    indices: list[int] = []
    refresh = False
    for token in tokens:
        index = int(token) if numeric else (
            4
            if normalize_custom_label(token) == "更多其他"
            else labels[normalize_custom_label(token).casefold()]
        )
        if index == 4:
            refresh = True
        else:
            indices.append(index)
    added: list[dict[str, object]] = []
    for index in indices:
        row = rows[index - 1]
        added.append(
            selection_item(
                stage,
                option_id=row["id"],
                label=row["label_cn"],
                round_number=round_number,
                option_number=index,
                source="library",
            )
        )
    if not retained_items and not added and not refresh:
        raise ValueError("Select at least one range")
    canonical = (
        merge_selection_items(list(retained_items or []), added, stage)
        if retained_items or added
        else []
    )
    return {
        "selected": canonical,
        "refresh_requested": refresh,
        "finalizable": bool(canonical) and not refresh,
    }


def cli_selection_items(
    stage: str,
    ids: list[str],
    labels: list[str],
    rounds: list[int],
    options: list[int],
    library: dict[str, dict[str, str]],
    profile: dict[str, str],
    *,
    user_specified: bool = False,
) -> list[dict[str, object]]:
    normalized_ids = [value.strip().upper() for value in ids if value.strip()]
    if not normalized_ids:
        raise ValueError(f"At least one --selected-{stage}-id is required")
    if labels and len(labels) != len(normalized_ids):
        raise ValueError(f"Selected {stage} labels must align one-to-one with IDs")
    if bool(rounds) != bool(options):
        raise ValueError(f"Selected {stage} rounds and options must be supplied together")
    if rounds and (len(rounds) != len(normalized_ids) or len(options) != len(normalized_ids)):
        raise ValueError(f"Selected {stage} provenance must align one-to-one with IDs")
    if not rounds:
        if user_specified:
            rounds = [0] * len(normalized_ids)
            options = [0] * len(normalized_ids)
        elif len(normalized_ids) > 1:
            raise ValueError(
                f"Multi-range {stage} finalization requires one round and option per ID"
            )
        else:
            rounds = [1]
            options = [1]

    items: list[dict[str, object]] = []
    for index, option_id in enumerate(normalized_ids):
        provided_label = normalize_custom_label(labels[index]) if labels else ""
        if option_id == "CUSTOM":
            if not provided_label:
                raise ValueError(f"CUSTOM {stage} requires a matching selected label")
            item = selection_item(
                stage,
                option_id="",
                label=provided_label,
                round_number=0,
                option_number=0,
                source="user-custom",
            )
        else:
            row = library.get(option_id)
            if row is None or row.get("stage") != stage:
                raise ValueError(f"{option_id!r} is not a valid selected {stage} ID")
            if provided_label and provided_label != row["label_cn"]:
                raise ValueError(f"Selected {stage} label does not match {option_id}")
            if (
                stage == "style"
                and not style_row_is_eligible(row, resolve_style_group(profile))
                and not (
                    user_specified
                    and resolve_age_domain(profile) == "adult"
                    and "adult" in style_row_age_domains(row)
                )
            ):
                raise ValueError(
                    f"Selected style {option_id} is outside resolved style group "
                    f"{resolve_style_group(profile)}"
                )
            item = selection_item(
                stage,
                option_id=option_id,
                label=row["label_cn"],
                round_number=rounds[index],
                option_number=options[index],
                source="library",
            )
        items.append(item)
    canonical = canonicalize_selection_items(items, stage)
    if any(item["source"] == "user-custom" for item in canonical):
        if resolve_age_domain(profile) != "adult":
            raise ValueError(
                "Custom wardrobe ranges require a clearly adult profile"
            )
    return canonical


def finalize_v1(
    args: argparse.Namespace,
    profile: dict[str, str],
    library: dict[str, dict[str, str]],
) -> dict[str, object]:
    if len(args.selected_color_id) != 1 or len(args.selected_style_id) != 1:
        raise ValueError("Selection schema v1 supports exactly one color and one style")
    color_id = args.selected_color_id[0].strip().upper()
    style_id = args.selected_style_id[0].strip().upper()
    selected_color = library.get(color_id)
    selected_style = library.get(style_id)
    if args.recommendation_method == "user-specified":
        basis = validate_basis("color", args.basis)
        custom_override = (args.custom_override or "").strip()
        if not custom_override:
            raise ValueError("User-specified v1 finalization requires --custom-override")
        if resolve_age_domain(profile) != "adult":
            raise ValueError(
                "User-specified wardrobe is not permitted for a child or age-uncertain profile"
            )
        color_label = (
            normalize_custom_label(args.selected_color_label[0])
            if color_id == "CUSTOM" and args.selected_color_label
            else selected_color["label_cn"] if selected_color else ""
        )
        style_label = (
            normalize_custom_label(args.selected_style_label[0])
            if style_id == "CUSTOM" and args.selected_style_label
            else selected_style["label_cn"] if selected_style else ""
        )
        if not color_label or not style_label:
            raise ValueError("Invalid v1 user-specified color or style")
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
        return {
            "choice_type": "wardrobe_selection",
            **selection_core,
            "recommendation_fingerprint": fingerprint(selection_core),
        }
    if selected_color is None or selected_color.get("stage") != "color":
        raise ValueError("--selected-color-id must identify one color option")
    if selected_style is None or selected_style.get("stage") != "style":
        raise ValueError("--selected-style-id must identify one style option")
    if not style_row_is_eligible(selected_style, resolve_style_group(profile)):
        raise ValueError(
            "--selected-style-id is outside resolved style group "
            f"{resolve_style_group(profile)}"
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
        "resolved_style_group": resolve_style_group(profile),
    }
    return {
        "choice_type": "wardrobe_selection",
        **selection_core,
        "recommendation_fingerprint": fingerprint(selection_core),
    }


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
    if row.get("wardrobe_selection_schema_version", "") == SELECTION_SCHEMA_VERSION:
        return validate_v2_selection_binding(row, library, profile)
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

    if len({row["label_cn"].casefold() for row in rows}) != 3:
        raise ValueError(
            f"The three {stage} recommendations must use distinct visible labels"
        )

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

    if args.stage == "finalize":
        use_v1 = args.selection_schema_version == "1" or (
            args.selection_schema_version == "auto"
            and len(args.selected_color_id) == 1
            and len(args.selected_style_id) == 1
            and args.assignment_count is None
            and not args.selected_color_round
            and not args.selected_color_option
            and not args.selected_style_round
            and not args.selected_style_option
        )
        if use_v1:
            payload = finalize_v1(args, profile, library)
            payload["expansion_contract"] = {
                "minimum_sub_palettes": 4,
                "minimum_silhouettes": 4,
                "minimum_substyles": 4,
                "reuse_rule": "cover-each-approved-pool-before-reuse",
                "boundary": "maximize diversity without leaving the selected single ranges",
            }
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0

        basis = validate_basis("color", args.basis or ["visible-appearance"])
        colors = cli_selection_items(
            "color",
            args.selected_color_id,
            args.selected_color_label,
            args.selected_color_round,
            args.selected_color_option,
            library,
            profile,
            user_specified=args.recommendation_method in {"user-specified", "mixed"},
        )
        styles = cli_selection_items(
            "style",
            args.selected_style_id,
            args.selected_style_label,
            args.selected_style_round,
            args.selected_style_option,
            library,
            profile,
            user_specified=args.recommendation_method in {"user-specified", "mixed"},
        )
        selected_ranges = canonical_selection_payload(colors, styles)
        selected_ranges_json = compact_json(selected_ranges)
        method = selection_method(selected_ranges)
        custom_override = selection_custom_override(selected_ranges)
        if args.custom_override is not None and args.custom_override.strip() != custom_override:
            raise ValueError(
                "--custom-override must exactly match the custom range labels in canonical order"
            )
        one_color = colors[0] if len(colors) == 1 else None
        one_style = styles[0] if len(styles) == 1 else None
        row_core = {
            "wardrobe_selection_schema_version": SELECTION_SCHEMA_VERSION,
            "wardrobe_library_version": LIBRARY_VERSION,
            "wardrobe_recommendation_method": method,
            "character_id": profile["character_id"],
            "character_profile_version": profile["profile_version"],
            "character_profile_sha256": profile["_profile_sha256"],
            "wardrobe_evidence_basis": ";".join(basis),
            "wardrobe_selected_ranges_json": selected_ranges_json,
            "wardrobe_assignment_strategy": ASSIGNMENT_STRATEGY,
            "color_direction_id": (
                str(one_color["id"])
                if one_color and one_color["source"] == "library"
                else "CUSTOM" if one_color else "not-applicable"
            ),
            "color_direction_label": str(one_color["label"]) if one_color else "not-applicable",
            "color_choice_round": str(one_color["round"]) if one_color else "0",
            "color_choice_option": str(one_color["option"]) if one_color else "0",
            "style_family_id": (
                str(one_style["id"])
                if one_style and one_style["source"] == "library"
                else "CUSTOM" if one_style else "not-applicable"
            ),
            "style_family_label": str(one_style["label"]) if one_style else "not-applicable",
            "style_choice_round": str(one_style["round"]) if one_style else "0",
            "style_choice_option": str(one_style["option"]) if one_style else "0",
            "wardrobe_custom_override": custom_override,
        }
        core = v2_selection_core(row_core, profile, selected_ranges)
        recommendation_fingerprint = fingerprint(core)
        assignments: list[dict[str, object]] = []
        effective_assignment_seed = (
            args.assignment_seed or recommendation_fingerprint
        )
        if args.assignment_count is not None:
            assignments = build_balanced_scattered_assignments(
                selected_ranges,
                args.assignment_count,
                effective_assignment_seed,
            )
        print(
            json.dumps(
                {
                    "choice_type": "wardrobe_selection",
                    **row_core,
                    "selected_ranges": selected_ranges,
                    "resolved_style_group": resolved_style_group,
                    "eligible_style_groups": eligible_groups,
                    "recommendation_fingerprint": recommendation_fingerprint,
                    "adaptation_seed": effective_assignment_seed,
                    "assignments": assignments,
                    "expansion_contract": {
                        "minimum_sub_palettes": 4,
                        "minimum_silhouettes": 4,
                        "minimum_substyles": 4,
                        "reuse_rule": "cover-each-approved-pool-before-reuse",
                        "assignment_rule": ASSIGNMENT_STRATEGY,
                        "boundary": "each row uses exactly one selected color range and one selected style range without same-dimension mixing",
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
    selected_colors: list[dict[str, object]] = []
    if args.stage == "style":
        if not args.selected_color_id:
            raise ValueError("Style recommendations require --selected-color-id")
        selected_colors = cli_selection_items(
            "color",
            args.selected_color_id,
            args.selected_color_label,
            args.selected_color_round,
            args.selected_color_option,
            library,
            profile,
            user_specified=False,
        )
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
        "selected_colors": selected_colors,
        "option_ids": [row["id"] for row in rows],
        "reasons": [value.strip() for value in args.reason],
    }
    if args.stage == "style":
        recommendation_core["resolved_style_group"] = resolved_style_group
    options = [
        option_payload(row, reason, index, args.stage, args.round)
        for index, (row, reason) in enumerate(zip(rows, args.reason), start=1)
    ]
    retained = parse_retained_items(args.retained_selection_json, args.stage)
    selection_resolution = None
    if args.selection_expression is not None:
        selection_resolution = resolve_selection_expression(
            args.selection_expression,
            rows,
            args.stage,
            args.round,
            profile,
            library,
            retained,
        )
        selection_resolution["next_exclude_ids"] = sorted(
            excluded_ids | {row["id"] for row in rows}
        )
    print(
        json.dumps(
            {
                "choice_type": "color_direction" if args.stage == "color" else "wardrobe_style",
                **recommendation_core,
                "eligible_style_groups": eligible_groups if args.stage == "style" else [],
                "recommendation_fingerprint": fingerprint(recommendation_core),
                "selection_mode": "multi-range-union",
                "selection_guidance": WARDROBE_SELECTION_GUIDANCE,
                "selected_color": (
                    {
                        "id": selected_colors[0]["id"],
                        "label": selected_colors[0]["label"],
                        "visual_direction": library[
                            str(selected_colors[0]["id"])
                        ]["visual_direction"],
                    }
                    if len(selected_colors) == 1
                    and selected_colors[0]["source"] == "library"
                    else None
                ),
                "selected_colors": selected_colors,
                "retained_selections": retained,
                "selection_resolution": selection_resolution,
                "options": options,
                "more_option": {
                    "index": 4,
                    "option_id": f"{args.stage}-round-{args.round}-more",
                    "label": "更多其他",
                    "next_round": args.round + 1,
                    "preserves_selected_color": args.stage == "style",
                    "preserves_style_group": args.stage == "style",
                    "preserves_retained_selections": True,
                    "never_enters_selected_ranges": True,
                },
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
