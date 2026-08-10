#!/usr/bin/env python3
"""Fail fast on missing card-generation and document-rendering capabilities."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path


def first_command(names: tuple[str, ...]) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return str(Path(resolved).resolve())
    return None


def first_existing(paths: list[Path]) -> str | None:
    for path in paths:
        if path.is_file():
            return str(path.resolve())
    return None


def find_pdf_rasterizer() -> str | None:
    resolved = first_command(("pdftoppm", "pdftoppm.exe"))
    if resolved:
        path = Path(resolved)
        if path.suffix.casefold() == ".cmd":
            dependencies = path.parent.parent.parent
            native_binary = dependencies / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe"
            if native_binary.is_file():
                return str(native_binary.resolve())
        return resolved
    return None


def windows_renderer_candidates() -> dict[str, str | None]:
    if platform.system() != "Windows":
        return {"winword": None, "wps": None}
    program_files = [
        value
        for value in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        )
        if value
    ]
    roots = [Path(value) for value in program_files]
    winword_paths = [
        root / "Microsoft Office" / "root" / "Office16" / "WINWORD.EXE"
        for root in roots
    ] + [
        root / "Microsoft Office" / "Office16" / "WINWORD.EXE" for root in roots
    ]
    wps_paths = [root / "Kingsoft" / "WPS Office" / "ksolaunch.exe" for root in roots]
    return {
        "winword": first_existing(winword_paths),
        "wps": first_existing(wps_paths),
    }


def probe() -> dict[str, object]:
    windows = windows_renderer_candidates()
    renderers = {
        "soffice": first_command(("soffice", "libreoffice")),
        "winword": windows["winword"] or first_command(("WINWORD.EXE", "winword")),
        "wps": windows["wps"] or first_command(("ksolaunch.exe", "wps")),
    }
    imports = {
        module: importlib.util.find_spec(module) is not None
        for module in ("PIL", "docx")
    }
    return {
        "python": {
            "executable": str(Path(sys.executable).resolve()),
            "version": platform.python_version(),
        },
        "imports": imports,
        "commands": {
            "pdftoppm": find_pdf_rasterizer(),
        },
        "word_renderers": renderers,
        "selected_word_renderer": next(
            (name for name in ("soffice", "winword", "wps") if renderers[name]),
            None,
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--need-word-render",
        action="store_true",
        help="Fail if no Office-compatible renderer is installed.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the probe as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = probe()
    failures = [
        f"missing required Python package: {module}"
        for module, present in result["imports"].items()
        if not present
    ]
    if sys.version_info < (3, 10):
        failures.append(
            f"Python 3.10 or newer is required; found {platform.python_version()}"
        )
    if args.need_word_render and result["selected_word_renderer"] is None:
        failures.append(
            "no Office-compatible renderer found (install/use LibreOffice, Word, or WPS before Word QA)"
        )
    if args.need_word_render and result["commands"]["pdftoppm"] is None:
        failures.append(
            "no PDF rasterizer found (pdftoppm is required for rendered Word page QA)"
        )
    result["status"] = "passed" if not failures else "blocked"
    result["failures"] = failures
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"PREFLIGHT {result['status'].upper()}")
        print(f"Python: {result['python']['executable']}")
        print(f"Packages: {result['imports']}")
        print(f"Word renderer: {result['selected_word_renderer'] or 'none'}")
        if failures:
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
