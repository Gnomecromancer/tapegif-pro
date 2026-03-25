"""
tapegif Pro TUI — visual recorder with live step progress, frame timing
editor, and export panel.
"""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Callable

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Rule,
    Select,
    Static,
)


# ---------------------------------------------------------------------------
# Messages (worker → main thread)
# ---------------------------------------------------------------------------

class StepStarted(Message):
    def __init__(self, idx: int) -> None:
        super().__init__()
        self.idx = idx


class FrameCaptured(Message):
    def __init__(self, frame_num: int, svg: str, hold_ms: int) -> None:
        super().__init__()
        self.frame_num = frame_num
        self.svg = svg
        self.hold_ms = hold_ms


class RecordingDone(Message):
    pass


class RecordingFailed(Message):
    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error


class ExportDone(Message):
    def __init__(self, path: str, size_kb: int) -> None:
        super().__init__()
        self.path = path
        self.size_kb = size_kb


class ExportFailed(Message):
    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step_label(step) -> str:
    parts = []
    if step.type is not None:
        parts.append(f'type "{step.type}"')
    if step.press is not None:
        parts.append(f"press {step.press}")
    if step.sleep:
        parts.append(f"sleep {step.sleep}s")
    if step.capture is not None:
        parts.append(f"capture {step.capture}ms")
    return "  ".join(parts) if parts else "(empty step)"


# ---------------------------------------------------------------------------
# Main TUI
# ---------------------------------------------------------------------------

class RecorderTUI(App):
    TITLE = "tapegif pro"

    CSS = """
    Screen { layout: vertical; }

    #main { height: 1fr; }

    #left {
        width: 36;
        border: solid $primary;
        padding: 0 1;
    }
    #right {
        width: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }

    #steps-list { height: auto; max-height: 20; }

    #status {
        height: 3;
        color: $text-muted;
        padding-bottom: 1;
    }

    #frames-table { height: auto; max-height: 12; display: none; }
    #frames-table.visible { display: block; }

    #export-panel { display: none; margin-top: 1; }
    #export-panel.visible { display: block; }

    #edit-bar { height: 3; display: none; }
    #edit-bar.visible { display: block; }

    #export-row { height: 3; }
    #format-select { width: 16; }
    #width-input { width: 10; margin-left: 1; }

    Button { margin-top: 1; }
    """

    BINDINGS = [
        ("r", "start_record", "Record"),
        ("e", "focus_export", "Export"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        app_spec: str,
        tape,
        output: Path,
        fmt: str,
        watermark: str,
    ) -> None:
        super().__init__()
        self._app_spec = app_spec
        self._tape = tape
        self._output = output
        self._fmt = fmt
        self._watermark = watermark
        # mutable so hold_ms can be edited post-record
        self._frames: list[list] = []   # [[svg, hold_ms], ...]
        self._state = "ready"           # ready | recording | done
        self._selected_row: int | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Label("STEPS", classes="panel-title")
                yield ListView(id="steps-list")
            with Vertical(id="right"):
                yield Label("STATUS", classes="panel-title")
                yield Static("Press [r] to start recording.", id="status")
                yield Rule()
                yield Label("FRAMES", classes="panel-title")
                yield DataTable(id="frames-table", cursor_type="row")
                with Vertical(id="export-panel"):
                    yield Label("EXPORT", classes="panel-title")
                    with Horizontal(id="export-row"):
                        yield Select(
                            options=[
                                ("GIF", "gif"),
                                ("WebP", "webp"),
                                ("APNG", "apng"),
                            ],
                            value=self._fmt,
                            id="format-select",
                        )
                        yield Input(
                            value=str(self._output),
                            placeholder="output path",
                            id="output-input",
                        )
                    yield Input(
                        value=self._watermark,
                        placeholder="Watermark text (optional)",
                        id="watermark-input",
                    )
                    yield Input(
                        placeholder="Edit hold ms for selected frame (press Enter)",
                        id="edit-bar",
                    )
                    yield Button("Export", id="export-btn", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        lst = self.query_one("#steps-list", ListView)
        for step in self._tape.steps:
            lst.append(ListItem(Label(f"  ○  {_step_label(step)}")))

        table = self.query_one("#frames-table", DataTable)
        table.add_columns("#", "Hold (ms)")

        name = self._app_spec.rsplit(":", 1)[-1].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        self.sub_title = name

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def action_start_record(self) -> None:
        if self._state != "ready":
            return
        self._state = "recording"
        self.query_one("#status", Static).update("Starting…")
        self.run_worker(self._record_worker, thread=True, exclusive=True)

    def _record_worker(self) -> None:
        """Runs in a thread pool. Creates its own event loop via asyncio.run()."""
        from termgif.recorder import _load_app_class

        try:
            AppClass = _load_app_class(self._app_spec)
            app_instance = AppClass(**self._tape.app_args)
            tape = self._tape
            frame_count = [0]

            async def _run() -> None:
                async with app_instance.run_test(size=tape.size) as pilot:
                    for i, step in enumerate(tape.steps):
                        self.call_from_thread(self.post_message, StepStarted(i))
                        if step.type is not None:
                            await pilot.press(*list(step.type))
                        if step.press is not None:
                            await pilot.press(step.press)
                        if step.sleep > 0:
                            await pilot.pause(step.sleep)
                        if step.capture is not None:
                            svg = app_instance.export_screenshot()
                            frame_count[0] += 1
                            self.call_from_thread(
                                self.post_message,
                                FrameCaptured(frame_count[0], svg, step.capture),
                            )

            asyncio.run(_run())
            self.call_from_thread(self.post_message, RecordingDone())
        except Exception as exc:
            self.call_from_thread(self.post_message, RecordingFailed(str(exc)))

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_step_started(self, event: StepStarted) -> None:
        lst = self.query_one("#steps-list", ListView)
        items = list(lst.query(ListItem))
        for j, item in enumerate(items):
            lbl = item.query_one(Label)
            desc = _step_label(self._tape.steps[j])
            if j < event.idx:
                lbl.update(f"  ✓  {desc}")
            elif j == event.idx:
                lbl.update(f"  ●  {desc}")
            else:
                lbl.update(f"  ○  {desc}")

        self.query_one("#status", Static).update(
            f"Step {event.idx + 1} / {len(self._tape.steps)}…"
        )

    def on_frame_captured(self, event: FrameCaptured) -> None:
        self._frames.append([event.svg, event.hold_ms])
        table = self.query_one("#frames-table", DataTable)
        table.add_row(str(event.frame_num), str(event.hold_ms))

    def on_recording_done(self, _: RecordingDone) -> None:
        self._state = "done"
        lst = self.query_one("#steps-list", ListView)
        for j, item in enumerate(list(lst.query(ListItem))):
            item.query_one(Label).update(f"  ✓  {_step_label(self._tape.steps[j])}")

        n = len(self._frames)
        self.query_one("#status", Static).update(
            f"Done — {n} frame{'s' if n != 1 else ''} captured. "
            f"Edit timings below, then [e] to export."
        )
        self.query_one("#frames-table").add_class("visible")
        self.query_one("#export-panel").add_class("visible")

    def on_recording_failed(self, event: RecordingFailed) -> None:
        self._state = "ready"
        self.query_one("#status", Static).update(
            f"[bold red]Error:[/bold red] {event.error}"
        )

    # ------------------------------------------------------------------
    # Frame timing editor
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_row = event.cursor_row
        edit_bar = self.query_one("#edit-bar", Input)
        if self._selected_row < len(self._frames):
            edit_bar.add_class("visible")
            edit_bar.value = str(self._frames[self._selected_row][1])
            edit_bar.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "edit-bar":
            return
        if self._selected_row is None or self._selected_row >= len(self._frames):
            return
        try:
            new_ms = int(event.value)
        except ValueError:
            return

        self._frames[self._selected_row][1] = new_ms
        table = self.query_one("#frames-table", DataTable)
        # Refresh the row — DataTable rows are 0-indexed
        table.update_cell_at((self._selected_row, 1), str(new_ms))
        self.query_one("#frames-table").focus()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def action_focus_export(self) -> None:
        if self._state == "done":
            self.query_one("#export-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-btn":
            self._start_export()

    def _start_export(self) -> None:
        if not self._frames:
            self.query_one("#status", Static).update(
                "[bold red]No frames to export.[/bold red]"
            )
            return

        output = Path(self.query_one("#output-input", Input).value.strip() or str(self._output))
        watermark = self.query_one("#watermark-input", Input).value.strip()
        fmt = str(self.query_one("#format-select", Select).value)

        # Adjust extension to match format
        ext_map = {"gif": ".gif", "webp": ".webp", "apng": ".png"}
        if output.suffix.lower() not in ext_map.values():
            output = output.with_suffix(ext_map[fmt])

        wm_fn = None
        if watermark:
            from .overlay import make_watermark_fn
            wm_fn = make_watermark_fn(watermark)

        frames = [(svg, hold_ms) for svg, hold_ms in self._frames]
        gif_width = self._tape.gif_width

        self.query_one("#status", Static).update(f"Rendering {len(frames)} frame(s)…")

        self.run_worker(
            lambda: self._export_worker(frames, output, fmt, gif_width, wm_fn),
            thread=True,
        )

    def _export_worker(
        self,
        frames: list,
        output: Path,
        fmt: str,
        gif_width: int,
        wm_fn: Callable | None,
    ) -> None:
        try:
            from .formats import RENDERERS
            render_fn = RENDERERS[fmt]
            result = render_fn(frames, output, gif_width, wm_fn)
            size_kb = result.stat().st_size // 1024
            self.call_from_thread(self.post_message, ExportDone(str(result), size_kb))
        except Exception as exc:
            self.call_from_thread(self.post_message, ExportFailed(str(exc)))

    def on_export_done(self, event: ExportDone) -> None:
        self.query_one("#status", Static).update(
            f"[bold green]Saved {event.path} ({event.size_kb} KB)[/bold green]"
        )

    def on_export_failed(self, event: ExportFailed) -> None:
        self.query_one("#status", Static).update(
            f"[bold red]Export failed:[/bold red] {event.error}"
        )
