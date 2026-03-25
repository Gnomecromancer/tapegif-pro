"""Unit tests for tapegif_pro.formats that don't need Playwright."""
from __future__ import annotations

from tapegif_pro.formats import _viewbox_size, RENDERERS


def test_viewbox_size_double_quotes():
    svg = '<svg viewBox="0 0 900 400" xmlns="...">'
    assert _viewbox_size(svg) == (900, 400)


def test_viewbox_size_single_quotes():
    svg = "<svg viewBox='0 0 1200 600'>"
    assert _viewbox_size(svg) == (1200, 600)


def test_viewbox_size_missing():
    assert _viewbox_size("<svg>") is None


def test_renderers_keys():
    assert set(RENDERERS.keys()) == {"gif", "webp", "apng"}


def test_renderers_callable():
    for fn in RENDERERS.values():
        assert callable(fn)
