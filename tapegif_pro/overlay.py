"""Watermark / text overlay for tapegif Pro."""
from __future__ import annotations
from typing import Callable

from PIL import Image, ImageDraw


def make_watermark_fn(text: str, position: str = "br") -> Callable:
    """
    Return a function that stamps a text watermark onto a PIL image.

    position: 'br' (bottom-right), 'bl' (bottom-left), 'tr', 'tl', 'center'
    """
    def apply(img: Image.Image) -> Image.Image:
        img = img.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        margin = 14

        try:
            bbox = draw.textbbox((0, 0), text)
        except TypeError:
            bbox = (0, 0, len(text) * 7, 13)

        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if position == "br":
            x, y = img.width - tw - margin, img.height - th - margin
        elif position == "bl":
            x, y = margin, img.height - th - margin
        elif position == "tr":
            x, y = img.width - tw - margin, margin
        elif position == "tl":
            x, y = margin, margin
        else:  # center
            x, y = (img.width - tw) // 2, (img.height - th) // 2

        # Subtle drop shadow + white text
        draw.text((x + 1, y + 1), text, fill=(0, 0, 0, 140))
        draw.text((x, y), text, fill=(230, 230, 230, 210))
        return img

    return apply
