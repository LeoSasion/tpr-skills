#!/usr/bin/env python3
"""Create deterministic range ZIPs from verified final adaptive card PNGs."""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path

from batch_common import (
    expected_card_map,
    read_manifest,
    require_delivery_choice,
    select_rows,
    sha256_file,
)
from verify_delivery import (
    verify_card,
    verify_manifest_gate,
    verify_manifest_profile_binding,
    verify_zip_set,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--character-profile", type=Path)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--id", dest="identifiers", action="append", default=[])
    parser.add_argument("--part-size", type=int, default=25)
    parser.add_argument("--prefix", default="Adaptive_TPR_cards")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def archive_name(prefix: str, first: str, last: str) -> str:
    safe_prefix = prefix.strip().replace("/", "-").replace("\\", "-")
    if not safe_prefix:
        raise ValueError("--prefix must not be empty")
    return f"{safe_prefix}_{first}-{last}.zip"


def write_archive(path: Path, card_paths: list[Path], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Archive already exists; use --overwrite to replace it: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for card_path in card_paths:
                info = zipfile.ZipInfo(card_path.name, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, card_path.read_bytes())
        with zipfile.ZipFile(temporary) as check:
            corrupt = check.testzip()
            if corrupt:
                raise RuntimeError(f"Temporary archive has corrupt member {corrupt}")
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    args = parse_args()
    if args.part_size < 1:
        raise ValueError("--part-size must be at least 1")

    fieldnames, all_rows = read_manifest(args.manifest)
    rows = select_rows(
        all_rows,
        start=args.start,
        end=args.end,
        identifiers=args.identifiers,
    )
    require_delivery_choice(rows, "zip")
    expected = expected_card_map(args.cards_dir, rows)
    actual_names = {path.name for path in args.cards_dir.glob("*.png")}
    if actual_names != set(expected):
        raise RuntimeError(
            f"PNG set mismatch; missing={sorted(set(expected) - actual_names)}, "
            f"extra={sorted(actual_names - set(expected))}"
        )

    failures = verify_manifest_profile_binding(
        args.manifest,
        fieldnames,
        rows,
        args.character_profile,
    )
    for name, (path, row) in expected.items():
        if not path.is_file():
            failures.append(f"{name}: expected PNG is missing")
            continue
        failures.extend(f"{row['number']}: {error}" for error in verify_manifest_gate(row))
        failures.extend(
            f"{name}: {error}"
            for error in verify_card(path, row, allow_legacy_caption_check=False)
        )
    if failures:
        raise RuntimeError("Cards are not ready for packaging:\n- " + "\n- ".join(failures))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ordered = list(expected.values())
    archives: list[Path] = []
    for offset in range(0, len(ordered), args.part_size):
        part = ordered[offset : offset + args.part_size]
        first = part[0][1]["number"]
        last = part[-1][1]["number"]
        target = args.output_dir / archive_name(args.prefix, first, last)
        write_archive(target, [item[0] for item in part], args.overwrite)
        archives.append(target)

    zip_errors = verify_zip_set(archives, expected)
    if zip_errors:
        raise RuntimeError("ZIP verification failed:\n- " + "\n- ".join(zip_errors))

    print(
        json.dumps(
            {
                "archives": [
                    {"path": str(path.resolve()), "sha256": sha256_file(path)}
                    for path in archives
                ],
                "card_count": len(ordered),
                "part_size": args.part_size,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
