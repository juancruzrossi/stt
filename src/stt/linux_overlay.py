"""Small always-on-top "Listening…" pill for Linux (X11), driven over stdin.

Reads the same line protocol as the macOS overlay: ``listening``,
``processing``, ``hide`` or a float RMS level. Exits when stdin closes.
"""

from __future__ import annotations

import os
import sys
from contextlib import suppress
from typing import Any

WIDTH = 184
HEIGHT = 46
BOTTOM_MARGIN = 60
POLL_MS = 33
BACKGROUND = "#1c1c1e"
TEXT = "#f2f2f7"
LISTENING_DOT = "#ff453a"
PROCESSING_DOT = "#ffd60a"
LEVEL_BAR = "#30d158"
LABELS = {"listening": "Listening...", "processing": "Processing..."}


def _normalized_level(rms: float) -> float:
    return min(1.0, max(0.0, (rms - 0.003) / 0.07))


def run_linux_overlay() -> None:
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    with suppress(tk.TclError):
        root.attributes("-type", "notification")
    with suppress(tk.TclError):
        root.attributes("-alpha", 0.92)
    root.configure(background=BACKGROUND)

    x = (root.winfo_screenwidth() - WIDTH) // 2
    y = root.winfo_screenheight() - HEIGHT - BOTTOM_MARGIN
    root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    canvas = tk.Canvas(
        root,
        width=WIDTH,
        height=HEIGHT,
        background=BACKGROUND,
        highlightthickness=0,
    )
    canvas.pack()
    dot = canvas.create_oval(16, 17, 28, 29, fill=LISTENING_DOT, outline="")
    label = canvas.create_text(
        40, 19, anchor="w", text=LABELS["listening"], fill=TEXT,
        font=("Sans", 11, "bold"),
    )
    bar_bg = canvas.create_rectangle(40, 32, WIDTH - 16, 35, fill="#3a3a3c", outline="")
    bar = canvas.create_rectangle(40, 32, 40, 35, fill=LEVEL_BAR, outline="")
    state: dict[str, Any] = {"visible": False, "level": 0.0, "buffer": b""}

    input_fd = sys.stdin.buffer.fileno()
    os.set_blocking(input_fd, False)

    def set_state(name: str) -> None:
        canvas.itemconfigure(label, text=LABELS[name])
        canvas.itemconfigure(
            dot, fill=LISTENING_DOT if name == "listening" else PROCESSING_DOT
        )
        bar_state = "normal" if name == "listening" else "hidden"
        canvas.itemconfigure(bar, state=bar_state)
        canvas.itemconfigure(bar_bg, state=bar_state)
        if not state["visible"]:
            state["visible"] = True
            root.deiconify()
            root.lift()

    def hide() -> None:
        if state["visible"]:
            state["visible"] = False
            state["level"] = 0.0
            root.withdraw()

    def tick() -> None:
        try:
            chunk: bytes | None = os.read(input_fd, 4096)
        except BlockingIOError:
            chunk = None
        except OSError:
            chunk = b""
        if chunk == b"":
            root.destroy()
            return
        if chunk:
            lines = (state["buffer"] + chunk).split(b"\n")
            state["buffer"] = lines.pop()
            for line in lines:
                if line in {b"listening", b"processing"}:
                    set_state(line.decode())
                elif line == b"hide":
                    hide()
                else:
                    with suppress(ValueError):
                        target = _normalized_level(float(line))
                        state["level"] = state["level"] * 0.5 + target * 0.5
        if state["visible"]:
            width = (WIDTH - 56) * state["level"]
            canvas.coords(bar, 40, 32, 40 + width, 35)
        root.after(POLL_MS, tick)

    root.after(POLL_MS, tick)
    root.mainloop()
