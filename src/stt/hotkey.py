from __future__ import annotations

import threading
import time
from collections.abc import Callable
from importlib import import_module
from types import ModuleType
from typing import Any

COMMAND_KEY_CODES = {54, 55}


def _application_services() -> ModuleType:
    return import_module("ApplicationServices")


def _core_foundation() -> ModuleType:
    return import_module("CoreFoundation")


class DoubleTapCommandListener:
    def __init__(
        self,
        on_toggle: Callable[[], None],
        *,
        max_interval: float = 0.45,
    ) -> None:
        self.on_toggle = on_toggle
        self.max_interval = max_interval
        self._last_release = 0.0
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._event_tap: Any | None = None
        self._run_loop: Any | None = None

    def run(self) -> None:
        self._stopped.clear()
        api = _application_services()
        core = _core_foundation()
        event_tap = api.CGEventTapCreate(
            api.kCGSessionEventTap,
            api.kCGHeadInsertEventTap,
            api.kCGEventTapOptionListenOnly,
            api.CGEventMaskBit(api.kCGEventFlagsChanged),
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
        try:
            while not self._stopped.is_set():
                core.CFRunLoopRunInMode(
                    core.kCFRunLoopDefaultMode,
                    0.1,
                    False,
                )
        finally:
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
        if event_type != api.kCGEventFlagsChanged:
            return event

        key_code = api.CGEventGetIntegerValueField(
            event,
            api.kCGKeyboardEventKeycode,
        )
        flags = api.CGEventGetFlags(event)
        if key_code in COMMAND_KEY_CODES and not flags & api.kCGEventFlagMaskCommand:
            self._on_command_release()
        return event

    def _on_command_release(self) -> None:
        now = time.monotonic()
        should_toggle = False
        with self._lock:
            if now - self._last_release <= self.max_interval:
                should_toggle = True
                self._last_release = 0.0
            else:
                self._last_release = now

        if should_toggle:
            self.on_toggle()
