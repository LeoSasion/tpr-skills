#!/usr/bin/env python3
"""Compose a generated action image as a print-ready bilingual A4 card."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, PngImagePlugin


WIDTH = 1240
HEIGHT = 1754
IMAGE_BOTTOM = 1450
CAPTION_HEIGHT = HEIGHT - IMAGE_BOTTOM
CAPTION_LAYOUT_VERSION = 2
FONT_PATH = Path(__file__).resolve().parents[1] / "assets" / "NotoSansSC-700.ttf"
CHINESE_CLOSING_PUNCTUATION = set("，。！？；：、）》】”’")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--identifier", required=True)
    parser.add_argument("--english", required=True)
    parser.add_argument("--chinese", required=True)
    parser.add_argument("--font", type=Path, default=FONT_PATH)
    parser.add_argument("--english-size", type=int, default=52)
    parser.add_argument("--chinese-size", type=int, default=50)
    parser.add_argument("--min-font-size", type=int, default=34)
    parser.add_argument("--max-lines", type=int, default=2)
    return parser.parse_args()


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.is_file():
        raise FileNotFoundError(f"Font not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pixel_sha256(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_english(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str] | None:
    words = text.split()
    if not words:
        return None
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if not current or text_width(draw, word, font) > max_width:
            return None
        lines.append(current)
        current = word
    lines.append(current)
    return lines if len(lines) <= max_lines else None


def wrap_chinese(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str] | None:
    if not text:
        return None
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if not current or text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = character
    lines.append(current)

    for index in range(1, len(lines)):
        while lines[index] and lines[index][0] in CHINESE_CLOSING_PUNCTUATION:
            candidate = lines[index - 1] + lines[index][0]
            if text_width(draw, candidate, font) > max_width:
                break
            lines[index - 1] = candidate
            lines[index] = lines[index][1:]
    lines = [line for line in lines if line]
    return lines if len(lines) <= max_lines else None


def line_height(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[3] - box[1]


def build_caption_layout(
    identifier: str,
    english: str,
    chinese: str,
    font_path: Path = FONT_PATH,
    english_size: int = 52,
    chinese_size: int = 50,
    min_font_size: int = 34,
    max_lines: int = 2,
) -> dict[str, object]:
    if not identifier or not english or not chinese:
        raise ValueError("Identifier, English, and Chinese text must all be non-empty")
    if min_font_size < 24:
        raise ValueError("--min-font-size must be at least 24")
    if max_lines not in {1, 2}:
        raise ValueError("--max-lines must be 1 or 2")

    probe = Image.new("RGB", (WIDTH, CAPTION_HEIGHT), "white")
    draw = ImageDraw.Draw(probe)
    max_text_width = WIDTH - 120
    content_height = CAPTION_HEIGHT - 56
    within_gap = 7
    block_gap = 16

    delta = 0
    while True:
        en_size = max(min_font_size, english_size - delta)
        zh_size = max(min_font_size, chinese_size - delta)
        en_font = load_font(font_path, en_size)
        zh_font = load_font(font_path, zh_size)
        en_lines = wrap_english(draw, english, en_font, max_text_width, max_lines)
        zh_lines = wrap_chinese(draw, chinese, zh_font, max_text_width, max_lines)
        if en_lines and zh_lines:
            en_heights = [line_height(draw, line, en_font) for line in en_lines]
            zh_heights = [line_height(draw, line, zh_font) for line in zh_lines]
            total = (
                sum(en_heights)
                + within_gap * (len(en_lines) - 1)
                + block_gap
                + sum(zh_heights)
                + within_gap * (len(zh_lines) - 1)
            )
            if total <= content_height:
                return {
                    "version": CAPTION_LAYOUT_VERSION,
                    "identifier": identifier,
                    "english_lines": en_lines,
                    "chinese_lines": zh_lines,
                    "english_size": en_size,
                    "chinese_size": zh_size,
                    "requested_english_size": english_size,
                    "requested_chinese_size": chinese_size,
                    "min_font_size": min_font_size,
                    "max_lines": max_lines,
                    "within_gap": within_gap,
                    "block_gap": block_gap,
                    "content_height": content_height,
                }
        if en_size == min_font_size and zh_size == min_font_size:
            raise ValueError(
                "Caption cannot fit within two lines per language at the minimum font size"
            )
        delta += 2


def render_caption_strip(
    identifier: str,
    english: str,
    chinese: str,
    font_path: Path = FONT_PATH,
    english_size: int = 52,
    chinese_size: int = 50,
    min_font_size: int = 34,
    max_lines: int = 2,
) -> tuple[Image.Image, dict[str, object]]:
    layout = build_caption_layout(
        identifier,
        english,
        chinese,
        font_path,
        english_size,
        chinese_size,
        min_font_size,
        max_lines,
    )
    strip = Image.new("RGB", (WIDTH, CAPTION_HEIGHT), "white")
    draw = ImageDraw.Draw(strip)

    identifier_font = load_font(font_path, 28)
    draw.text((48, 17), identifier, font=identifier_font, fill="black", anchor="lt")

    en_font = load_font(font_path, int(layout["english_size"]))
    zh_font = load_font(font_path, int(layout["chinese_size"]))
    en_lines = list(layout["english_lines"])
    zh_lines = list(layout["chinese_lines"])
    within_gap = int(layout["within_gap"])
    block_gap = int(layout["block_gap"])
    en_heights = [line_height(draw, line, en_font) for line in en_lines]
    zh_heights = [line_height(draw, line, zh_font) for line in zh_lines]
    total_height = (
        sum(en_heights)
        + within_gap * (len(en_lines) - 1)
        + block_gap
        + sum(zh_heights)
        + within_gap * (len(zh_lines) - 1)
    )
    cursor = 52 + (int(layout["content_height"]) - total_height) / 2

    for line, height in zip(en_lines, en_heights):
        draw.text((WIDTH / 2, cursor + height / 2), line, font=en_font, fill="black", anchor="mm")
        cursor += height + within_gap
    cursor += block_gap - within_gap
    for line, height in zip(zh_lines, zh_heights):
        draw.text((WIDTH / 2, cursor + height / 2), line, font=zh_font, fill="black", anchor="mm")
        cursor += height + within_gap
    return strip, layout


def flatten_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, "white")
    white.alpha_composite(rgba)
    return white.convert("RGB")


def save_png_atomically(
    canvas: Image.Image,
    output: Path,
    pnginfo: PngImagePlugin.PngInfo,
) -> None:
    """Publish only a completely written, decodable PNG in the destination directory."""
    output_mode = output.stat().st_mode & 0o777 if output.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=output.name + ".",
        suffix=".tmp",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        canvas.save(
            temporary,
            format="PNG",
            dpi=(150, 150),
            pnginfo=pnginfo,
            optimize=True,
        )
        # Windows requires a writable file descriptor for os.fsync().
        with temporary.open("r+b") as handle:
            if not handle.read(8).startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Temporary compositor output is not a PNG")
            handle.flush()
            os.fsync(handle.fileno())
        with Image.open(temporary) as check:
            if check.format != "PNG" or check.size != (WIDTH, HEIGHT):
                raise RuntimeError(
                    f"Temporary compositor output has format/size {check.format}/{check.size}"
                )
            missing_metadata = sorted(
                key
                for key in (
                    "Identifier",
                    "English",
                    "Chinese",
                    "CaptionEmbedded",
                    "CompositorVersion",
                    "CaptionLayout",
                    "CaptionPixelSHA256",
                    "FontSHA256",
                )
                if not check.info.get(key)
            )
            if missing_metadata:
                raise RuntimeError(
                    f"Temporary compositor output lacks metadata {missing_metadata}"
                )
            check.load()
        os.chmod(temporary, output_mode)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(f"Input image not found: {args.input}")

    with Image.open(args.input) as source:
        source = ImageOps.exif_transpose(source)
        source = flatten_rgb(source)
        source.thumbnail((WIDTH, IMAGE_BOTTOM), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (WIDTH, HEIGHT), "white")
        x = (WIDTH - source.width) // 2
        y = max(0, (IMAGE_BOTTOM - source.height) // 2)
        canvas.paste(source, (x, y))

    caption, layout = render_caption_strip(
        args.identifier,
        args.english,
        args.chinese,
        args.font,
        args.english_size,
        args.chinese_size,
        args.min_font_size,
        args.max_lines,
    )
    canvas.paste(caption, (0, IMAGE_BOTTOM))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Identifier", args.identifier)
    pnginfo.add_text("English", args.english)
    pnginfo.add_text("Chinese", args.chinese)
    pnginfo.add_text("CaptionEmbedded", "true")
    pnginfo.add_text("CompositorVersion", str(CAPTION_LAYOUT_VERSION))
    pnginfo.add_text("CaptionLayout", json.dumps(layout, ensure_ascii=False, sort_keys=True))
    pnginfo.add_text("CaptionPixelSHA256", pixel_sha256(caption))
    pnginfo.add_text("FontSHA256", file_sha256(args.font))
    save_png_atomically(canvas, args.output, pnginfo)

    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "size": [WIDTH, HEIGHT],
                "dpi": [150, 150],
                "identifier": args.identifier,
                "english": args.english,
                "chinese": args.chinese,
                "caption_layout": layout,
                "caption_pixel_sha256": pixel_sha256(caption),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
