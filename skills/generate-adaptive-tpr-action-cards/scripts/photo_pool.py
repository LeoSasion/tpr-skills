#!/usr/bin/env python3
"""Register and validate approved original-reference evidence by character."""

from __future__ import annotations

import argparse
import csv
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from batch_common import atomic_write_csv, read_manifest, sha256_file


FIELDS = [
    "photo_id",
    "character_id",
    "filename",
    "sha256",
    "source_kind",
    "status",
    "exclude_reason",
    "approved_at",
    "last_verified_at",
    "notes",
]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
STATUSES = {"pending", "approved", "excluded", "missing", "hash_changed"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan")
    scan.add_argument("photo_dir", type=Path)
    scan.add_argument("pool_csv", type=Path)
    scan.add_argument("--character-id", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("photo_dir", type=Path)
    validate.add_argument("pool_csv", type=Path)
    validate.add_argument("--manifest", type=Path)

    select = subparsers.add_parser("select")
    select.add_argument("photo_dir", type=Path)
    select.add_argument("pool_csv", type=Path)
    select.add_argument("--count", type=int, required=True)
    select.add_argument("--character-id", required=True)
    return parser.parse_args()


def read_pool(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) != set(FIELDS):
            raise ValueError(f"Photo pool must contain exactly these fields: {FIELDS}")
        return [{key: (value or "") for key, value in row.items()} for row in reader]


def decodable_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.load()
        return True
    except Exception:
        return False


def next_photo_id(rows: list[dict[str, str]]) -> str:
    values = []
    for row in rows:
        value = row.get("photo_id", "")
        if value.startswith("P") and value[1:].isdigit():
            values.append(int(value[1:]))
    return f"P{(max(values, default=0) + 1):03d}"


def scan_pool(photo_dir: Path, pool_csv: Path, character_id: str) -> list[dict[str, str]]:
    if not character_id.strip():
        raise ValueError("--character-id must not be empty")
    rows = read_pool(pool_csv)
    by_name = {row["filename"]: row for row in rows}
    by_hash = {row["sha256"]: row for row in rows if row.get("sha256")}
    seen: set[str] = set()
    timestamp = now_iso()

    for path in sorted(photo_dir.iterdir()):
        if not path.is_file() or path.suffix.casefold() not in IMAGE_EXTENSIONS:
            continue
        seen.add(path.name)
        if not decodable_image(path):
            continue
        digest = sha256_file(path)
        row = by_name.get(path.name)
        if row is None:
            prior = by_hash.get(digest)
            if prior and prior.get("status") == "excluded":
                status = "excluded"
                reason = f"same content as excluded photo {prior['filename']}"
            else:
                status = "pending"
                reason = "manual original-photo approval required"
            row = {
                "photo_id": next_photo_id(rows),
                "character_id": character_id,
                "filename": path.name,
                "sha256": digest,
                "source_kind": "unverified",
                "status": status,
                "exclude_reason": reason,
                "approved_at": "",
                "last_verified_at": timestamp,
                "notes": "",
            }
            rows.append(row)
            by_name[path.name] = row
            by_hash[digest] = row
        else:
            if row.get("character_id") != character_id:
                raise ValueError(
                    f"{path.name}: already belongs to character "
                    f"{row.get('character_id')!r}, not {character_id!r}"
                )
            old_digest = row.get("sha256", "")
            if old_digest and old_digest != digest and row.get("status") == "approved":
                row["status"] = "hash_changed"
                row["exclude_reason"] = "file content changed; re-approval required"
            row["sha256"] = digest
            row["last_verified_at"] = timestamp

    for row in rows:
        if row.get("character_id") != character_id:
            continue
        if row["filename"] not in seen and row.get("status") not in {"excluded", "missing"}:
            row["status"] = "missing"
            row["exclude_reason"] = "registered source file is missing"
            row["last_verified_at"] = timestamp

    atomic_write_csv(pool_csv, FIELDS, rows)
    return rows


def validate_pool(
    photo_dir: Path,
    rows: list[dict[str, str]],
    manifest_path: Path | None,
) -> list[str]:
    errors: list[str] = []
    filenames: set[str] = set()
    photo_ids: set[str] = set()
    approved_hashes: set[str] = set()
    by_name: dict[str, dict[str, str]] = {}

    for row in rows:
        name = row.get("filename", "")
        photo_id = row.get("photo_id", "")
        status = row.get("status", "")
        character_id = row.get("character_id", "")
        if not character_id:
            errors.append(f"{name}: character_id is empty")
        if name in filenames:
            errors.append(f"duplicate photo filename {name!r}")
        filenames.add(name)
        if photo_id in photo_ids:
            errors.append(f"duplicate photo_id {photo_id!r}")
        photo_ids.add(photo_id)
        if status not in STATUSES:
            errors.append(f"{name}: unknown status {status!r}")
        by_name[name] = row
        path = photo_dir / name
        if status == "approved":
            if row.get("source_kind") != "original":
                errors.append(f"{name}: approved source_kind is not original")
            if not path.is_file() or not decodable_image(path):
                errors.append(f"{name}: approved original is missing or corrupt")
            else:
                digest = sha256_file(path)
                if digest != row.get("sha256"):
                    errors.append(f"{name}: approved original hash changed")
                if digest in approved_hashes:
                    errors.append(f"{name}: duplicate approved photo content")
                approved_hashes.add(digest)

    if manifest_path:
        _, manifest_rows = read_manifest(manifest_path)
        for card in manifest_rows:
            filename = card.get("reference_photo", "")
            source = by_name.get(filename)
            if source is None:
                errors.append(f"{card['number']}: reference {filename!r} is not registered")
                continue
            if source.get("status") != "approved" or source.get("source_kind") != "original":
                errors.append(f"{card['number']}: reference {filename!r} is not an approved original")
            if source.get("character_id") != card.get("character_id"):
                errors.append(
                    f"{card['number']}: reference {filename!r} belongs to character "
                    f"{source.get('character_id')!r}, not {card.get('character_id')!r}"
                )
            expected_hash = card.get("reference_sha256", "")
            if not expected_hash or expected_hash != source.get("sha256"):
                errors.append(f"{card['number']}: reference_sha256 does not match photo pool")
    return errors


def main() -> int:
    args = parse_args()
    if args.command == "scan":
        rows = scan_pool(args.photo_dir, args.pool_csv, args.character_id)
        print(json.dumps({"registered": len(rows), "pool": str(args.pool_csv)}, ensure_ascii=False))
        return 0

    rows = read_pool(args.pool_csv)
    errors = validate_pool(
        args.photo_dir,
        rows,
        getattr(args, "manifest", None),
    )
    if errors:
        raise RuntimeError("Photo pool validation failed:\n- " + "\n- ".join(errors))

    if args.command == "validate":
        print(f"PHOTO POOL CHECK PASSED: {len(rows)} registered photos")
        return 0

    if args.count < 1:
        raise ValueError("--count must be at least 1")
    approved = [
        row
        for row in rows
        if row.get("status") == "approved"
        and row.get("source_kind") == "original"
        and row.get("character_id") == args.character_id
    ]
    if not approved:
        raise RuntimeError(
            f"No approved original references are available for character {args.character_id!r}"
        )
    choices = [secrets.choice(approved) for _ in range(args.count)]
    print(
        json.dumps(
            [
                {
                    "photo_id": row["photo_id"],
                    "character_id": row["character_id"],
                    "filename": row["filename"],
                    "sha256": row["sha256"],
                }
                for row in choices
            ],
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
