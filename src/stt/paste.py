from __future__ import annotations

import platform
import time

import pyperclip
from pynput import keyboard


def read_clipboard() -> str:
    try:
        return pyperclip.paste()
    except pyperclip.PyperclipException:
        return ""


def write_clipboard(text: str) -> None:
    pyperclip.copy(text)


def paste_text(text: str, *, restore_clipboard: bool = True) -> None:
    previous = read_clipboard() if restore_clipboard else ""
    write_clipboard(text)

    controller = keyboard.Controller()
    modifier = keyboard.Key.cmd if platform.system() == "Darwin" else keyboard.Key.ctrl

    time.sleep(0.05)
    with controller.pressed(modifier):
        controller.press("v")
        controller.release("v")

    if restore_clipboard:
        time.sleep(0.7)
        if read_clipboard() == text:
            write_clipboard(previous)
