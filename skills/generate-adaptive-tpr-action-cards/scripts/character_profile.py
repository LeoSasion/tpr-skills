#!/usr/bin/env python3
"""Validate character evidence and produce reproducible persona/wardrobe factors."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
import re
from pathlib import Path

from batch_common import (
    WARDROBE_SELECTION_FIELDS,
    WARDROBE_V2_ASSIGNMENT_FIELDS,
    WARDROBE_V2_BATCH_FIELDS,
    read_manifest,
    validate_wardrobe_provenance,
)


PROFILE_FIELDS_V1 = [
    "character_id",
    "profile_version",
    "character_kind",
    "identity_anchors",
    "appearance_summary",
    "proportion_summary",
    "apparent_age_band",
    "age_confidence",
    "gender_presentation",
    "gender_confidence",
    "render_capabilities",
    "analysis_confidence",
    "uncertain_fields",
    "recommended_persona",
    "persona_candidates",
    "wardrobe_policy",
    "outfit_palette_options",
    "outfit_silhouette_options",
    "outfit_style_options",
    "signature_outfit",
    "action_safety_notes",
    "do_not_change",
    "avoid_outfit_features",
    "analysis_basis",
    "status",
]
PROFILE_FIELDS_V2 = [
    *PROFILE_FIELDS_V1[: PROFILE_FIELDS_V1.index("signature_outfit")],
    "wardrobe_range_pools_json",
    *PROFILE_FIELDS_V1[PROFILE_FIELDS_V1.index("signature_outfit") :],
]
PROFILE_FIELDS = PROFILE_FIELDS_V2
CHARACTER_KINDS = {
    "human",
    "animal",
    "mascot",
    "doll-or-toy",
    "robot",
    "fantasy-creature",
    "stylized-figure",
    "other",
}
AGE_BANDS = {
    "infant",
    "toddler",
    "child",
    "teen",
    "young-adult",
    "adult",
    "older-adult",
    "juvenile",
    "mature",
    "ageless",
    "not-applicable",
    "uncertain",
}
GENDER_PRESENTATIONS = {
    "feminine",
    "masculine",
    "androgynous",
    "neutral",
    "not-applicable",
    "uncertain",
}
CONFIDENCES = {"low", "medium", "high", "not-applicable"}
WARDROBE_POLICIES = {"varied", "signature-variants", "fixed", "none"}
ADAPTATION_MODES = {"recommend", "specified"}
# These are optional action-safe styling details used when a batch is longer
# than the profile's base color/silhouette/style combinations.  They keep the
# complete outfit text unique while the audited factor fields stay in-pool.
OUTFIT_DETAIL_VARIANTS = (
    "tonal piping",
    "textured knit finish",
    "soft pleat detail",
    "minimal belt detail",
    "rolled cuff detail",
    "utility pocket accents",
    "ribbed fabric finish",
    "structured collar detail",
)
ADAPTATION_STATUSES = {"pass", "fallback", "blocked"}
ADAPTATION_REASONS = {
    "ok",
    "safe-override",
    "ambiguous-subject",
    "insufficient-reference",
    "conflicting-references",
    "morphology-incompatible",
    "unsafe-outfit",
    "profile-mismatch",
}
SUITABILITY_HANDLINGS = {
    "none",
    "confirm-or-neutralize",
    "partial-cue-only",
    "explicit-context-only",
    "symbolic-safe-only",
    "layered-safe-only",
}
CHARACTER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ADULT_CHILD_SAFETY_LOCK_NOTE_MARKERS = (
    "nonsexualized",
    "non-sexualized",
    "never sexualize",
    "do not sexualize",
    "不得性感化",
    "不得性化",
    "非性感化",
    "全覆盖服装",
    "全身遮盖",
    "不得露肤",
    "opaque from neckline to ankles",
    "fully opaque",
    "opaque clothing",
    "modest clothing",
    "conservative clothing",
    "fully clothed",
    "fully covered",
    "non-exposing",
    "no exposure",
    "不透明服装",
    "保守服装",
    "完全穿着",
    "完全遮盖",
    "不得暴露",
)
ADULT_CHILD_SAFETY_LOCK_AVOID_MARKERS = (
    "low neckline",
    "bare midriff",
    "lingerie styling",
    "lingerie-inspired",
    "sleeveless",
    "camisole",
    "strapless",
    "off-shoulder",
    "open-back",
    "high slit",
    "short hem",
    "short-hem",
    "swimwear",
    "bikini",
    "cleavage",
    "sheer or translucent fabric",
    "sheer fabric",
    "translucent fabric",
    "transparent fabric",
    "revealing clothing",
    "revealing outfit",
    "nudity",
    "high heels",
    "低领",
    "露脐",
    "露腰",
    "内衣风",
    "无袖",
    "吊带",
    "抹胸",
    "露肩",
    "露背",
    "高开衩",
    "短下装",
    "短裙",
    "泳装",
    "比基尼",
    "乳沟",
    "透视",
    "透明材质",
    "裸露",
    "裸体",
    "高跟鞋",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("profile_csv", type=Path)
    validate.add_argument("--photo-pool", type=Path)
    validate.add_argument("--manifest", type=Path)

    suggest = subparsers.add_parser("suggest")
    suggest.add_argument("profile_csv", type=Path)
    suggest.add_argument("--character-id", required=True)
    suggest.add_argument(
        "--mode",
        choices=["recommend", "specified"],
        required=True,
        help="Final batch mode. Wardrobe recommendations are handled by the two-round chooser.",
    )
    suggest.add_argument("--seed")
    suggest.add_argument("--selected-ranges-json")
    suggest.add_argument("--assignment-seed")
    suggest.add_argument("--persona")
    suggest.add_argument("--count", type=int, required=True)
    return parser.parse_args()


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def compact_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def parse_range_pools(value: str) -> dict[str, object]:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("wardrobe_range_pools_json is not valid JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {"colors", "styles"}:
        raise ValueError(
            "wardrobe_range_pools_json must contain exactly colors and styles"
        )
    colors = raw["colors"]
    styles = raw["styles"]
    if not isinstance(colors, dict) or not isinstance(styles, dict):
        raise ValueError("wardrobe range colors/styles must be JSON objects")
    canonical_colors: dict[str, list[str]] = {}
    for key, raw_values in colors.items():
        if not re.fullmatch(r"(?:C\d{2}|CUSTOM-C-[0-9A-F]{16})", str(key)):
            raise ValueError(f"Invalid color range key {key!r}")
        if not isinstance(raw_values, list) or not raw_values:
            raise ValueError(f"Color range {key} must contain a non-empty array")
        values = [str(item).strip() for item in raw_values]
        if any(not item or ";" in item or "\n" in item or "\r" in item for item in values):
            raise ValueError(f"Color range {key} contains an invalid factor value")
        if len({item.casefold() for item in values}) != len(values):
            raise ValueError(f"Color range {key} contains duplicate factor values")
        canonical_colors[str(key)] = values
    canonical_styles: dict[str, dict[str, list[str]]] = {}
    for key, raw_pools in styles.items():
        if not re.fullmatch(r"(?:S\d{2}|CUSTOM-S-[0-9A-F]{16})", str(key)):
            raise ValueError(f"Invalid style range key {key!r}")
        if not isinstance(raw_pools, dict) or set(raw_pools) != {
            "silhouettes",
            "substyles",
        }:
            raise ValueError(
                f"Style range {key} must contain exactly silhouettes and substyles"
            )
        canonical_pools: dict[str, list[str]] = {}
        for pool_name in ("silhouettes", "substyles"):
            raw_values = raw_pools[pool_name]
            if not isinstance(raw_values, list) or not raw_values:
                raise ValueError(
                    f"Style range {key} {pool_name} must contain a non-empty array"
                )
            values = [str(item).strip() for item in raw_values]
            if any(
                not item or ";" in item or "\n" in item or "\r" in item
                for item in values
            ):
                raise ValueError(
                    f"Style range {key} {pool_name} contains an invalid factor value"
                )
            if len({item.casefold() for item in values}) != len(values):
                raise ValueError(
                    f"Style range {key} {pool_name} contains duplicate factor values"
                )
            canonical_pools[pool_name] = values
        canonical_styles[str(key)] = canonical_pools
    payload: dict[str, object] = {
        "colors": dict(sorted(canonical_colors.items())),
        "styles": dict(sorted(canonical_styles.items())),
    }
    if value != compact_json(payload):
        raise ValueError("wardrobe_range_pools_json is not canonical compact JSON")
    return payload


def validate_range_pools_against_profile(
    profile: dict[str, str],
    selected_color_keys: set[str] | None = None,
    selected_style_keys: set[str] | None = None,
) -> list[str]:
    label = profile.get("character_id", "?")
    value = profile.get("wardrobe_range_pools_json", "")
    if not value:
        return [f"{label}: wardrobe_range_pools_json is required for v2 wardrobe selection"]
    try:
        pools = parse_range_pools(value)
    except ValueError as exc:
        return [f"{label}: {exc}"]
    colors = pools["colors"]
    styles = pools["styles"]
    errors: list[str] = []
    for key, values in colors.items():
        if len(values) < 4:
            errors.append(
                f"{label}: color range {key} requires at least four approved sub-palettes"
            )
    for key, style_pools in styles.items():
        for pool_name in ("silhouettes", "substyles"):
            if len(style_pools[pool_name]) < 4:
                errors.append(
                    f"{label}: style range {key} requires at least four approved {pool_name}"
                )
    if selected_color_keys is not None and set(colors) != selected_color_keys:
        errors.append(
            f"{label}: color range-pool keys do not exactly match selected color keys"
        )
    if selected_style_keys is not None and set(styles) != selected_style_keys:
        errors.append(
            f"{label}: style range-pool keys do not exactly match selected style keys"
        )
    flat_colors = {
        item.casefold() for values in colors.values() for item in values
    }
    flat_silhouettes = {
        item.casefold()
        for pools_for_style in styles.values()
        for item in pools_for_style["silhouettes"]
    }
    flat_substyles = {
        item.casefold()
        for pools_for_style in styles.values()
        for item in pools_for_style["substyles"]
    }
    expected = {
        "outfit_palette_options": flat_colors,
        "outfit_silhouette_options": flat_silhouettes,
        "outfit_style_options": flat_substyles,
    }
    for field, union in expected.items():
        actual = {item.casefold() for item in split_values(profile.get(field, ""))}
        if actual != union:
            errors.append(
                f"{label}: {field} must equal the exact union of wardrobe range pools"
            )
    return errors


def duplicated(values: list[str]) -> list[str]:
    seen: set[str] = set()
    repeats: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            repeats.append(value)
        else:
            seen.add(key)
    return repeats


def profile_sha256(row: dict[str, str]) -> str:
    fields = (
        PROFILE_FIELDS_V2
        if "wardrobe_range_pools_json" in row
        else PROFILE_FIELDS_V1
    )
    canonical = {field: row.get(field, "") for field in fields}
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def adult_profile_wardrobe_lock_conflicts(profile: dict[str, str]) -> list[str]:
    """Find child-only coverage or sexualization locks copied into an adult profile."""
    notes = profile.get("action_safety_notes", "").casefold()
    avoid = profile.get("avoid_outfit_features", "").casefold()
    conflicts = [
        f"action_safety_notes:{marker}"
        for marker in ADULT_CHILD_SAFETY_LOCK_NOTE_MARKERS
        if marker.casefold() in notes
    ]
    conflicts.extend(
        f"avoid_outfit_features:{marker}"
        for marker in ADULT_CHILD_SAFETY_LOCK_AVOID_MARKERS
        if marker.casefold() in avoid
    )
    return list(dict.fromkeys(conflicts))


def validate_adult_profile_wardrobe_lock(
    profile: dict[str, str],
    row: dict[str, str],
    *,
    age_domain: str,
) -> list[str]:
    """Keep child-only wardrobe safety review out of clearly adult profiles."""
    if age_domain != "adult":
        return []
    identifier = row.get("number", "?")
    conflicts = adult_profile_wardrobe_lock_conflicts(profile)
    if conflicts:
        return [
            f"{identifier}: clearly adult profile contains child-only wardrobe safety "
            f"locks {conflicts}; remove coverage/sexualization restrictions from the "
            "profile, express any user-requested conservative aesthetic only in the "
            "selected outfit pools, increment profile_version, and re-finalize the "
            "wardrobe fingerprint"
        ]
    return []


def validate_profile_row(row: dict[str, str], line: int) -> list[str]:
    label = row.get("character_id") or f"line {line}"
    errors: list[str] = []
    required = {
        "character_id",
        "profile_version",
        "character_kind",
        "identity_anchors",
        "appearance_summary",
        "proportion_summary",
        "apparent_age_band",
        "age_confidence",
        "gender_presentation",
        "gender_confidence",
        "render_capabilities",
        "analysis_confidence",
        "recommended_persona",
        "persona_candidates",
        "wardrobe_policy",
        "action_safety_notes",
        "do_not_change",
        "avoid_outfit_features",
        "analysis_basis",
        "status",
    }
    for field in required:
        if not row.get(field, ""):
            errors.append(f"{label}: {field} is empty")

    character_id = row.get("character_id", "")
    if character_id and not CHARACTER_ID_RE.fullmatch(character_id):
        errors.append(f"{label}: character_id must contain only letters, digits, . _ or -")
    try:
        if int(row.get("profile_version", "0")) < 1:
            raise ValueError
    except ValueError:
        errors.append(f"{label}: profile_version must be a positive integer")

    if row.get("character_kind") not in CHARACTER_KINDS:
        errors.append(f"{label}: unsupported character_kind {row.get('character_kind')!r}")
    if row.get("apparent_age_band") not in AGE_BANDS:
        errors.append(f"{label}: unsupported apparent_age_band {row.get('apparent_age_band')!r}")
    if row.get("gender_presentation") not in GENDER_PRESENTATIONS:
        errors.append(
            f"{label}: unsupported gender_presentation {row.get('gender_presentation')!r}"
        )
    for field in ("age_confidence", "gender_confidence", "analysis_confidence"):
        if row.get(field) not in CONFIDENCES:
            errors.append(f"{label}: unsupported {field} {row.get(field)!r}")
    if row.get("wardrobe_policy") not in WARDROBE_POLICIES:
        errors.append(f"{label}: unsupported wardrobe_policy {row.get('wardrobe_policy')!r}")
    if row.get("status") != "approved":
        errors.append(f"{label}: status must be approved before planning")

    anchors = split_values(row.get("identity_anchors", ""))
    if len(anchors) < 2:
        errors.append(f"{label}: at least two stable identity_anchors are required")
    candidates = split_values(row.get("persona_candidates", ""))
    if len(candidates) < 2:
        errors.append(f"{label}: at least two persona_candidates are required")
    if row.get("recommended_persona", "").casefold() not in {
        value.casefold() for value in candidates
    }:
        errors.append(f"{label}: recommended_persona is not in persona_candidates")

    for field in (
        "identity_anchors",
        "render_capabilities",
        "uncertain_fields",
        "persona_candidates",
        "outfit_palette_options",
        "outfit_silhouette_options",
        "outfit_style_options",
        "analysis_basis",
    ):
        repeats = duplicated(split_values(row.get(field, "")))
        if repeats:
            errors.append(f"{label}: {field} contains duplicate values {repeats}")

    capabilities = split_values(row.get("render_capabilities", ""))
    invalid_capabilities = [value for value in capabilities if not TOKEN_RE.fullmatch(value)]
    if invalid_capabilities:
        errors.append(
            f"{label}: render_capabilities must be lowercase hyphenated tokens: "
            f"{invalid_capabilities}"
        )

    uncertain = {value.casefold() for value in split_values(row.get("uncertain_fields", ""))}
    allowed_uncertain = {
        "character_kind",
        "identity_anchors",
        "appearance_summary",
        "proportion_summary",
        "apparent_age_band",
        "gender_presentation",
    }
    unknown_uncertain = sorted(uncertain - allowed_uncertain)
    if unknown_uncertain:
        errors.append(f"{label}: uncertain_fields contains unsupported names {unknown_uncertain}")
    if "apparent_age_band" in uncertain and row.get("apparent_age_band") != "uncertain":
        errors.append(f"{label}: uncertain apparent_age_band must use the value uncertain")
    if "gender_presentation" in uncertain and row.get("gender_presentation") not in {
        "neutral",
        "uncertain",
    }:
        errors.append(
            f"{label}: uncertain gender presentation must be neutral or uncertain"
        )

    policy = row.get("wardrobe_policy")
    palette = split_values(row.get("outfit_palette_options", ""))
    silhouettes = split_values(row.get("outfit_silhouette_options", ""))
    styles = split_values(row.get("outfit_style_options", ""))
    signature = row.get("signature_outfit", "")
    if policy in {"varied", "signature-variants"}:
        required_pool_size = 4 if policy == "varied" else 2
        if min(len(palette), len(silhouettes), len(styles)) < required_pool_size:
            errors.append(
                f"{label}: {policy} requires at least {required_pool_size} palette, silhouette, and style options"
            )
        minimum_palette = 4 if policy == "varied" else 3
        if len(palette) < minimum_palette:
            errors.append(
                f"{label}: {policy} requires at least {minimum_palette} palette values for broad in-range diversity"
            )
        if policy == "signature-variants" and not signature:
            errors.append(f"{label}: signature-variants requires signature_outfit")
    elif policy == "fixed" and not signature:
        errors.append(f"{label}: fixed wardrobe requires signature_outfit")
    elif policy == "none" and signature.casefold() != "not-applicable":
        errors.append(f"{label}: no-clothing profile must set signature_outfit to not-applicable")
    if row.get("wardrobe_range_pools_json", ""):
        errors.extend(validate_range_pools_against_profile(row))
    return errors


def load_profiles(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    errors: list[str] = []
    profiles: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if tuple(fieldnames) not in {tuple(PROFILE_FIELDS_V1), tuple(PROFILE_FIELDS_V2)}:
            raise ValueError(
                "Character profile must contain exactly the v1 or v2 field set"
            )
        for line, raw in enumerate(reader, start=2):
            row = {key: (value or "") for key, value in raw.items()}
            for field, value in row.items():
                if value != value.strip():
                    errors.append(f"line {line}: {field} has leading or trailing whitespace")
            errors.extend(validate_profile_row(row, line))
            character_id = row.get("character_id", "")
            if character_id in profiles:
                errors.append(f"line {line}: duplicate character_id {character_id!r}")
            elif character_id:
                row["_profile_sha256"] = profile_sha256(row)
                profiles[character_id] = row
    if not profiles:
        errors.append("Character profile contains no rows")
    return profiles, errors


def validate_photo_pool(
    profiles: dict[str, dict[str, str]], photo_pool: Path
) -> list[str]:
    errors: list[str] = []
    with photo_pool.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"character_id", "filename", "source_kind", "status"}
        if not required.issubset(reader.fieldnames or []):
            return [f"Photo pool must contain {sorted(required)}"]
        rows = [{key: (value or "") for key, value in raw.items()} for raw in reader]
    approved = {
        (row["character_id"], row["filename"])
        for row in rows
        if row.get("status") == "approved" and row.get("source_kind") == "original"
    }
    for character_id, profile in profiles.items():
        for filename in split_values(profile.get("analysis_basis", "")):
            if (character_id, filename) not in approved:
                errors.append(
                    f"{character_id}: analysis_basis {filename!r} is not an approved original"
                )
    return errors


def validate_v2_assignment_plan(rows: list[dict[str, str]]) -> list[str]:
    """Recompute every v2 range assignment in full manifest order."""
    from wardrobe_choice import (
        build_balanced_scattered_assignments,
        parse_selection_payload,
    )

    errors: list[str] = []
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("wardrobe_selection_schema_version") != "2":
            continue
        if row.get("wardrobe_policy") not in {"varied", "signature-variants"}:
            continue
        key = (
            row.get("batch_id", ""),
            row.get("character_id", ""),
            row.get("wardrobe_recommendation_fingerprint", ""),
        )
        groups.setdefault(key, []).append(row)

    for (batch_id, character_id, digest), group_rows in groups.items():
        first = group_rows[0]
        selected_json = first.get("wardrobe_selected_ranges_json", "")
        seed = first.get("adaptation_seed", "") or digest
        for row in group_rows[1:]:
            for field in (
                "wardrobe_selected_ranges_json",
                "wardrobe_assignment_strategy",
                "adaptation_seed",
            ):
                if row.get(field, "") != first.get(field, ""):
                    errors.append(
                        f"{row.get('number', '?')}: {field} must be stable for "
                        "v2 range assignment"
                    )
        try:
            payload = parse_selection_payload(selected_json)
            expected = build_balanced_scattered_assignments(
                payload,
                len(group_rows),
                seed,
            )
        except ValueError as exc:
            errors.append(
                f"{batch_id or '?'}/{character_id or '?'}: cannot rebuild "
                f"v2 assignments: {exc}"
            )
            continue

        for row, assignment in zip(group_rows, expected):
            for field in WARDROBE_V2_ASSIGNMENT_FIELDS:
                if row.get(field, "") != assignment[field]:
                    errors.append(
                        f"{row.get('number', '?')}: {field} does not match "
                        "balanced-scattered-v1 recomputation"
                    )

        color_keys = [str(item["key"]) for item in payload["colors"]]
        style_keys = [str(item["key"]) for item in payload["styles"]]
        color_counts = [
            sum(
                row.get("assigned_color_direction_key") == key
                for row in group_rows
            )
            for key in color_keys
        ]
        style_counts = [
            sum(
                row.get("assigned_style_family_key") == key
                for row in group_rows
            )
            for key in style_keys
        ]
        for dimension, counts in (("color", color_counts), ("style", style_counts)):
            if counts and max(counts) - min(counts) > 1:
                errors.append(
                    f"{character_id}: v2 {dimension} range usage is unbalanced {counts}"
                )
        pair_counts = {
            (color_key, style_key): sum(
                row.get("assigned_color_direction_key") == color_key
                and row.get("assigned_style_family_key") == style_key
                for row in group_rows
            )
            for color_key in color_keys
            for style_key in style_keys
        }
        if pair_counts and max(pair_counts.values()) - min(pair_counts.values()) > 1:
            errors.append(
                f"{character_id}: v2 color/style pair usage is unbalanced "
                f"{sorted(pair_counts.values())}"
            )
        if len(pair_counts) > 1:
            for left, middle, right in zip(
                group_rows, group_rows[1:], group_rows[2:]
            ):
                triples = [
                    (
                        item.get("assigned_color_direction_key"),
                        item.get("assigned_style_family_key"),
                    )
                    for item in (left, middle, right)
                ]
                if len(set(triples)) == 1:
                    errors.append(
                        f"{left.get('number', '?')}/{middle.get('number', '?')}/"
                        f"{right.get('number', '?')}: v2 range assignment repeats "
                        "the same pair three times consecutively"
                    )
    return errors


def validate_manifest_profiles(
    profiles: dict[str, dict[str, str]],
    manifest: Path,
    selected_rows: list[dict[str, str]] | None = None,
    wardrobe_library: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    # Import lazily because wardrobe_choice imports load_profiles from this
    # module.  The local import lets profile-aware plan and delivery gates bind
    # a current model-curated style to its resolved recommendation group
    # without introducing an import cycle during CLI startup.
    from wardrobe_choice import (
        DEFAULT_LIBRARY as DEFAULT_WARDROBE_LIBRARY,
        load_library as load_wardrobe_library,
        parse_selection_payload,
        resolve_age_domain,
        validate_model_curated_binding,
    )

    errors: list[str] = []
    fieldnames, all_rows = read_manifest(manifest)
    errors.extend(validate_v2_assignment_plan(all_rows))
    rows = all_rows if selected_rows is None else selected_rows
    if wardrobe_library is None:
        wardrobe_library = load_wardrobe_library(DEFAULT_WARDROBE_LIBRARY)
    required_fields = {
        "character_id",
        "character_profile_version",
        "character_profile_sha256",
        "adaptation_mode",
        "adaptation_seed",
        "persona",
        "wardrobe_policy",
        "required_render_capabilities",
        "action_risk_tags",
        "suitability_handling",
        "adaptation_status",
        "adaptation_reason",
        *WARDROBE_SELECTION_FIELDS,
    }
    missing = sorted(required_fields - set(fieldnames))
    if missing:
        return [f"Manifest is missing character-adaptation fields {missing}"]
    present_v2 = set(WARDROBE_V2_BATCH_FIELDS) | set(WARDROBE_V2_ASSIGNMENT_FIELDS)
    if present_v2.intersection(fieldnames) and not present_v2.issubset(fieldnames):
        return [
            "Manifest has a partial wardrobe v2 profile-binding schema; missing "
            f"{sorted(present_v2 - set(fieldnames))}"
        ]

    batch_values: dict[str, tuple[str, ...]] = {}
    for row in rows:
        identifier = row["number"]
        character_id = row.get("character_id", "")
        profile = profiles.get(character_id)
        if profile is None:
            errors.append(f"{identifier}: unknown character_id {character_id!r}")
            continue
        if row.get("character_profile_version") != profile.get("profile_version"):
            errors.append(f"{identifier}: character profile version does not match")
        if row.get("character_profile_sha256") != profile.get("_profile_sha256"):
            errors.append(f"{identifier}: character profile SHA-256 does not match")
        if row.get("wardrobe_policy") != profile.get("wardrobe_policy"):
            errors.append(f"{identifier}: wardrobe_policy does not match character profile")

        mode = row.get("adaptation_mode", "")
        if mode not in ADAPTATION_MODES:
            errors.append(f"{identifier}: invalid adaptation_mode {mode!r}")
        if mode == "recommend" and row.get("persona") != profile.get("recommended_persona"):
            errors.append(f"{identifier}: recommend mode must use recommended_persona")
        elif mode == "specified" and not row.get("persona"):
            errors.append(f"{identifier}: specified mode requires persona")

        errors.extend(validate_wardrobe_provenance(row))
        errors.extend(validate_model_curated_binding(row, wardrobe_library, profile))
        if row.get("wardrobe_selection_schema_version") == "2":
            try:
                selected_ranges = parse_selection_payload(
                    row.get("wardrobe_selected_ranges_json", "")
                )
            except ValueError:
                # The selection validator above reports the exact JSON error.
                selected_ranges = None
            if selected_ranges is not None:
                errors.extend(
                    validate_range_pools_against_profile(
                        profile,
                        {
                            str(item["key"])
                            for item in selected_ranges["colors"]
                        },
                        {
                            str(item["key"])
                            for item in selected_ranges["styles"]
                        },
                    )
                )
        errors.extend(
            validate_adult_profile_wardrobe_lock(
                profile,
                row,
                age_domain=resolve_age_domain(profile),
            )
        )

        required_caps = split_values(row.get("required_render_capabilities", ""))
        if not required_caps:
            errors.append(f"{identifier}: required_render_capabilities is empty; use none")
        available = {value.casefold() for value in split_values(profile["render_capabilities"])}
        incompatible = sorted(
            value for value in required_caps if value.casefold() != "none" and value.casefold() not in available
        )
        if incompatible:
            errors.append(f"{identifier}: unsupported render capabilities {incompatible}")
        if not split_values(row.get("action_risk_tags", "")):
            errors.append(f"{identifier}: action_risk_tags is empty; use none")
        if row.get("suitability_handling", "") not in SUITABILITY_HANDLINGS:
            errors.append(f"{identifier}: invalid suitability_handling")

        status = row.get("adaptation_status", "")
        reason = row.get("adaptation_reason", "")
        if status not in ADAPTATION_STATUSES:
            errors.append(f"{identifier}: invalid adaptation_status {status!r}")
        if reason not in ADAPTATION_REASONS:
            errors.append(f"{identifier}: invalid adaptation_reason {reason!r}")
        if status == "pass" and reason != "ok":
            errors.append(f"{identifier}: pass adaptation must use reason ok")
        if status == "fallback" and reason != "safe-override":
            errors.append(f"{identifier}: fallback adaptation must use safe-override")
        if status == "blocked":
            errors.append(f"{identifier}: blocked character adaptation cannot be generated")

        values = (
            row.get("character_profile_version", ""),
            row.get("character_profile_sha256", ""),
            mode,
            row.get("adaptation_seed", ""),
            row.get("persona", ""),
            *(row.get(field, "") for field in WARDROBE_SELECTION_FIELDS),
            *(row.get(field, "") for field in WARDROBE_V2_BATCH_FIELDS),
        )
        prior = batch_values.setdefault(character_id, values)
        if prior != values:
            errors.append(
                f"{identifier}: profile, mode, persona, and two-round wardrobe selection must be stable "
                f"for character {character_id}"
            )
    return errors


def difference_count(left: tuple[str, str, str], right: tuple[str, str, str]) -> int:
    return sum(a.casefold() != b.casefold() for a, b in zip(left, right))


def build_diverse_sequence(
    combinations: list[tuple[str, str, str]],
    count: int,
    *,
    require_cycle_boundary: bool,
) -> list[tuple[str, str, str]]:
    """Greedily maximize visible factor distance and balanced pool coverage."""
    if not combinations or count < 1 or count > len(combinations):
        raise ValueError("Invalid wardrobe combination count")
    color_count = len({item[0].casefold() for item in combinations})
    start_attempts = min(len(combinations), 64)
    for start_index in range(start_attempts):
        pool = list(combinations)
        first = pool.pop(start_index)
        selected = [first]
        usage = [Counter({first[index].casefold(): 1}) for index in range(3)]
        while pool and len(selected) < count:
            eligible: list[tuple[int, tuple[str, str, str]]] = []
            for pool_index, item in enumerate(pool):
                if difference_count(selected[-1], item) < 2:
                    continue
                if color_count >= 2 and item[0].casefold() == selected[-1][0].casefold():
                    continue
                is_last = len(selected) + 1 == count
                if require_cycle_boundary and is_last:
                    if difference_count(item, first) < 2:
                        continue
                    if color_count >= 2 and item[0].casefold() == first[0].casefold():
                        continue
                eligible.append((pool_index, item))
            if not eligible:
                break

            def score(candidate: tuple[int, tuple[str, str, str]]) -> tuple[int, ...]:
                pool_index, item = candidate
                changed = difference_count(selected[-1], item)
                fresh_dimensions = sum(
                    usage[index][value.casefold()] == 0
                    for index, value in enumerate(item)
                )
                recent_distance = min(
                    difference_count(item, prior) for prior in selected[-8:]
                )
                dimension_usage = [
                    usage[index][value.casefold()] for index, value in enumerate(item)
                ]
                prospective_spreads: list[int] = []
                for index, value in enumerate(item):
                    next_usage = usage[index].copy()
                    next_usage[value.casefold()] += 1
                    all_values = {
                        candidate_item[index].casefold()
                        for candidate_item in combinations
                    }
                    counts = [next_usage[key] for key in all_values]
                    prospective_spreads.append(max(counts) - min(counts))
                return (
                    -max(prospective_spreads),
                    -sum(prospective_spreads),
                    changed,
                    fresh_dimensions,
                    recent_distance,
                    -max(dimension_usage),
                    -sum(dimension_usage),
                    -pool_index,
                )

            _, chosen = max(eligible, key=score)
            selected.append(chosen)
            pool.remove(chosen)
            for index, value in enumerate(chosen):
                usage[index][value.casefold()] += 1
        if len(selected) == count:
            return selected
    raise ValueError(
        "Could not arrange wardrobe factors with maximum feasible coverage and safe adjacency"
    )


def choose_factor_sequence(
    profile: dict[str, str], count: int, seed: str = ""
) -> list[tuple[str, str, str]]:
    policy = profile["wardrobe_policy"]
    if policy == "fixed":
        return [("fixed", "fixed", "fixed")] * count
    if policy == "none":
        return [("not-applicable", "not-applicable", "not-applicable")] * count

    palette = split_values(profile["outfit_palette_options"])
    silhouettes = split_values(profile["outfit_silhouette_options"])
    styles = split_values(profile["outfit_style_options"])
    combinations = list(itertools.product(palette, silhouettes, styles))
    if count > len(combinations):
        selected: list[tuple[str, str, str]] = []
        cycle_index = 0
        base_offset = int(
            hashlib.sha256(
                (seed or profile.get("_profile_sha256", "")).encode("utf-8")
            ).hexdigest(),
            16,
        ) % len(combinations)
        while len(selected) < count:
            # Advancing the offset guarantees that complete Cartesian cycles do
            # not replay in the same order while remaining deterministic.
            offset = (base_offset + cycle_index) % len(combinations)
            rotated = combinations[offset:] + combinations[:offset]
            cycle_count = min(len(combinations), count - len(selected))
            cycle = build_diverse_sequence(
                rotated,
                cycle_count,
                require_cycle_boundary=cycle_count == len(combinations),
            )
            if selected and len(cycle) > 1:
                for shift in range(len(cycle)):
                    candidate = cycle[shift:] + cycle[:shift]
                    if difference_count(selected[-1], candidate[0]) >= 2 and (
                        len(palette) < 2
                        or selected[-1][0].casefold() != candidate[0][0].casefold()
                    ):
                        cycle = candidate
                        break
            selected.extend(cycle)
            cycle_index += 1
        return selected
    return build_diverse_sequence(
        combinations,
        count,
        require_cycle_boundary=False,
    )


def deterministic_value_sequence(
    values: list[str], count: int, seed: str, key: str, dimension: str
) -> list[str]:
    result: list[str] = []
    cycle_index = 0
    while len(result) < count:
        ordered = sorted(
            values,
            key=lambda value: hashlib.sha256(
                f"{seed}|{key}|{dimension}|{cycle_index}|{value.casefold()}".encode(
                    "utf-8"
                )
            ).hexdigest(),
        )
        if result and len(ordered) > 1 and ordered[0].casefold() == result[-1].casefold():
            ordered = ordered[1:] + ordered[:1]
        result.extend(ordered)
        cycle_index += 1
    return result[:count]


def choose_range_factor_sequence(
    profile: dict[str, str],
    selected_ranges_json: str,
    count: int,
    seed: str,
) -> list[dict[str, str]]:
    from wardrobe_choice import (
        build_balanced_scattered_assignments,
        parse_selection_payload,
    )

    selected_ranges = parse_selection_payload(selected_ranges_json)
    errors = validate_range_pools_against_profile(
        profile,
        {str(item["key"]) for item in selected_ranges["colors"]},
        {str(item["key"]) for item in selected_ranges["styles"]},
    )
    if errors:
        raise ValueError("Invalid wardrobe range pools:\n- " + "\n- ".join(errors))
    range_pools = parse_range_pools(profile["wardrobe_range_pools_json"])
    effective_seed = seed or profile.get("_profile_sha256", "")
    assignments = build_balanced_scattered_assignments(
        selected_ranges,
        count,
        effective_seed,
    )
    color_totals = Counter(
        str(item["assigned_color_direction_key"]) for item in assignments
    )
    style_totals = Counter(
        str(item["assigned_style_family_key"]) for item in assignments
    )
    color_sequences = {
        key: deterministic_value_sequence(
            range_pools["colors"][key], total, effective_seed, key, "color"
        )
        for key, total in color_totals.items()
    }
    style_factor_sequences: dict[str, list[tuple[str, str]]] = {}
    for key, total in style_totals.items():
        style_pool = range_pools["styles"][key]
        factor_payload = {
            "colors": [
                {"key": value} for value in style_pool["silhouettes"]
            ],
            "styles": [
                {"key": value} for value in style_pool["substyles"]
            ],
        }
        factor_assignments = build_balanced_scattered_assignments(
            factor_payload,
            total,
            f"{effective_seed}|{key}|style-factors",
        )
        style_factor_sequences[key] = [
            (
                str(item["assigned_color_direction_key"]),
                str(item["assigned_style_family_key"]),
            )
            for item in factor_assignments
        ]
    color_offsets: Counter[str] = Counter()
    style_offsets: Counter[str] = Counter()
    factors: list[dict[str, str]] = []
    for assignment in assignments:
        color_key = str(assignment["assigned_color_direction_key"])
        style_key = str(assignment["assigned_style_family_key"])
        color_offset = color_offsets[color_key]
        style_offset = style_offsets[style_key]
        silhouette, substyle = style_factor_sequences[style_key][style_offset]
        factors.append(
            {
                "outfit_color": color_sequences[color_key][color_offset],
                "outfit_silhouette": silhouette,
                "outfit_style": substyle,
                "assigned_color_direction_key": color_key,
                "assigned_style_family_key": style_key,
            }
        )
        color_offsets[color_key] += 1
        style_offsets[style_key] += 1
    return factors


def suggest(
    profile: dict[str, str],
    mode: str,
    seed: str | None,
    count: int,
    persona_override: str | None = None,
    selected_ranges_json: str | None = None,
    assignment_seed: str | None = None,
) -> dict[str, object]:
    if count < 1:
        raise ValueError("--count must be at least 1")
    if mode not in ADAPTATION_MODES:
        raise ValueError(f"Unsupported adaptation mode {mode!r}")
    effective_seed = seed or ""
    output_seed = effective_seed
    persona = persona_override or profile["recommended_persona"]
    if mode == "recommend" and persona != profile["recommended_persona"]:
        raise ValueError("recommend mode must use the profile's recommended_persona")
    if selected_ranges_json:
        output_seed = (
            assignment_seed
            or effective_seed
            or profile.get("_profile_sha256", "")
        )
        planned_factors = choose_range_factor_sequence(
            profile,
            selected_ranges_json,
            count,
            output_seed,
        )
    else:
        planned_factors = [
            {
                "outfit_color": color,
                "outfit_silhouette": silhouette,
                "outfit_style": style,
                "assigned_color_direction_key": "",
                "assigned_style_family_key": "",
            }
            for color, silhouette, style in choose_factor_sequence(
                profile, count, effective_seed
            )
        ]
    outfits: list[dict[str, object]] = []
    factor_occurrences: dict[tuple[str, str, str], int] = {}
    for index, factor in enumerate(planned_factors, start=1):
        color = factor["outfit_color"]
        silhouette = factor["outfit_silhouette"]
        style = factor["outfit_style"]
        if profile["wardrobe_policy"] == "none":
            description = "not-applicable"
        elif profile["wardrobe_policy"] == "fixed":
            description = profile["signature_outfit"]
        elif profile["wardrobe_policy"] == "signature-variants":
            description = "; ".join(
                [profile["signature_outfit"], color, silhouette, style]
            )
        else:
            description = "; ".join([color, silhouette, style])
        if profile["wardrobe_policy"] in {"varied", "signature-variants"}:
            factor_key = (color, silhouette, style)
            occurrence = factor_occurrences.get(factor_key, 0)
            factor_occurrences[factor_key] = occurrence + 1
            if occurrence:
                if occurrence <= len(OUTFIT_DETAIL_VARIANTS):
                    detail = OUTFIT_DETAIL_VARIANTS[occurrence - 1]
                else:
                    detail = f"tailored variation {occurrence + 1:03d}"
                description = f"{description}; {detail}"
        outfits.append(
            {
                "index": index,
                "outfit": description,
                "outfit_color": color,
                "outfit_silhouette": silhouette,
                "outfit_style": style,
                "assigned_color_direction_key": factor[
                    "assigned_color_direction_key"
                ],
                "assigned_style_family_key": factor[
                    "assigned_style_family_key"
                ],
            }
        )
    return {
        "character_id": profile["character_id"],
        "profile_version": profile["profile_version"],
        "character_profile_sha256": profile["_profile_sha256"],
        "adaptation_mode": mode,
        "adaptation_seed": output_seed,
        "persona": persona,
        "wardrobe_policy": profile["wardrobe_policy"],
        "wardrobe_selection_schema_version": "2" if selected_ranges_json else "1",
        "wardrobe_selected_ranges_json": selected_ranges_json or "",
        "outfits": outfits,
    }


def main() -> int:
    args = parse_args()
    profiles, errors = load_profiles(args.profile_csv)
    if args.command == "validate":
        if args.photo_pool:
            errors.extend(validate_photo_pool(profiles, args.photo_pool))
        if args.manifest:
            errors.extend(validate_manifest_profiles(profiles, args.manifest))
        if errors:
            raise RuntimeError("Character profile validation failed:\n- " + "\n- ".join(errors))
        print(
            json.dumps(
                {
                    "status": "passed",
                    "profiles": [
                        {
                            "character_id": row["character_id"],
                            "profile_version": row["profile_version"],
                            "character_profile_sha256": row["_profile_sha256"],
                        }
                        for row in profiles.values()
                    ],
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    if errors:
        raise RuntimeError("Character profile validation failed:\n- " + "\n- ".join(errors))
    profile = profiles.get(args.character_id)
    if profile is None:
        raise ValueError(f"Unknown character_id {args.character_id!r}")
    print(
        json.dumps(
            suggest(
                profile,
                args.mode,
                args.seed,
                args.count,
                args.persona,
                args.selected_ranges_json,
                args.assignment_seed,
            ),
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
