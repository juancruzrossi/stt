from __future__ import annotations

import time
from importlib import import_module
from types import ModuleType
from typing import Any

EDITABLE_TEXT_ROLES = {
    "AXComboBox",
    "AXSearchField",
    "AXSecureTextField",
    "AXTextArea",
    "AXTextField",
}
TERMINAL_BUNDLE_ID = "com.apple.Terminal"
V_KEY_CODE = 9


def _application_services() -> ModuleType:
    return import_module("ApplicationServices")


def _appkit() -> ModuleType:
    return import_module("AppKit")


def _frontmost_application() -> Any:
    workspace = _appkit().NSWorkspace.sharedWorkspace()
    return workspace.frontmostApplication()


def read_clipboard() -> str:
    appkit = _appkit()
    pasteboard = appkit.NSPasteboard.generalPasteboard()
    return pasteboard.stringForType_(appkit.NSPasteboardTypeString) or ""


def write_clipboard(text: str) -> None:
    appkit = _appkit()
    pasteboard = appkit.NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, appkit.NSPasteboardTypeString)


def deliver_text(
    text: str,
    *,
    input_was_focused: bool,
    restore_clipboard: bool = True,
) -> None:
    if not input_was_focused:
        write_clipboard(text)
        return

    if not has_focused_editable_field():
        write_clipboard(text)
        return
    paste_text(text, restore_clipboard=restore_clipboard)


def has_focused_editable_field() -> bool:
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

        error, is_focused = api.AXUIElementCopyAttributeValue(
            focused,
            api.kAXFocusedAttribute,
            None,
        )
        if error != 0 or not is_focused:
            return False

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

    time.sleep(0.05)
    _post_command_v()

    if restore_clipboard:
        time.sleep(0.7)
        if read_clipboard() == text:
            write_clipboard(previous)


def _post_command_v() -> None:
    api = _application_services()
    source = api.CGEventSourceCreate(api.kCGEventSourceStateCombinedSessionState)
    for is_pressed in (True, False):
        event = api.CGEventCreateKeyboardEvent(source, V_KEY_CODE, is_pressed)
        api.CGEventSetFlags(event, api.kCGEventFlagMaskCommand)
        api.CGEventPost(api.kCGHIDEventTap, event)
