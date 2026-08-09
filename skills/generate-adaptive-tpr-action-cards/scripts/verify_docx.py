#!/usr/bin/env python3
"""Verify the static package structure and optional rendered pages of a card DOCX."""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

from batch_common import read_manifest, resolve_word_identifier_visibility, select_rows


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
W = "{" + NS["w"] + "}"
R = "{" + NS["r"] + "}"
IDENTIFIER_CLEAR_TOP = 1450
IDENTIFIER_CLEAR_BOTTOM = 1504
IDENTIFIER_DARK_THRESHOLD = 180
IDENTIFIER_DARK_PIXEL_MINIMUM = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--expected-cards", type=int)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--id", dest="identifiers", action="append", default=[])
    parser.add_argument("--media-source-dir", type=Path)
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument(
        "--identifier-visibility",
        choices=["hidden", "shown"],
        help="Expected Word identifier policy; defaults to the manifest value or hidden.",
    )
    return parser.parse_args()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_rows(args) -> list[dict[str, str]]:
    if not args.manifest:
        return []
    _, rows = read_manifest(args.manifest)
    return select_rows(
        rows,
        start=args.start,
        end=args.end,
        identifiers=args.identifiers,
    )


def expected_media_sources(
    rows: list[dict[str, str]], directory: Path
) -> tuple[list[Path], list[str]]:
    sources: list[Path] = []
    errors: list[str] = []
    for row in rows:
        stem = Path(row["output_path"]).stem
        matches = sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.stem == stem
            and path.suffix.casefold() in {".png", ".jpg", ".jpeg"}
        )
        if len(matches) != 1:
            errors.append(
                f"{row['number']}: expected one embedded-media source named {stem}, found {len(matches)}"
            )
        else:
            sources.append(matches[0])
    return sources, errors


def verify_table(table: ET.Element, index: int) -> list[str]:
    errors: list[str] = []
    rows = table.findall("./w:tr", NS)
    cells = table.findall("./w:tr/w:tc", NS)
    if len(rows) != 2 or len(cells) != 4:
        errors.append(f"table {index}: expected 2 rows and 4 cells")
    layout = table.find("./w:tblPr/w:tblLayout", NS)
    if layout is None or layout.get(W + "type") != "fixed":
        errors.append(f"table {index}: layout is not fixed")
    borders = table.find("./w:tblPr/w:tblBorders", NS)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = None if borders is None else borders.find("w:" + edge, NS)
        if element is None or element.get(W + "val") != "nil":
            errors.append(f"table {index}: {edge} border is not nil")
    for cell_index, cell in enumerate(cells, start=1):
        if len(cell.findall(".//wp:inline", NS)) != 1:
            errors.append(f"table {index} cell {cell_index}: expected exactly one inline picture")
    return errors


def verify_inline(inline: ET.Element, index: int) -> list[str]:
    errors: list[str] = []
    extent = inline.find("./wp:extent", NS)
    if extent is None:
        errors.append(f"picture {index}: missing extent")
    else:
        try:
            ratio = int(extent.get("cx", "0")) / int(extent.get("cy", "0"))
            expected_ratio = 1240 / 1754
            if abs(ratio - expected_ratio) > 0.005:
                errors.append(f"picture {index}: aspect ratio {ratio:.5f} is unexpected")
        except (ValueError, ZeroDivisionError):
            errors.append(f"picture {index}: invalid extent")
    if inline.findall(".//a:srcRect", NS):
        errors.append(f"picture {index}: source image is cropped")
    lines = inline.findall(".//pic:spPr/a:ln", NS)
    if len(lines) != 1:
        errors.append(f"picture {index}: expected exactly one picture outline")
    else:
        line = lines[0]
        if line.get("w") != "6350":
            errors.append(f"picture {index}: outline width is not 0.5 pt")
        color = line.find("./a:solidFill/a:srgbClr", NS)
        dash = line.find("./a:prstDash", NS)
        if color is None or color.get("val") != "000000":
            errors.append(f"picture {index}: outline is not solid black")
        if dash is None or dash.get("val") != "solid":
            errors.append(f"picture {index}: outline dash is not solid")
    return errors


def verify_rendered_pages(render_dir: Path, expected_pages: int) -> list[str]:
    errors: list[str] = []
    page_files = sorted(render_dir.glob("page-*.png"))
    if len(page_files) != expected_pages:
        errors.append(
            f"rendered page count is {len(page_files)}, expected {expected_pages}"
        )
    for path in page_files:
        try:
            with Image.open(path) as image:
                image.load()
                rgb = image.convert("RGB")
                white = Image.new("RGB", rgb.size, "white")
                if ImageChops.difference(rgb, white).getbbox() is None:
                    errors.append(f"{path.name}: rendered page is blank")
        except Exception as exc:
            errors.append(f"{path.name}: cannot decode rendered page: {exc}")
    return errors


def verify_media_identifier_visibility(
    data: bytes, media_name: str, expected_visibility: str
) -> list[str]:
    errors: list[str] = []
    try:
        with Image.open(BytesIO(data)) as image:
            if image.size != (1240, 1754):
                return [f"{media_name}: embedded media size is {image.size}, expected 1240x1754"]
            grayscale = image.convert("L")
            region = grayscale.crop(
                (0, IDENTIFIER_CLEAR_TOP, grayscale.width, IDENTIFIER_CLEAR_BOTTOM)
            )
            pixels = (
                region.get_flattened_data()
                if hasattr(region, "get_flattened_data")
                else region.getdata()
            )
            dark_pixels = sum(
                pixel < IDENTIFIER_DARK_THRESHOLD for pixel in pixels
            )
    except Exception as exc:
        return [f"{media_name}: cannot inspect identifier region: {exc}"]
    if expected_visibility == "hidden" and dark_pixels >= IDENTIFIER_DARK_PIXEL_MINIMUM:
        errors.append(f"{media_name}: action identifier is visible but should be hidden")
    if expected_visibility == "shown" and dark_pixels < IDENTIFIER_DARK_PIXEL_MINIMUM:
        errors.append(f"{media_name}: action identifier is hidden but should be shown")
    return errors


def verify_package(
    document: Path,
    expected_cards: int,
    media_sources: list[Path],
    identifier_visibility: str,
) -> list[str]:
    errors: list[str] = []
    expected_pages = expected_cards // 4
    required_parts = {
        "[Content_Types].xml",
        "word/document.xml",
        "word/_rels/document.xml.rels",
    }
    try:
        with zipfile.ZipFile(document) as archive:
            names = archive.namelist()
            missing_parts = sorted(required_parts - set(names))
            if missing_parts:
                return [f"DOCX is missing required parts: {missing_parts}"]
            corrupt = archive.testzip()
            if corrupt:
                errors.append(f"DOCX has corrupt member {corrupt}")
            media_names = sorted(name for name in names if name.startswith("word/media/"))
            if len(media_names) != expected_cards:
                errors.append(
                    f"DOCX media count is {len(media_names)}, expected {expected_cards}"
                )

            document_xml = ET.fromstring(archive.read("word/document.xml"))
            rels_xml = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
            body = document_xml.find("w:body", NS)
            if body is None:
                return errors + ["word/document.xml has no body"]

            tables = body.findall("./w:tbl", NS)
            inlines = body.findall(".//wp:inline", NS)
            anchors = body.findall(".//wp:anchor", NS)
            page_breaks = [
                element
                for element in body.findall(".//w:br", NS)
                if element.get(W + "type") == "page"
            ]
            if len(tables) != expected_pages:
                errors.append(f"table count is {len(tables)}, expected {expected_pages}")
            if len(inlines) != expected_cards:
                errors.append(f"inline picture count is {len(inlines)}, expected {expected_cards}")
            if anchors:
                errors.append(f"found {len(anchors)} floating picture anchors")
            if len(page_breaks) != max(0, expected_pages - 1):
                errors.append(
                    f"explicit page-break count is {len(page_breaks)}, "
                    f"expected {max(0, expected_pages - 1)}"
                )
            for index, table in enumerate(tables, start=1):
                errors.extend(verify_table(table, index))
            for index, inline in enumerate(inlines, start=1):
                errors.extend(verify_inline(inline, index))

            sect = body.find("./w:sectPr", NS)
            if sect is None:
                errors.append("document is missing section properties")
            else:
                size = sect.find("./w:pgSz", NS)
                margins = sect.find("./w:pgMar", NS)
                if size is None:
                    errors.append("section is missing page size")
                else:
                    try:
                        width = int(size.get(W + "w", "0"))
                        height = int(size.get(W + "h", "0"))
                        if abs(width - 11906) > 2 or abs(height - 16838) > 2:
                            errors.append(f"page size is {width}x{height}, not A4 portrait")
                    except ValueError:
                        errors.append("page size values are invalid")
                if margins is None:
                    errors.append("section is missing page margins")
                else:
                    for key in ("top", "bottom", "left", "right", "header", "footer"):
                        if margins.get(W + key) != "0":
                            errors.append(f"section {key} margin is not zero")

            rel_targets = {
                element.get("Id"): element.get("Target")
                for element in rels_xml.findall("./pr:Relationship", NS)
            }
            ordered_media: list[str] = []
            for index, inline in enumerate(inlines, start=1):
                blip = inline.find(".//a:blip", NS)
                relationship = None if blip is None else blip.get(R + "embed")
                target = rel_targets.get(relationship)
                if not target:
                    errors.append(f"picture {index}: missing media relationship")
                    continue
                name = "word/" + target.lstrip("/")
                if name not in names:
                    errors.append(f"picture {index}: relationship target {name} is missing")
                    continue
                ordered_media.append(name)

            if len(set(ordered_media)) != len(ordered_media):
                errors.append("one embedded media file is reused by multiple cards")
            for media_name in ordered_media:
                errors.extend(
                    verify_media_identifier_visibility(
                        archive.read(media_name), media_name, identifier_visibility
                    )
                )
            if media_sources and len(ordered_media) == len(media_sources):
                for index, (media_name, source) in enumerate(
                    zip(ordered_media, media_sources), start=1
                ):
                    if sha256_bytes(archive.read(media_name)) != sha256_bytes(source.read_bytes()):
                        errors.append(
                            f"picture {index}: embedded media does not match {source.name}"
                        )
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        errors.append(f"cannot verify DOCX package: {exc}")
    return errors


def main() -> int:
    args = parse_args()
    try:
        rows = selected_rows(args)
        identifier_visibility = resolve_word_identifier_visibility(
            rows, args.identifier_visibility
        )
        expected_cards = args.expected_cards or len(rows)
        if expected_cards < 1 or expected_cards % 4:
            raise ValueError("Expected card count must be a positive multiple of four")
        if args.expected_cards and rows and args.expected_cards != len(rows):
            raise ValueError("--expected-cards does not match the selected manifest rows")
        media_sources: list[Path] = []
        failures: list[str] = []
        if args.media_source_dir:
            if not rows:
                raise ValueError("--media-source-dir requires --manifest")
            media_sources, media_errors = expected_media_sources(rows, args.media_source_dir)
            failures.extend(media_errors)
        failures.extend(
            verify_package(
                args.document,
                expected_cards,
                media_sources,
                identifier_visibility,
            )
        )
        if args.render_dir:
            failures.extend(verify_rendered_pages(args.render_dir, expected_cards // 4))
    except (OSError, ValueError) as exc:
        failures = [str(exc)]

    if failures:
        print("DOCX CHECK FAILED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(
        f"DOCX CHECK PASSED: {expected_cards} cards, {expected_cards // 4} pages, "
        f"identifiers {identifier_visibility}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
