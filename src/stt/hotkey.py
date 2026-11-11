from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from contextlib import suppress
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


class DoubleTapControlListener:
    """Linux/X11 listener: double-tap Ctrl (alone, without other keys) to toggle."""

    def __init__(
        self,
        on_toggle: Callable[[], None],
        *,
        max_interval: float = 0.45,
    ) -> None:
        self.on_toggle = on_toggle
        self.max_interval = max_interval
        self._last_release = 0.0
        self._ctrl_down = False
        self._chorded = False
        self._lock = threading.Lock()
        self._control: Any | None = None
        self._context: Any | None = None

    def run(self) -> None:
        xlib: Any = import_module("Xlib")
        display: Any = import_module("Xlib.display")
        record: Any = import_module("Xlib.ext.record")
        rq: Any = import_module("Xlib.protocol.rq")
        xk: Any = import_module("Xlib.XK")
        x: Any = xlib.X

        try:
            local = display.Display()
            self._control = display.Display()
        except Exception as exc:
            raise RuntimeError(
                "Global hotkey unavailable. A running X11 session is required."
            ) from exc
        ctrl_codes = {
            local.keysym_to_keycode(xk.XK_Control_L),
            local.keysym_to_keycode(xk.XK_Control_R),
        }
        context = local.record_create_context(
            0,
            [record.AllClients],
            [
                {
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0, 0, 0),
                    "ext_replies": (0, 0, 0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (x.KeyPress, x.KeyRelease),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }
            ],
        )
        self._context = context
        event_field = rq.EventField(None)

        def on_reply(reply: Any) -> None:
            if reply.category != record.FromServer or reply.client_swapped:
                return
            data = reply.data
            while data:
                key_event, data = event_field.parse_binary_value(
                    data, local.display, None, None
                )
                is_ctrl = key_event.detail in ctrl_codes
                if key_event.type == x.KeyPress:
                    if is_ctrl:
                        self._on_control_press()
                    else:
                        self._on_other_key()
                elif key_event.type == x.KeyRelease and is_ctrl:
                    self._on_control_release()

        try:
            local.record_enable_context(context, on_reply)
        finally:
            local.record_free_context(context)
            local.close()

    def stop(self) -> None:
        control = self._control
        if control is not None and self._context is not None:
            with suppress(Exception):
                control.record_disable_context(self._context)
                control.flush()

    def _on_control_press(self) -> None:
        with self._lock:
            if not self._ctrl_down:
                self._ctrl_down = True
                self._chorded = False

    def _on_other_key(self) -> None:
        with self._lock:
            if self._ctrl_down:
                self._chorded = True
            self._last_release = 0.0

    def _on_control_release(self) -> None:
        now = time.monotonic()
        should_toggle = False
        with self._lock:
            if not self._ctrl_down:
                # Ignore repeated releases so each physical tap counts once.
                return
            chorded = self._chorded
            self._ctrl_down = False
            self._chorded = False
            if chorded:
                self._last_release = 0.0
            elif now - self._last_release <= self.max_interval:
                should_toggle = True
                self._last_release = 0.0
            else:
                self._last_release = now

        if should_toggle:
            self.on_toggle()


def create_hotkey_listener(
    on_toggle: Callable[[], None],
    *,
    max_interval: float = 0.45,
) -> DoubleTapCommandListener | DoubleTapControlListener:
    if sys.platform.startswith("linux"):
        return DoubleTapControlListener(on_toggle, max_interval=max_interval)
    return DoubleTapCommandListener(on_toggle, max_interval=max_interval)


def hotkey_name() -> str:
    return "Ctrl" if sys.platform.startswith("linux") else "Command"
