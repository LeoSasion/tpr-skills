#!/usr/bin/env python3
"""Verify work packets exactly match the current manifest and character profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from batch_common import read_manifest, select_rows, sha256_file
from build_work_packets import build_packet, packet_output_path
from character_profile import load_profiles, validate_manifest_profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--character-profile", type=Path, required=True)
    parser.add_argument("--packets-dir", type=Path, required=True)
    parser.add_argument("--id", dest="identifiers", action="append", default=[])
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    return parser.parse_args()


def packet_errors(
    actual: dict[str, object], expected: dict[str, object], identifier: str
) -> list[str]:
    if actual == expected:
        return []
    errors: list[str] = []
    actual_keys = set(actual)
    expected_keys = set(expected)
    if actual_keys != expected_keys:
        errors.append(
            f"{identifier}: packet fields differ; missing "
            f"{sorted(expected_keys - actual_keys)}, extra "
            f"{sorted(actual_keys - expected_keys)}"
        )
    for key in sorted(actual_keys.intersection(expected_keys)):
        if actual[key] != expected[key]:
            errors.append(f"{identifier}: packet field {key!r} was modified")
    return errors


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

    for row in rows:
        identifier = row["number"]
        profile = profiles[row["character_id"]]
        reference = Path(row.get("reference_photo", ""))
        if not reference.is_absolute():
            reference = args.manifest.parent / reference
        reference = reference.resolve()
        if not reference.is_file():
            errors.append(f"{identifier}: reference is missing: {reference}")
            continue
        if row.get("reference_sha256", "") != sha256_file(reference):
            errors.append(f"{identifier}: reference SHA-256 does not match manifest")
            continue
        path = packet_output_path(args.packets_dir, identifier)
        if not path.is_file():
            errors.append(f"{identifier}: work packet is missing: {path}")
            continue
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{identifier}: work packet is unreadable: {exc}")
            continue
        if not isinstance(actual, dict):
            errors.append(f"{identifier}: work packet root must be a JSON object")
            continue
        expected = build_packet(row, profile, reference_path=str(reference))
        errors.extend(packet_errors(actual, expected, identifier))

    if errors:
        print("WORK PACKET CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"WORK PACKET CHECK PASSED: {len(rows)} immutable packet(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
