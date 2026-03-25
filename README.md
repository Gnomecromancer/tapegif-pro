# tapegif Pro

The pro layer on top of [tapegif](https://github.com/Gnomecromancer/tapegif) — an interactive TUI recorder
for Textual apps, with WebP/APNG output, frame timing editor, and watermarks.

## What's different from free tapegif

| | tapegif (free) | tapegif Pro |
|---|---|---|
| Output formats | GIF | GIF + WebP + APNG |
| File size | baseline | WebP ~40-60% smaller |
| Color depth | 256-color palette | Full color (WebP/APNG) |
| Watermarks | — | ✓ positioned text stamp |
| Frame editor | — | ✓ edit hold times in TUI |
| Interactive TUI | — | ✓ progress, preview, export |
| Headless mode | ✓ | ✓ (`--no-ui`) |

## Install

```
pip install tapegif  # base recorder
pip install tapegif-pro
playwright install chromium
```

tapegif-pro depends on the free `tapegif` package for recording.

## Usage

```
tapegif-pro record myapp.py
tapegif-pro record myapp.py --tape demo.tape --format webp
tapegif-pro record myapp.py --format apng --watermark "beta"
tapegif-pro record myapp.py --no-ui --output out.webp
tapegif-pro preview myapp.py --output hero.png
```

**The TUI** opens by default. It shows:
- Left panel: step-by-step recording progress (○ pending / ● active / ✓ done)
- Right panel: captured frames table with editable hold times
- Export panel: choose format, output path, optional watermark, then Export

## Tape format

Same as tapegif — see [tapegif docs](https://github.com/Gnomecromancer/tapegif#tape-format).

## CLI reference

```
tapegif-pro record APP [--tape FILE] [--output FILE]
                       [--format gif|webp|apng] [--width PX]
                       [--watermark TEXT] [--no-ui]

tapegif-pro preview APP [--output FILE] [--sleep SECS]
```

`APP` is `path/to/file.py` (auto-discovers App class) or `path/to/file.py:ClassName`.

## Requirements

- Python 3.10+
- tapegif (free) — `pip install tapegif`
- Playwright (Chromium) — `playwright install chromium`
- Pillow

## License

Commercial — distributed as part of the devcull Pro Pack.
