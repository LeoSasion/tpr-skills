#!/usr/bin/env python3
"""Advance, fail, retry, or reopen card workflow states atomically."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from batch_common import (
    atomic_write_csv,
    read_manifest,
    require_delivery_choice,
    select_rows,
    sha256_file,
)
from verify_delivery import verify_card


STATES = ["planned", "generated", "composed", "qa_passed", "packaged", "delivered"]
FAILURE_CODES = {
    "PROFILE_MISSING",
    "PROFILE_UNAPPROVED",
    "PROFILE_AMBIGUOUS",
    "PROFILE_REFERENCE_MISMATCH",
    "CHARACTER_ACTION_MISMATCH",
    "CHARACTER_CONSISTENCY",
    "WARDROBE_UNSAFE",
    "REF_MISSING",
    "REF_EXCLUDED",
    "REF_HASH_CHANGED",
    "SEMANTIC_MISSING",
    "SEMANTIC_AMBIGUOUS",
    "GEN_IDENTITY",
    "GEN_ACTION",
    "GEN_ANATOMY",
    "GEN_COMPOSITION",
    "GEN_UNWANTED_ELEMENT",
    "COMP_SIZE_DPI",
    "COMP_CAPTION",
    "COMP_METADATA",
    "DIV_HEAD_GAZE",
    "DIV_EXPRESSION",
    "DIV_OUTFIT",
    "PKG_CONTENT",
    "PKG_INTEGRITY",
    "WORD_LAYOUT",
    "DELIVERY_UNCONFIRMED",
}
REQUIRED_FIELDS = {
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
    "workflow_state",
    "attempt_count",
    "composition_attempt_count",
    "package_attempt_count",
    "generation_version",
    "raw_output_path",
    "raw_sha256",
    "output_sha256",
    "qa_auto_status",
    "qa_visual_status",
    "qa_status",
    "failure_codes",
    "failure_detail",
    "diversity_plan_status",
    "diversity_visual_status",
    "delivery_format",
    "word_identifier_visibility",
    "package_name",
    "package_sha256",
    "delivered_at",
    "updated_at",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--id", dest="identifiers", action="append", default=[])

    advance = subparsers.add_parser("advance")
    add_selection(advance)
    advance.add_argument("--to", choices=STATES[1:], required=True)
    advance.add_argument("--cards-dir", type=Path)
    advance.add_argument("--raw-dir", type=Path)
    advance.add_argument("--package", type=Path, action="append", default=[])
    advance.add_argument("--delivery-confirmed-sha", action="append", default=[])

    visual = subparsers.add_parser("visual")
    add_selection(visual)
    visual.add_argument("--result", choices=["pass", "fail"], required=True)
    visual.add_argument("--failure-code", choices=sorted(FAILURE_CODES))
    visual.add_argument("--detail", default="")
    visual.add_argument("--diversity-pass", action="store_true")

    fail = subparsers.add_parser("fail")
    add_selection(fail)
    fail.add_argument("--gate", choices=["auto", "visual"], required=True)
    fail.add_argument("--failure-code", choices=sorted(FAILURE_CODES), required=True)
    fail.add_argument("--detail", default="")

    retry = subparsers.add_parser("retry")
    add_selection(retry)
    retry.add_argument("--mode", choices=["regenerate", "recompose"], required=True)
    retry.add_argument("--reason", required=True)
    retry.add_argument("--override-limit", action="store_true")

    reopen = subparsers.add_parser("reopen")
    add_selection(reopen)
    reopen.add_argument("--reason", required=True)
    return parser.parse_args()


def add_selection(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", dest="identifiers", action="append")
    group.add_argument("--all", action="store_true")


def selected(rows: list[dict[str, str]], args) -> list[dict[str, str]]:
    identifiers = getattr(args, "identifiers", None) or []
    if getattr(args, "all", False):
        return rows
    return select_rows(rows, identifiers=identifiers)


def require_schema(fieldnames: list[str]) -> None:
    missing = sorted(REQUIRED_FIELDS - set(fieldnames))
    if missing:
        raise ValueError(f"Manifest is not the current workflow schema; missing {missing}")


def append_failure(row: dict[str, str], code: str, detail: str) -> None:
    codes = [value for value in row.get("failure_codes", "").split(";") if value]
    codes.append(code)
    row["failure_codes"] = ";".join(codes)
    if detail:
        entry = f"[{now_iso()}] {code}: {detail}"
        row["failure_detail"] = "\n".join(
            value for value in (row.get("failure_detail", ""), entry) if value
        )


def integer_field(row: dict[str, str], name: str, default: int = 0) -> int:
    try:
        return int(row.get(name, "") or default)
    except ValueError as exc:
        raise ValueError(f"{row['number']}: {name} is not an integer") from exc


def advance_row(row: dict[str, str], args) -> None:
    current = row.get("workflow_state", "") or "planned"
    if current not in STATES:
        raise ValueError(f"{row['number']}: unknown state {current!r}")
    expected_index = STATES.index(current) + 1
    if expected_index >= len(STATES) or STATES[expected_index] != args.to:
        raise ValueError(f"{row['number']}: cannot advance directly from {current} to {args.to}")

    if args.to == "generated":
        if row.get("adaptation_status") not in {"pass", "fallback"}:
            raise ValueError(f"{row['number']}: character adaptation has not passed planning")
        if row.get("diversity_plan_status") != "pass":
            raise ValueError(f"{row['number']}: batch plan validation has not passed")
        attempts = integer_field(row, "attempt_count") + 1
        if attempts > 3:
            raise ValueError(f"{row['number']}: generation attempt limit reached")
        raw_path_text = row.get("raw_output_path", "").strip()
        if not raw_path_text or args.raw_dir is None:
            raise ValueError(f"{row['number']}: raw_output_path and --raw-dir are required")
        raw_path = args.raw_dir / Path(raw_path_text).name
        if not raw_path.is_file():
            raise ValueError(f"{row['number']}: raw output is missing: {raw_path}")
        row["attempt_count"] = str(attempts)
        row["raw_sha256"] = sha256_file(raw_path)
        row["qa_status"] = "pending"

    elif args.to == "composed":
        attempts = integer_field(row, "composition_attempt_count") + 1
        if attempts > 2:
            raise ValueError(f"{row['number']}: composition attempt limit reached")
        if args.cards_dir is None:
            raise ValueError("--cards-dir is required when advancing to composed")
        output = args.cards_dir / Path(row.get("output_path", "")).name
        if not output.is_file():
            raise ValueError(f"{row['number']}: composed PNG is missing: {output}")
        errors = verify_card(output, row, allow_legacy_caption_check=False)
        if errors:
            raise ValueError(f"{row['number']}: composition gate failed: {errors}")
        row["output_sha256"] = sha256_file(output)
        row["composition_attempt_count"] = str(attempts)
        row["qa_auto_status"] = "pass"

    elif args.to == "qa_passed":
        if row.get("adaptation_status") not in {"pass", "fallback"}:
            raise ValueError(f"{row['number']}: character adaptation has not passed")
        if row.get("qa_auto_status") != "pass":
            raise ValueError(f"{row['number']}: automatic QA has not passed")
        if row.get("qa_visual_status") != "pass":
            raise ValueError(f"{row['number']}: visual QA has not passed")
        if row.get("diversity_plan_status") != "pass":
            raise ValueError(f"{row['number']}: plan diversity has not passed")
        if row.get("diversity_visual_status") != "pass":
            raise ValueError(f"{row['number']}: visual diversity has not passed")
        row["qa_status"] = "pass"

    elif args.to == "packaged":
        attempts = integer_field(row, "package_attempt_count") + 1
        if attempts > 2:
            raise ValueError(f"{row['number']}: packaging attempt limit reached")
        if not args.package or any(not path.is_file() for path in args.package):
            raise ValueError("Every --package must identify a verified package")
        choice = row.get("delivery_format", "").strip().casefold()
        suffixes = [path.suffix.casefold() for path in args.package]
        if choice == "zip":
            require_delivery_choice([row], "zip")
            if any(suffix != ".zip" for suffix in suffixes):
                raise ValueError(f"{row['number']}: ZIP was selected but a package is not a ZIP")
        elif choice == "word":
            require_delivery_choice([row], "word")
            if suffixes != [".docx"]:
                raise ValueError(f"{row['number']}: Word requires exactly one DOCX package")
        elif choice == "both":
            require_delivery_choice([row], "zip")
            require_delivery_choice([row], "word")
            if ".zip" not in suffixes or ".docx" not in suffixes:
                raise ValueError(f"{row['number']}: both requires at least one ZIP and one DOCX")
            if any(suffix not in {".zip", ".docx"} for suffix in suffixes):
                raise ValueError(f"{row['number']}: unsupported package type")
        else:
            raise ValueError(f"{row['number']}: delivery format is not confirmed")
        row["package_name"] = ";".join(path.name for path in args.package)
        row["package_sha256"] = ";".join(sha256_file(path) for path in args.package)
        row["package_attempt_count"] = str(attempts)

    elif args.to == "delivered":
        expected_shas = [value for value in row.get("package_sha256", "").split(";") if value]
        if not expected_shas or sorted(args.delivery_confirmed_sha) != sorted(expected_shas):
            raise ValueError(
                f"{row['number']}: every delivery confirmation SHA must match a packaged file"
            )
        row["delivered_at"] = now_iso()

    row["workflow_state"] = args.to
    row["updated_at"] = now_iso()


def reset_for_retry(row: dict[str, str], reason: str) -> None:
    row["workflow_state"] = "planned"
    row["generation_version"] = str(integer_field(row, "generation_version", 1) + 1)
    row["raw_output_path"] = ""
    row["raw_sha256"] = ""
    row["output_sha256"] = ""
    row["composition_attempt_count"] = "0"
    row["package_attempt_count"] = "0"
    row["qa_auto_status"] = "pending"
    row["qa_visual_status"] = "pending"
    row["qa_status"] = "pending"
    row["diversity_visual_status"] = "pending"
    row["package_name"] = ""
    row["package_sha256"] = ""
    row["delivered_at"] = ""
    entry = f"[{now_iso()}] workflow reopened: {reason}"
    row["failure_detail"] = "\n".join(
        value for value in (row.get("failure_detail", ""), entry) if value
    )
    row["updated_at"] = now_iso()


def reset_for_recompose(row: dict[str, str], reason: str) -> None:
    if integer_field(row, "composition_attempt_count") >= 2:
        raise ValueError(f"{row['number']}: composition retry limit reached")
    row["workflow_state"] = "generated"
    row["output_sha256"] = ""
    row["qa_auto_status"] = "pending"
    row["qa_visual_status"] = "pending"
    row["qa_status"] = "pending"
    row["diversity_visual_status"] = "pending"
    entry = f"[{now_iso()}] composition reopened: {reason}"
    row["failure_detail"] = "\n".join(
        value for value in (row.get("failure_detail", ""), entry) if value
    )
    row["updated_at"] = now_iso()


def main() -> int:
    args = parse_args()
    fieldnames, rows = read_manifest(args.manifest)
    require_schema(fieldnames)
    chosen = selected(rows, args)

    if args.command == "status":
        print(
            json.dumps(
                [
                    {
                        "number": row["number"],
                        "state": row.get("workflow_state", "planned"),
                        "attempt_count": row.get("attempt_count", "0"),
                        "qa_status": row.get("qa_status", "pending"),
                        "failure_codes": row.get("failure_codes", ""),
                    }
                    for row in chosen
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    for row in chosen:
        if args.command == "advance":
            advance_row(row, args)
        elif args.command == "visual":
            if row.get("workflow_state") != "composed":
                raise ValueError(f"{row['number']}: visual QA requires composed state")
            if args.result == "pass":
                row["qa_visual_status"] = "pass"
                if args.diversity_pass:
                    row["diversity_visual_status"] = "pass"
            else:
                if not args.failure_code:
                    raise ValueError("--failure-code is required for failed visual QA")
                row["qa_visual_status"] = "fail"
                row["qa_status"] = "fail"
                append_failure(row, args.failure_code, args.detail)
            row["updated_at"] = now_iso()
        elif args.command == "fail":
            if row.get("workflow_state") in {"qa_passed", "packaged", "delivered"}:
                raise ValueError(
                    f"{row['number']}: passed cards cannot be failed without explicit reopen"
                )
            row[f"qa_{args.gate}_status"] = "fail"
            row["qa_status"] = "fail"
            append_failure(row, args.failure_code, args.detail)
            if integer_field(row, "attempt_count") >= 3:
                row["qa_status"] = "blocked"
            row["updated_at"] = now_iso()
        elif args.command == "retry":
            if row.get("workflow_state") not in {"generated", "composed"}:
                raise ValueError(f"{row['number']}: retry requires generated or composed state")
            if args.mode == "recompose":
                if row.get("workflow_state") != "composed":
                    raise ValueError(f"{row['number']}: recompose requires composed state")
                reset_for_recompose(row, args.reason)
            else:
                attempts = integer_field(row, "attempt_count")
                if attempts >= 3 and not args.override_limit:
                    raise ValueError(
                        f"{row['number']}: retry limit reached; user decision is required"
                    )
                reset_for_retry(row, args.reason)
        elif args.command == "reopen":
            if row.get("workflow_state") not in {"qa_passed", "packaged", "delivered"}:
                raise ValueError(f"{row['number']}: reopen is only for already passed work")
            reset_for_retry(row, args.reason)
            row["attempt_count"] = "0"

    atomic_write_csv(args.manifest, fieldnames, rows)
    print(f"Updated {len(chosen)} manifest row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
