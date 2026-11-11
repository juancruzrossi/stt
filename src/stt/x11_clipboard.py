"""Minimal X11 clipboard owner and paste shortcut (no xclip/xdotool needed).

The process that sets the clipboard must keep answering selection requests,
so a background thread serves the text for as long as ``stt listen`` runs.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from Xlib import XK, X, Xatom, display
from Xlib.ext import xtest
from Xlib.protocol import event

POLL_SECONDS = 0.02
_owner: ClipboardOwner | None = None
_owner_lock = threading.Lock()


class ClipboardOwner:
    def __init__(self) -> None:
        self._display: Any = display.Display()
        self._window = self._display.screen().root.create_window(
            0, 0, 1, 1, 0, X.CopyFromParent
        )
        intern = self._display.intern_atom
        self._clipboard = intern("CLIPBOARD")
        self._targets = intern("TARGETS")
        self._text_targets = {
            intern("UTF8_STRING"),
            intern("text/plain;charset=utf-8"),
            intern("TEXT"),
            Xatom.STRING,
        }
        self._data = b""
        self._lock = threading.Lock()
        threading.Thread(target=self._serve, daemon=True).start()

    def set_text(self, text: str) -> None:
        with self._lock:
            self._data = text.encode("utf-8")
            for selection in (self._clipboard, Xatom.PRIMARY):
                self._window.set_selection_owner(selection, X.CurrentTime)
            self._display.flush()

    def _serve(self) -> None:
        while True:
            with self._lock:
                while self._display.pending_events():
                    self._handle(self._display.next_event())
            time.sleep(POLL_SECONDS)

    def _handle(self, request: Any) -> None:
        if request.type != X.SelectionRequest:
            return
        prop = request.property or request.target
        requestor = request.requestor
        if request.target == self._targets:
            atoms = [self._targets, *self._text_targets]
            requestor.change_property(prop, Xatom.ATOM, 32, atoms)
        elif request.target in self._text_targets:
            requestor.change_property(prop, request.target, 8, self._data)
        else:
            prop = X.NONE
        notify = event.SelectionNotify(
            time=request.time,
            requestor=requestor,
            selection=request.selection,
            target=request.target,
            property=prop,
        )
        requestor.send_event(notify)
        self._display.flush()


def write_clipboard(text: str) -> None:
    global _owner
    with _owner_lock:
        if _owner is None:
            _owner = ClipboardOwner()
        owner = _owner
    owner.set_text(text)


def send_paste_shortcut() -> None:
    """Shift+Insert pastes the clipboard in terminals and GUI apps alike."""
    conn: Any = display.Display()
    try:
        shift = conn.keysym_to_keycode(XK.XK_Shift_L)
        insert = conn.keysym_to_keycode(XK.XK_Insert)
        xtest.fake_input(conn, X.KeyPress, shift)
        xtest.fake_input(conn, X.KeyPress, insert)
        xtest.fake_input(conn, X.KeyRelease, insert)
        xtest.fake_input(conn, X.KeyRelease, shift)
        conn.sync()
    finally:
        conn.close()


def paste_text(text: str) -> None:
    write_clipboard(text)
    time.sleep(0.05)
    send_paste_shortcut()
