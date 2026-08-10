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
    read_manifest,
    validate_wardrobe_provenance,
)


PROFILE_FIELDS = [
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
    suggest.add_argument("--persona")
    suggest.add_argument("--count", type=int, required=True)
    return parser.parse_args()


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


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
    canonical = {field: row.get(field, "") for field in PROFILE_FIELDS}
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
    return errors


def load_profiles(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    errors: list[str] = []
    profiles: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != PROFILE_FIELDS:
            raise ValueError(f"Character profile must contain exactly these fields: {PROFILE_FIELDS}")
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


def validate_manifest_profiles(
    profiles: dict[str, dict[str, str]],
    manifest: Path,
    selected_rows: list[dict[str, str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    fieldnames, all_rows = read_manifest(manifest)
    rows = all_rows if selected_rows is None else selected_rows
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
                return (
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
    profile: dict[str, str], count: int
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
        cycle = build_diverse_sequence(
            combinations,
            len(combinations),
            require_cycle_boundary=True,
        )
        return [cycle[index % len(cycle)] for index in range(count)]
    return build_diverse_sequence(
        combinations,
        count,
        require_cycle_boundary=False,
    )


def suggest(
    profile: dict[str, str],
    mode: str,
    seed: str | None,
    count: int,
    persona_override: str | None = None,
) -> dict[str, object]:
    if count < 1:
        raise ValueError("--count must be at least 1")
    if mode not in ADAPTATION_MODES:
        raise ValueError(f"Unsupported adaptation mode {mode!r}")
    effective_seed = seed or ""
    persona = persona_override or profile["recommended_persona"]
    if mode == "recommend" and persona != profile["recommended_persona"]:
        raise ValueError("recommend mode must use the profile's recommended_persona")
    factors = choose_factor_sequence(profile, count)
    outfits: list[dict[str, object]] = []
    factor_occurrences: dict[tuple[str, str, str], int] = {}
    for index, (color, silhouette, style) in enumerate(factors, start=1):
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
            }
        )
    return {
        "character_id": profile["character_id"],
        "profile_version": profile["profile_version"],
        "character_profile_sha256": profile["_profile_sha256"],
        "adaptation_mode": mode,
        "adaptation_seed": effective_seed,
        "persona": persona,
        "wardrobe_policy": profile["wardrobe_policy"],
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
            suggest(profile, args.mode, args.seed, args.count, args.persona),
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
