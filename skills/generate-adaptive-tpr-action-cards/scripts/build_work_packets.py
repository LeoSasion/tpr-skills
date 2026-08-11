#!/usr/bin/env python3
"""Build validated immutable per-row image-generation work packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from batch_common import (
    WARDROBE_V2_ASSIGNMENT_FIELDS,
    WARDROBE_V2_BATCH_FIELDS,
    read_manifest,
    select_rows,
    sha256_file,
    validate_wardrobe_assignment_key,
)
from character_profile import load_profiles, split_values, validate_manifest_profiles
from wardrobe_choice import resolve_age_domain


PACKET_SCHEMA_VERSION = "2026.08.3"
SAFE_PACKET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--character-profile", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--id", dest="identifiers", action="append", default=[])
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    return parser.parse_args()


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def packet_output_path(output_dir: Path, identifier: str) -> Path:
    """Return a contained packet path for one strict manifest identifier."""
    if not SAFE_PACKET_ID_RE.fullmatch(identifier) or identifier in {".", ".."}:
        raise ValueError(
            f"Unsafe work-packet identifier {identifier!r}; use only letters, "
            "digits, dot, underscore, or hyphen and start with a letter or digit"
        )
    resolved_dir = output_dir.resolve()
    output = (resolved_dir / f"{identifier}.json").resolve()
    if not output.is_relative_to(resolved_dir):
        raise ValueError(f"Work-packet output escapes --output-dir: {output}")
    return output


def build_packet(
    row: dict[str, str],
    profile: dict[str, str],
    *,
    reference_path: str,
) -> dict[str, object]:
    """Build one prompt only from current validated structured inputs."""
    identifier = row.get("number", "?")
    selection_schema_version = row.get(
        "wardrobe_selection_schema_version", ""
    ).strip()
    v2_active = any(
        row.get(field, "")
        for field in (*WARDROBE_V2_BATCH_FIELDS, *WARDROBE_V2_ASSIGNMENT_FIELDS)
    )
    assigned_color_key = row.get("assigned_color_direction_key", "").strip()
    assigned_style_key = row.get("assigned_style_family_key", "").strip()
    if not v2_active:
        assigned_color_key = assigned_color_key or row.get(
            "color_direction_id", ""
        ).strip()
        assigned_style_key = assigned_style_key or row.get(
            "style_family_id", ""
        ).strip()

    assignment_errors: list[str] = []
    for field, value in (
        ("assigned_color_direction_key", assigned_color_key),
        ("assigned_style_family_key", assigned_style_key),
    ):
        assignment_errors.extend(
            validate_wardrobe_assignment_key(
                value,
                field=field,
                identifier=identifier,
                required=v2_active,
            )
        )
    if v2_active and selection_schema_version != "2":
        assignment_errors.append(
            f"{identifier}: wardrobe_selection_schema_version must be 2"
        )
    if assignment_errors:
        raise ValueError(
            "Invalid wardrobe range assignment:\n- "
            + "\n- ".join(assignment_errors)
        )

    age_domain = resolve_age_domain(profile)
    if age_domain == "adult":
        wardrobe_safety_scope = "adult-none"
        # Keep the adult scope as structured audit metadata only. Explicit
        # no-restriction prose adds no visual value and can itself trip a
        # backend classifier. The absence of a minor-only rule is sufficient.
        wardrobe_rule = ""
        minor_safety_notes: list[str] = []
        minor_avoid_features: list[str] = []
    else:
        wardrobe_safety_scope = "minor-nonsexualized"
        wardrobe_rule = (
            "Minor wardrobe safety scope: minor-nonsexualized. Keep the child "
            "or age-uncertain subject age-appropriate and nonsexualized, and "
            "do not use lingerie-inspired or revealing sexualized styling."
        )
        minor_safety_notes = split_values(profile.get("action_safety_notes", ""))
        minor_avoid_features = split_values(profile.get("avoid_outfit_features", ""))

    action_parts = [
        row.get("body_action", "").strip(),
        f"Key joints: {row.get('key_joints', '').strip()}.",
        f"Weight shift: {row.get('weight_shift', '').strip()}.",
        f"Head angle: {row.get('head_angle', '').strip()}.",
        f"Gaze: {row.get('gaze', '').strip()}.",
        f"Expression: {row.get('expression', '').strip()}.",
    ]
    action_instruction = " ".join(part for part in action_parts if part)
    outfit = row.get("outfit", "").strip()
    background_mode = row.get("background_mode", "").strip().casefold()
    background = row.get("background_treatment", "").strip()
    identity = profile.get("identity_anchors", "").strip()
    proportions = profile.get("proportion_summary", "").strip()
    signature = profile.get("signature_outfit", "").strip()

    prompt_parts = [
        "Use only the supplied approved original as the identity reference.",
        f"Preserve identity anchors: {identity}.",
        f"Preserve proportions: {proportions}.",
        f"Render one readable full-body TPR action: {action_instruction}",
        f"Approved outfit: {outfit}.",
    ]
    if signature and signature.casefold() != "not-applicable":
        prompt_parts.append(f"Preserve signature outfit elements: {signature}.")
    if wardrobe_rule:
        prompt_parts.append(wardrobe_rule)
    if background:
        if background_mode == "pure-white":
            prompt_parts.append("Background: pure white.")
        elif background_mode in {"specified", "auto-varied"}:
            prompt_parts.append(f"Background: {background}.")
    prompt_parts.append(
        "Keep the full body and action-critical limbs visible. Leave clear "
        "bottom space for later captions. Do not render captions, identifiers, "
        "logos, borders, unrelated people, or watermarks."
    )
    if minor_safety_notes:
        prompt_parts.append(
            "Minor action-safety notes: " + "; ".join(minor_safety_notes) + "."
        )
    if minor_avoid_features:
        prompt_parts.append(
            "Minor avoid features: " + "; ".join(minor_avoid_features) + "."
        )
    prompt = "\n\n".join(prompt_parts)

    packet: dict[str, object] = {
        "packet_schema_version": PACKET_SCHEMA_VERSION,
        "number": row.get("number", ""),
        "character_id": row.get("character_id", ""),
        "character_profile_version": row.get("character_profile_version", ""),
        "character_profile_sha256": row.get("character_profile_sha256", ""),
        "reference_path": reference_path,
        "reference_sha256": row.get("reference_sha256", ""),
        "raw_output_path": row.get("raw_output_path", ""),
        "generation_version": row.get("generation_version", "1") or "1",
        "generation_interface": row.get("generation_interface", ""),
        "generation_model": row.get("generation_model", ""),
        "age_domain": age_domain,
        "wardrobe_safety_scope": wardrobe_safety_scope,
        "wardrobe_selection_schema_version": selection_schema_version or "1",
        "wardrobe_assignment_strategy": row.get(
            "wardrobe_assignment_strategy", ""
        ),
        "assigned_color_direction_key": assigned_color_key,
        "assigned_style_family_key": assigned_style_key,
        "minor_safety_notes": minor_safety_notes,
        "minor_avoid_features": minor_avoid_features,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256(prompt),
    }
    return packet


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    args = parse_args()
    _, all_rows = read_manifest(args.manifest)
    rows = select_rows(
        all_rows,
        start=args.start,
        end=args.end,
        identifiers=args.identifiers,
    )
    profiles, errors = load_profiles(args.character_profile)
    if errors:
        raise RuntimeError("Character profile validation failed:\n- " + "\n- ".join(errors))
    errors = validate_manifest_profiles(
        profiles,
        args.manifest,
        selected_rows=rows,
    )
    if errors:
        raise RuntimeError("Work-packet binding failed:\n- " + "\n- ".join(errors))

    written: list[str] = []
    for row in rows:
        profile = profiles[row["character_id"]]
        reference = Path(row.get("reference_photo", ""))
        if not reference.is_absolute():
            reference = args.manifest.parent / reference
        reference = reference.resolve()
        if not reference.is_file():
            raise FileNotFoundError(f"{row['number']}: reference is missing: {reference}")
        if row.get("reference_sha256", "") != sha256_file(reference):
            raise ValueError(f"{row['number']}: reference SHA-256 does not match manifest")
        packet = build_packet(row, profile, reference_path=str(reference))
        output = packet_output_path(args.output_dir, row["number"])
        atomic_write_json(output, packet)
        written.append(str(output))

    print(
        json.dumps(
            {
                "status": "passed",
                "packet_schema_version": PACKET_SCHEMA_VERSION,
                "count": len(written),
                "paths": written,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
