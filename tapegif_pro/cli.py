"""
tapegif Pro CLI.

    tapegif-pro record myapp.py [--tape demo.tape] [--format webp] [--watermark "text"]
    tapegif-pro preview myapp.py [--output shot.png]
"""
from __future__ import annotations
import sys
from pathlib import Path

import click

from termgif.tape import load as load_tape, default_tape
from termgif.recorder import _load_app_class


@click.group()
def main():
    """tapegif Pro — TUI recorder, WebP/APNG output, watermarks."""


@main.command()
@click.argument("app_spec", metavar="APP")
@click.option("--tape", "-t", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--format", "-f", "fmt", type=click.Choice(["gif", "webp", "apng"]), default="gif", show_default=True)
@click.option("--width", "-w", type=int, default=None)
@click.option("--watermark", default="", help="Text to stamp on every frame.")
@click.option("--no-ui", is_flag=True, help="Skip the TUI and render headlessly.")
def record(
    app_spec: str,
    tape: Path | None,
    output: Path | None,
    fmt: str,
    width: int | None,
    watermark: str,
    no_ui: bool,
):
    """
    Record APP to an animated GIF, WebP, or APNG.

    Opens the tapegif Pro TUI by default. Pass --no-ui for headless mode.

    \b
    Examples:
        tapegif-pro record myapp.py
        tapegif-pro record myapp.py --format webp --watermark "demo"
        tapegif-pro record myapp.py --tape demo.tape --no-ui
    """
    tape_obj = load_tape(tape) if tape else default_tape()
    if width is not None:
        tape_obj.gif_width = width

    ext = {"gif": ".gif", "webp": ".webp", "apng": ".png"}[fmt]
    out = output or Path("demo" + ext)

    if no_ui:
        _record_headless(app_spec, tape_obj, out, fmt, watermark)
    else:
        from .tui import RecorderTUI
        app = RecorderTUI(app_spec, tape_obj, out, fmt, watermark)
        app.run()


def _record_headless(app_spec, tape_obj, out, fmt, watermark):
    from termgif.recorder import record as do_record
    from .formats import RENDERERS
    from .overlay import make_watermark_fn

    click.echo(f"recording {app_spec} …")
    try:
        frames = do_record(app_spec, tape_obj)
    except Exception as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)

    if not frames:
        click.echo("no frames captured", err=True)
        sys.exit(1)

    wm_fn = make_watermark_fn(watermark) if watermark else None
    click.echo(f"rendering {len(frames)} frame(s) as {fmt.upper()} …")
    try:
        result = RENDERERS[fmt](frames, out, tape_obj.gif_width, wm_fn)
    except Exception as e:
        click.echo(f"render error: {e}", err=True)
        sys.exit(1)

    size_kb = result.stat().st_size // 1024
    click.echo(f"saved {result} ({len(frames)} frames, {size_kb} KB)")


@main.command()
@click.argument("app_spec", metavar="APP")
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=Path), default=Path("screenshot.png"), show_default=True)
@click.option("--sleep", default=2.0, show_default=True, help="Seconds to wait before capturing.")
def preview(app_spec: str, output: Path, sleep: float):
    """
    Take a single PNG screenshot of APP.

    Useful for README hero images without recording a full GIF.

    \b
    Example:
        tapegif-pro preview myapp.py --output hero.png
    """
    import asyncio
    import io
    from PIL import Image
    from playwright.sync_api import sync_playwright
    import tempfile, os

    from termgif.tape import Tape, Step
    from termgif.recorder import record

    tape = Tape(steps=[Step(sleep=sleep, capture=1)])
    frames = record(app_spec, tape)
    if not frames:
        click.echo("no frame captured", err=True)
        sys.exit(1)

    svg, _ = frames[0]

    import re
    _HTML = "<html><head><style>html,body{{margin:0;padding:0;background:#000;}}svg{{display:block;}}</style></head><body>{svg}</body></html>"

    def _vb(s):
        m = re.search(r'viewBox=["\'][\d.]+ [\d.]+ ([\d.]+) ([\d.]+)["\']', s)
        return (int(float(m.group(1))), int(float(m.group(2)))) if m else None

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        vb = _vb(svg)
        if vb:
            page.set_viewport_size({"width": vb[0] + 4, "height": vb[1] + 4})
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
            f.write(_HTML.format(svg=svg))
            tmp = f.name
        try:
            page.goto("file:///" + tmp.replace("\\", "/"))
            page.wait_for_load_state("networkidle")
            png = page.screenshot(full_page=True)
        finally:
            os.unlink(tmp)
        browser.close()

    img = Image.open(io.BytesIO(png))
    img.save(output, format="PNG")
    click.echo(f"saved {output} ({img.width}×{img.height})")
