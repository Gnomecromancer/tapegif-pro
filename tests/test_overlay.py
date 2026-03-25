"""Tests for tapegif_pro.overlay — no Playwright required."""
from __future__ import annotations

from PIL import Image
from tapegif_pro.overlay import make_watermark_fn


def _blank(w=200, h=100) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 255))


def test_watermark_returns_image():
    fn = make_watermark_fn("test")
    img = fn(_blank())
    assert isinstance(img, Image.Image)


def test_watermark_preserves_size():
    fn = make_watermark_fn("hello")
    orig = _blank(320, 240)
    result = fn(orig)
    assert result.size == orig.size


def test_watermark_does_not_mutate_original():
    fn = make_watermark_fn("hello")
    orig = _blank()
    pixels_before = list(orig.getdata())
    fn(orig)
    assert list(orig.getdata()) == pixels_before


def test_all_positions():
    for pos in ("br", "bl", "tr", "tl", "center"):
        fn = make_watermark_fn("pos", position=pos)
        result = fn(_blank())
        assert result.size == (200, 100)
