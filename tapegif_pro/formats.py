"""
Extra output formats for tapegif Pro: animated WebP and APNG.

Both preserve full color (no 256-palette quantization needed), making
them noticeably sharper than GIF for terminal screenshots.
"""
from __future__ import annotations
import io
import os
import tempfile
from pathlib import Path
from typing import Callable

from PIL import Image
from playwright.sync_api import sync_playwright


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:transparent;display:inline-block;}}</style>
</head>
<body>{svg}</body>
</html>"""


def _svg_to_pil(svg: str, page, gif_width: int) -> Image.Image:
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(_HTML_TEMPLATE.format(svg=svg))
        tmp = f.name
    try:
        page.goto("file:///" + tmp.replace("\\", "/"))
        page.wait_for_load_state("networkidle")
        svg_el = page.query_selector("svg")
        if svg_el:
            bb = svg_el.bounding_box()
            if bb:
                page.set_viewport_size({
                    "width": max(1, int(bb["width"]) + 4),
                    "height": max(1, int(bb["height"]) + 4),
                })
        png_bytes = page.screenshot(full_page=True)
    finally:
        os.unlink(tmp)

    img = Image.open(io.BytesIO(png_bytes))
    ratio = gif_width / img.width
    new_h = max(1, int(img.height * ratio))
    return img.resize((gif_width, new_h), Image.LANCZOS).convert("RGBA")


def _render_images(
    frames: list[tuple[str, int]],
    gif_width: int,
    watermark_fn: Callable | None,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[Image.Image], list[int]]:
    images: list[Image.Image] = []
    delays: list[int] = []
    total = len(frames)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for i, (svg, hold_ms) in enumerate(frames):
            img = _svg_to_pil(svg, page, gif_width)
            if watermark_fn:
                img = watermark_fn(img)
            images.append(img)
            delays.append(hold_ms)
            if on_progress:
                on_progress(i + 1, total)
        browser.close()

    return images, delays


def render_gif(
    frames: list[tuple[str, int]],
    output_path: str | Path,
    gif_width: int = 900,
    watermark_fn: Callable | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """GIF with optional watermark. Same format as tapegif free, plus watermark support."""
    output_path = Path(output_path)
    images, delays = _render_images(frames, gif_width, watermark_fn, on_progress)

    rgb = [img.convert("RGB") for img in images]
    palette = [img.quantize(colors=256, method=Image.Quantize.MEDIANCUT) for img in rgb]
    palette[0].save(
        output_path,
        save_all=True,
        append_images=palette[1:],
        loop=0,
        duration=delays,
        optimize=True,
    )
    return output_path


def render_webp(
    frames: list[tuple[str, int]],
    output_path: str | Path,
    gif_width: int = 900,
    watermark_fn: Callable | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Animated WebP — full color, typically 40-60% smaller than GIF."""
    output_path = Path(output_path)
    images, delays = _render_images(frames, gif_width, watermark_fn, on_progress)

    images[0].save(
        output_path,
        format="WEBP",
        save_all=True,
        append_images=images[1:],
        loop=0,
        duration=delays,
    )
    return output_path


def render_apng(
    frames: list[tuple[str, int]],
    output_path: str | Path,
    gif_width: int = 900,
    watermark_fn: Callable | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Animated PNG — lossless full color, best quality."""
    output_path = Path(output_path)
    images, delays = _render_images(frames, gif_width, watermark_fn, on_progress)

    images[0].save(
        output_path,
        format="PNG",
        save_all=True,
        append_images=images[1:],
        loop=0,
        duration=delays,
    )
    return output_path


RENDERERS = {
    "gif": render_gif,
    "webp": render_webp,
    "apng": render_apng,
}
