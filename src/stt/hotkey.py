from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from importlib import import_module
from types import ModuleType
from typing import Any

from .settings import (
    COMMAND,
    MODIFIER_MASK,
    ActivationMode,
    AppSettings,
    ShortcutKind,
)

COMMAND_KEY_CODES = {54, 55}
KEY_DOWN = 10
KEY_UP = 11
FLAGS_CHANGED = 12


def _application_services() -> ModuleType:
    return import_module("ApplicationServices")


def _core_foundation() -> ModuleType:
    return import_module("CoreFoundation")


def ensure_listen_event_access() -> None:
    api = _application_services()
    if not api.CGPreflightListenEventAccess():
        api.CGRequestListenEventAccess()
        raise RuntimeError("Input Monitoring required")


class GlobalHotkeyListener:
    def __init__(
        self,
        settings: AppSettings,
        *,
        on_toggle: Callable[[], None],
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        max_interval: float = 0.45,
    ) -> None:
        self.settings = settings.normalized()
        self.on_toggle = on_toggle
        self.on_start = on_start
        self.on_stop = on_stop
        self.max_interval = max_interval
        self._last_command_release = 0.0
        self._command_was_chorded = False
        self._shortcut_is_pressed = False
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._event_tap: Any | None = None
        self._run_loop: Any | None = None
        self._actions: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._defer_actions = False

    def run(self) -> None:
        self._stopped.clear()
        api = _application_services()
        core = _core_foundation()
        ensure_listen_event_access()

        event_mask = (
            api.CGEventMaskBit(api.kCGEventFlagsChanged)
            | api.CGEventMaskBit(api.kCGEventKeyDown)
            | api.CGEventMaskBit(api.kCGEventKeyUp)
        )
        event_tap = api.CGEventTapCreate(
            api.kCGSessionEventTap,
            api.kCGHeadInsertEventTap,
            api.kCGEventTapOptionListenOnly,
            event_mask,
            self._handle_event,
            None,
        )
        if event_tap is None:
            raise RuntimeError(
                "Global hotkey unavailable. Enable Input Monitoring and Accessibility."
            )

        source = core.CFMachPortCreateRunLoopSource(None, event_tap, 0)
        run_loop = core.CFRunLoopGetCurrent()
        self._event_tap = event_tap
        self._run_loop = run_loop
        core.CFRunLoopAddSource(run_loop, source, core.kCFRunLoopCommonModes)
        api.CGEventTapEnable(event_tap, True)
        action_worker = threading.Thread(
            target=self._run_actions,
            name="stt-hotkey-actions",
            daemon=True,
        )
        self._defer_actions = True
        action_worker.start()
        try:
            while not self._stopped.is_set():
                core.CFRunLoopRunInMode(
                    core.kCFRunLoopDefaultMode,
                    0.1,
                    False,
                )
        finally:
            self._defer_actions = False
            self._actions.put(None)
            action_worker.join(timeout=2)
            self._event_tap = None
            self._run_loop = None

    def stop(self) -> None:
        self._stopped.set()
        if self._run_loop is not None:
            _core_foundation().CFRunLoopStop(self._run_loop)

    def _handle_event(
        self,
        _proxy: object,
        event_type: int,
        event: Any,
        _refcon: object,
    ) -> Any:
        api = _application_services()
        if event_type in {
            api.kCGEventTapDisabledByTimeout,
            api.kCGEventTapDisabledByUserInput,
        }:
            if self._event_tap is not None:
                api.CGEventTapEnable(self._event_tap, True)
            return event

        key_code = int(
            api.CGEventGetIntegerValueField(
                event,
                api.kCGKeyboardEventKeycode,
            )
        )
        flags = int(api.CGEventGetFlags(event))
        is_repeat = bool(
            api.CGEventGetIntegerValueField(
                event,
                api.kCGKeyboardEventAutorepeat,
            )
        )
        self.handle_event(
            event_type=event_type,
            key_code=key_code,
            flags=flags,
            is_repeat=is_repeat,
        )
        return event

    def handle_event(
        self,
        *,
        event_type: int,
        key_code: int,
        flags: int,
        is_repeat: bool = False,
    ) -> None:
        hotkey = self.settings.hotkey
        if hotkey.kind == ShortcutKind.DOUBLE_COMMAND:
            self._handle_double_command(event_type, key_code, flags)
            return

        if hotkey.key_code is None or key_code != hotkey.key_code:
            if event_type == KEY_DOWN and flags & COMMAND:
                self._command_was_chorded = True
            return

        if event_type == KEY_DOWN:
            if is_repeat or flags & MODIFIER_MASK != hotkey.modifiers:
                return
            if self.settings.activation_mode == ActivationMode.TOGGLE:
                self._invoke(self.on_toggle)
            elif not self._shortcut_is_pressed:
                self._shortcut_is_pressed = True
                self._invoke(self.on_start)
        elif (
            event_type == KEY_UP
            and self.settings.activation_mode == ActivationMode.HOLD
            and self._shortcut_is_pressed
        ):
            self._shortcut_is_pressed = False
            self._invoke(self.on_stop)

    def _handle_double_command(
        self,
        event_type: int,
        key_code: int,
        flags: int,
    ) -> None:
        if event_type == KEY_DOWN and flags & COMMAND:
            self._command_was_chorded = True
            return
        if (
            event_type != FLAGS_CHANGED
            or key_code not in COMMAND_KEY_CODES
            or flags & COMMAND
        ):
            return
        if self._command_was_chorded:
            self._command_was_chorded = False
            self._last_command_release = 0.0
            return

        now = time.monotonic()
        with self._lock:
            if now - self._last_command_release <= self.max_interval:
                self._last_command_release = 0.0
                self._invoke(self.on_toggle)
            else:
                self._last_command_release = now

    def _invoke(self, action: Callable[[], None]) -> None:
        if self._defer_actions:
            self._actions.put(action)
        else:
            action()

    def _run_actions(self) -> None:
        while True:
            action = self._actions.get()
            if action is None:
                return
            action()
