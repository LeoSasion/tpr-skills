#!/usr/bin/env python3
"""Verify final adaptive TPR cards and one or more delivery ZIPs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image, ImageChops

from batch_common import (
    expected_card_map,
    read_manifest,
    select_rows,
    sha256_file,
    validate_execution_background_rows,
    validate_generation_backend_rows,
    validate_wardrobe_provenance,
)
from character_profile import (
    SUITABILITY_HANDLINGS,
    load_profiles,
    validate_manifest_profiles,
)
from compose_a4_card import (
    CAPTION_HEIGHT,
    CAPTION_LAYOUT_VERSION,
    FONT_PATH,
    HEIGHT,
    IMAGE_BOTTOM,
    WIDTH,
    file_sha256,
    pixel_sha256,
    render_caption_strip,
)
from wardrobe_choice import (
    DEFAULT_LIBRARY as DEFAULT_WARDROBE_LIBRARY,
    load_library as load_wardrobe_library,
    validate_model_curated_binding,
)


LEGACY_NUMBER_RE = re.compile(r"^(\d+)_.*_A4\.png$", re.IGNORECASE)
QA_PASS_VALUES = {"pass", "passed"}
WARDROBE_LIBRARY = load_wardrobe_library(DEFAULT_WARDROBE_LIBRARY)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards_dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--character-profile", type=Path)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--id", dest="identifiers", action="append", default=[])
    parser.add_argument("--zip", dest="zip_paths", action="append", type=Path, default=[])
    parser.add_argument("--report", type=Path)
    parser.add_argument("--allow-unselected", action="store_true")
    parser.add_argument("--allow-unapproved", action="store_true")
    parser.add_argument("--allow-legacy-caption-check", action="store_true")
    return parser.parse_args()


def legacy_specs(cards_dir: Path, start: int | None, end: int | None):
    if start is None or end is None:
        raise ValueError("Without --manifest, --start and --end are required")
    found: dict[int, Path] = {}
    for path in cards_dir.glob("*.png"):
        match = LEGACY_NUMBER_RE.match(path.name)
        if not match:
            raise ValueError(f"Unrecognized PNG in strict legacy directory: {path.name}")
        value = int(match.group(1))
        if value in found:
            raise ValueError(f"Duplicate numeric card {value}: {found[value].name}, {path.name}")
        found[value] = path
    expected = set(range(start, end + 1))
    if set(found) != expected:
        raise ValueError(
            f"Number range mismatch; missing={sorted(expected - set(found))}, "
            f"extra={sorted(set(found) - expected)}"
        )
    return {
        found[value].name: (
            found[value],
            {
                "number": match.group(1) if (match := LEGACY_NUMBER_RE.match(found[value].name)) else str(value),
                "english": "",
                "chinese": "",
                "output_sha256": "",
            },
        )
        for value in range(start, end + 1)
    }


def verify_manifest_gate(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not row.get("character_id"):
        errors.append("character_id is empty")
    if not row.get("character_profile_version"):
        errors.append("character_profile_version is empty")
    if len(row.get("character_profile_sha256", "")) != 64:
        errors.append("character_profile_sha256 is invalid")
    if row.get("adaptation_mode") not in {"recommend", "specified"}:
        errors.append("adaptation_mode is invalid")
    if not row.get("persona"):
        errors.append("persona is empty")
    if row.get("wardrobe_policy") not in {
        "varied",
        "signature-variants",
        "fixed",
        "none",
    }:
        errors.append("wardrobe_policy is invalid")
    if row.get("suitability_handling") not in SUITABILITY_HANDLINGS:
        errors.append("suitability_handling is invalid")
    if row.get("adaptation_status") not in {"pass", "fallback"}:
        errors.append("character adaptation is not pass or fallback")
    if row.get("workflow_state", "") not in {"qa_passed", "packaged", "delivered"}:
        errors.append(f"workflow_state is {row.get('workflow_state', '')!r}, not qa_passed or later")
    if row.get("qa_auto_status", "").casefold() not in QA_PASS_VALUES:
        errors.append("qa_auto_status is not pass")
    if row.get("qa_visual_status", "").casefold() not in QA_PASS_VALUES:
        errors.append("qa_visual_status is not pass")
    if row.get("qa_status", "").casefold() not in QA_PASS_VALUES:
        errors.append("qa_status is not pass")
    if row.get("diversity_plan_status", "").casefold() not in QA_PASS_VALUES:
        errors.append("diversity_plan_status is not pass")
    if row.get("diversity_visual_status", "").casefold() not in QA_PASS_VALUES:
        errors.append("diversity_visual_status is not pass")
    errors.extend(validate_wardrobe_provenance(row))
    errors.extend(validate_model_curated_binding(row, WARDROBE_LIBRARY))
    errors.extend(validate_execution_background_rows([row]))
    errors.extend(validate_generation_backend_rows([row]))
    return errors


def verify_manifest_profile_binding(
    manifest: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    character_profile: Path | None,
) -> list[str]:
    """Bind adaptive manifest rows to the exact approved profile used for planning."""
    if "character_id" not in fieldnames:
        return []
    profile_path = character_profile or manifest.with_name("character_profile.csv")
    if not profile_path.is_file():
        return [
            "Adaptive manifest requires an approved character profile; pass "
            "--character-profile or place character_profile.csv beside the manifest"
        ]
    profiles, errors = load_profiles(profile_path)
    errors.extend(
        validate_manifest_profiles(
            profiles,
            manifest,
            selected_rows=rows,
            wardrobe_library=WARDROBE_LIBRARY,
        )
    )
    errors.extend(validate_execution_background_rows(rows))
    errors.extend(validate_generation_backend_rows(rows))
    character_ids = {row.get("character_id", "") for row in rows}
    if len(character_ids) != 1:
        errors.append(
            f"Selected delivery rows must use one primary character; found {sorted(character_ids)}"
        )
    return errors


def verify_card(
    path: Path,
    row: dict[str, str],
    *,
    allow_legacy_caption_check: bool,
) -> list[str]:
    errors: list[str] = []
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                errors.append(f"format is {image.format}, not PNG")
            image.load()
            if image.size != (WIDTH, HEIGHT):
                errors.append(f"wrong size {image.size}")
            dpi = image.info.get("dpi")
            if dpi is None or any(abs(float(value) - 150) > 1 for value in dpi[:2]):
                errors.append(f"wrong or missing DPI {dpi}")

            identifier = row.get("number", "")
            english = row.get("english", "")
            chinese = row.get("chinese", "")
            if english and image.info.get("English") != english:
                errors.append("English metadata does not exactly match manifest")
            if chinese and image.info.get("Chinese") != chinese:
                errors.append("Chinese metadata does not exactly match manifest")
            if identifier and image.info.get("Identifier") != identifier:
                errors.append("Identifier metadata does not exactly match manifest")
            if image.info.get("CaptionEmbedded") != "true":
                errors.append("CaptionEmbedded metadata is missing")

            caption = image.convert("RGB").crop((0, IMAGE_BOTTOM, WIDTH, HEIGHT))
            white = Image.new("RGB", (WIDTH, CAPTION_HEIGHT), "white")
            if ImageChops.difference(caption, white).getbbox() is None:
                errors.append("caption region contains no visible ink")

            version = image.info.get("CompositorVersion")
            if version != str(CAPTION_LAYOUT_VERSION):
                if not allow_legacy_caption_check:
                    errors.append(
                        f"CompositorVersion is {version!r}; exact visible-caption verification requires "
                        f"version {CAPTION_LAYOUT_VERSION}"
                    )
            elif identifier and english and chinese:
                try:
                    stored_layout = json.loads(image.info.get("CaptionLayout", ""))
                    requested_en = int(stored_layout["requested_english_size"])
                    requested_zh = int(stored_layout["requested_chinese_size"])
                    minimum = int(stored_layout["min_font_size"])
                    max_lines = int(stored_layout["max_lines"])
                    expected_caption, expected_layout = render_caption_strip(
                        identifier,
                        english,
                        chinese,
                        FONT_PATH,
                        requested_en,
                        requested_zh,
                        minimum,
                        max_lines,
                    )
                    if stored_layout != expected_layout:
                        errors.append("stored caption layout does not match deterministic layout")
                    if ImageChops.difference(caption, expected_caption).getbbox() is not None:
                        errors.append("visible identifier or caption pixels do not match manifest")
                    if image.info.get("CaptionPixelSHA256") != pixel_sha256(caption):
                        errors.append("CaptionPixelSHA256 does not match visible caption pixels")
                    if image.info.get("FontSHA256") != file_sha256(FONT_PATH):
                        errors.append("FontSHA256 does not match bundled approved font")
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"invalid CaptionLayout metadata: {exc}")
    except Exception as exc:
        errors.append(f"cannot fully decode PNG: {exc}")

    expected_hash = row.get("output_sha256", "").strip()
    if expected_hash and path.is_file() and sha256_file(path) != expected_hash:
        errors.append("file SHA-256 does not match manifest output_sha256")
    return errors


def unsafe_archive_member(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return True
    pure = PurePosixPath(name)
    return pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1


def verify_zip_set(
    zip_paths: list[Path],
    expected: dict[str, tuple[Path, dict[str, str]]],
) -> list[str]:
    errors: list[str] = []
    expected_names = set(expected)
    manifest_order = {name: index for index, name in enumerate(expected)}
    seen_in: dict[str, str] = {}

    for zip_path in zip_paths:
        try:
            with zipfile.ZipFile(zip_path) as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                if not names:
                    errors.append(f"{zip_path.name}: archive is empty")
                    continue
                if len(names) != len(set(names)):
                    errors.append(f"{zip_path.name}: archive contains duplicate member names")
                casefolded = [name.casefold() for name in names]
                if len(casefolded) != len(set(casefolded)):
                    errors.append(f"{zip_path.name}: archive contains case-insensitive name collisions")
                for name in names:
                    if unsafe_archive_member(name):
                        errors.append(f"{zip_path.name}: unsafe or nested member {name!r}")
                    if not name.lower().endswith(".png"):
                        errors.append(f"{zip_path.name}: non-PNG member {name!r}")
                member_set = set(names)
                unexpected = sorted(member_set - expected_names)
                if unexpected:
                    errors.append(f"{zip_path.name}: unexpected members {unexpected}")
                valid_names = [name for name in names if name in expected_names]
                ordered_indices = [manifest_order[name] for name in valid_names]
                indices = sorted(set(ordered_indices))
                if ordered_indices != indices:
                    errors.append(f"{zip_path.name}: members are not in manifest order")
                if indices and indices != list(range(indices[0], indices[-1] + 1)):
                    errors.append(f"{zip_path.name}: members are not one contiguous manifest segment")
                if valid_names:
                    first = expected[valid_names[0]][1]["number"]
                    last = expected[valid_names[-1]][1]["number"]
                    if f"{first}-{last}" not in zip_path.stem:
                        errors.append(
                            f"{zip_path.name}: filename does not contain inclusive range {first}-{last}"
                        )
                for name in valid_names:
                    if name in seen_in:
                        errors.append(
                            f"{name}: appears in both {seen_in[name]} and {zip_path.name}"
                        )
                    else:
                        seen_in[name] = zip_path.name
                    digest = hashlib.sha256(archive.read(name)).hexdigest()
                    if digest != sha256_file(expected[name][0]):
                        errors.append(f"{zip_path.name}: member {name} differs from verified source PNG")
                corrupt = archive.testzip()
                if corrupt:
                    errors.append(f"{zip_path.name}: corrupt member {corrupt}")
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            errors.append(f"{zip_path.name}: cannot verify ZIP: {exc}")

    missing = sorted(expected_names - set(seen_in))
    if missing:
        errors.append(f"ZIP set is missing verified PNGs: {missing}")
    return errors


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    card_results: list[dict[str, object]] = []

    try:
        if args.manifest:
            fieldnames, all_rows = read_manifest(args.manifest)
            rows = select_rows(
                all_rows,
                start=args.start,
                end=args.end,
                identifiers=args.identifiers,
            )
            if not args.allow_unapproved:
                failures.extend(
                    verify_manifest_profile_binding(
                        args.manifest,
                        fieldnames,
                        rows,
                        args.character_profile,
                    )
                )
            expected = expected_card_map(args.cards_dir, rows)
        else:
            if args.identifiers:
                raise ValueError("--id requires --manifest")
            expected = legacy_specs(args.cards_dir, args.start, args.end)
            rows = [item[1] for item in expected.values()]

        for name, (path, row) in expected.items():
            if not path.is_file():
                failures.append(f"{name}: expected PNG is missing")
                continue
            if args.manifest and not args.allow_unapproved:
                for error in verify_manifest_gate(row):
                    failures.append(f"{row['number']}: {error}")
            errors = verify_card(
                path,
                row,
                allow_legacy_caption_check=args.allow_legacy_caption_check,
            )
            card_results.append(
                {"identifier": row.get("number", ""), "filename": name, "errors": errors}
            )
            failures.extend(f"{name}: {error}" for error in errors)

        if not args.allow_unselected:
            actual_names = {path.name for path in args.cards_dir.glob("*.png")}
            expected_names = set(expected)
            missing = sorted(expected_names - actual_names)
            extra = sorted(actual_names - expected_names)
            if missing or extra:
                failures.append(f"PNG set mismatch; missing={missing}, extra={extra}")

        if args.zip_paths:
            failures.extend(verify_zip_set(args.zip_paths, expected))
    except (OSError, ValueError) as exc:
        failures.append(str(exc))

    report = {
        "status": "failed" if failures else "passed",
        "card_count": len(card_results),
        "cards": card_results,
        "zip_files": [str(path) for path in args.zip_paths],
        "failures": failures,
    }
    if args.report:
        write_report(args.report, report)

    if failures:
        print("DELIVERY CHECK FAILED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"DELIVERY CHECK PASSED: {len(card_results)} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
