from __future__ import annotations

from importlib import import_module
import platform
import time
from types import ModuleType
from typing import Any

import pyperclip


EDITABLE_TEXT_ROLES = {
    "AXComboBox",
    "AXSearchField",
    "AXSecureTextField",
    "AXTextArea",
    "AXTextField",
}
TERMINAL_BUNDLE_ID = "com.apple.Terminal"


def _keyboard() -> ModuleType:
    return import_module("pynput.keyboard")


def _application_services() -> ModuleType:
    return import_module("ApplicationServices")


def _frontmost_application() -> Any:
    workspace = import_module("AppKit").NSWorkspace.sharedWorkspace()
    return workspace.frontmostApplication()


def read_clipboard() -> str:
    try:
        return pyperclip.paste()
    except pyperclip.PyperclipException:
        return ""


def write_clipboard(text: str) -> None:
    pyperclip.copy(text)


def deliver_text(
    text: str,
    *,
    input_was_focused: bool | None,
    restore_clipboard: bool = True,
) -> None:
    if input_was_focused is False:
        write_clipboard(text)
        return

    input_is_focused = has_focused_editable_field()
    if input_is_focused is False:
        write_clipboard(text)
        return
    paste_text(
        text,
        restore_clipboard=restore_clipboard and input_is_focused is True,
    )


def has_focused_editable_field() -> bool | None:
    if platform.system() != "Darwin":
        return None

    try:
        api = _application_services()
        application = _frontmost_application()
        application_element = api.AXUIElementCreateApplication(
            application.processIdentifier()
        )
        error, focused = api.AXUIElementCopyAttributeValue(
            application_element,
            api.kAXFocusedUIElementAttribute,
            None,
        )
        if error != 0 or focused is None:
            return False

        error, role = api.AXUIElementCopyAttributeValue(
            focused,
            api.kAXRoleAttribute,
            None,
        )
        if error != 0 or role not in EDITABLE_TEXT_ROLES:
            return False

        if (
            role == "AXTextArea"
            and application.bundleIdentifier() == TERMINAL_BUNDLE_ID
        ):
            return True

        for attribute in (api.kAXSelectedTextAttribute, api.kAXValueAttribute):
            error, settable = api.AXUIElementIsAttributeSettable(
                focused,
                attribute,
                None,
            )
            if error == 0 and settable:
                return True
    except Exception:  # noqa: BLE001
        return False

    return False


def paste_text(text: str, *, restore_clipboard: bool = True) -> None:
    previous = read_clipboard() if restore_clipboard else ""
    write_clipboard(text)

    keyboard = _keyboard()
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
