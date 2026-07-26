from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from importlib import import_module
from types import ModuleType
from typing import Any

from .settings import (
    MODIFIER_KEY_CODES,
    MODIFIER_MASK,
    ActivationMode,
    AppSettings,
    ShortcutKind,
)

KEY_DOWN = 10
KEY_UP = 11
FLAGS_CHANGED = 12
REPLAY_MARKER = 0x535454


def _application_services() -> ModuleType:
    return import_module("ApplicationServices")


def _core_foundation() -> ModuleType:
    return import_module("CoreFoundation")


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
        self._last_tap_at = 0.0
        self._modifier_was_chorded = False
        self._shortcut_is_pressed = False
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._event_tap: Any | None = None
        self._run_loop: Any | None = None
        self._pending_key_events: list[Any] = []
        self._pending_key_timer: threading.Timer | None = None
        self._suppress_key_up = False
        self._actions: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._defer_actions = False

    def run(self) -> None:
        self._stopped.clear()
        api = _application_services()
        core = _core_foundation()
        if not api.AXIsProcessTrusted():
            raise RuntimeError("Accessibility required")

        event_mask = (
            api.CGEventMaskBit(api.kCGEventFlagsChanged)
            | api.CGEventMaskBit(api.kCGEventKeyDown)
            | api.CGEventMaskBit(api.kCGEventKeyUp)
        )
        tap_option = (
            api.kCGEventTapOptionDefault
            if self.settings.hotkey.kind == ShortcutKind.DOUBLE_KEY
            else api.kCGEventTapOptionListenOnly
        )
        event_tap = api.CGEventTapCreate(
            api.kCGSessionEventTap,
            api.kCGHeadInsertEventTap,
            tap_option,
            event_mask,
            self._handle_event,
            None,
        )
        if event_tap is None:
            raise RuntimeError("Global hotkey unavailable. Enable Accessibility.")

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
        self._replay_pending_key()
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

        if (
            int(
                api.CGEventGetIntegerValueField(
                    event,
                    api.kCGEventSourceUserData,
                )
            )
            == REPLAY_MARKER
        ):
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
        if self.settings.hotkey.kind == ShortcutKind.DOUBLE_KEY:
            return self._intercept_double_key(
                event_type=event_type,
                key_code=key_code,
                flags=flags,
                is_repeat=is_repeat,
                event=event,
                api=api,
            )

        self.handle_event(
            event_type=event_type,
            key_code=key_code,
            flags=flags,
            is_repeat=is_repeat,
        )
        return event

    def _intercept_double_key(
        self,
        *,
        event_type: int,
        key_code: int,
        flags: int,
        is_repeat: bool,
        event: Any,
        api: ModuleType,
    ) -> Any | None:
        hotkey = self.settings.hotkey
        is_target = key_code == hotkey.key_code and not flags & MODIFIER_MASK

        if event_type == KEY_UP and is_target:
            with self._lock:
                if self._suppress_key_up:
                    self._suppress_key_up = False
                    return None
                if self._pending_key_events:
                    self._pending_key_events.append(
                        self._copy_for_replay(api, event)
                    )
                    return None

        if event_type == KEY_DOWN and is_target and not is_repeat:
            now = time.monotonic()
            replay: list[Any] = []
            toggle = False
            with self._lock:
                if (
                    self._pending_key_events
                    and now - self._last_tap_at <= self.max_interval
                ):
                    self._take_pending_key_locked()
                    self._suppress_key_up = True
                    toggle = True
                else:
                    replay = self._take_pending_key_locked()
                    self._pending_key_events = [
                        self._copy_for_replay(api, event)
                    ]
                    self._last_tap_at = now
                    self._pending_key_timer = threading.Timer(
                        self.max_interval,
                        self._replay_pending_key,
                    )
                    self._pending_key_timer.daemon = True
                    self._pending_key_timer.start()
            self._post_replay_events(api, replay)
            if toggle:
                self._invoke(self.on_toggle)
            return None

        with self._lock:
            has_pending_key = bool(self._pending_key_events)
        if has_pending_key:
            self._replay_pending_key(event)
            return None
        return event

    def _copy_for_replay(self, api: ModuleType, event: Any) -> Any:
        copied = api.CGEventCreateCopy(event)
        api.CGEventSetIntegerValueField(
            copied,
            api.kCGEventSourceUserData,
            REPLAY_MARKER,
        )
        return copied

    def _replay_pending_key(self, extra_event: Any | None = None) -> None:
        api = _application_services()
        with self._lock:
            events = self._take_pending_key_locked()
            if extra_event is not None:
                events.append(self._copy_for_replay(api, extra_event))
        self._post_replay_events(api, events)

    def _take_pending_key_locked(self) -> list[Any]:
        events = self._pending_key_events
        self._pending_key_events = []
        self._clear_pending_key_locked()
        return events

    def _clear_pending_key_locked(self) -> None:
        if self._pending_key_timer is not None:
            self._pending_key_timer.cancel()
            self._pending_key_timer = None
        self._last_tap_at = 0.0

    @staticmethod
    def _post_replay_events(api: ModuleType, events: list[Any]) -> None:
        for event in events:
            api.CGEventPost(api.kCGHIDEventTap, event)

    def handle_event(
        self,
        *,
        event_type: int,
        key_code: int,
        flags: int,
        is_repeat: bool = False,
    ) -> None:
        hotkey = self.settings.hotkey
        if hotkey.kind == ShortcutKind.DOUBLE_MODIFIER:
            self._handle_double_modifier(event_type, key_code, flags)
            return
        if hotkey.kind == ShortcutKind.DOUBLE_KEY:
            self._handle_double_key(
                event_type,
                key_code,
                flags,
                is_repeat=is_repeat,
            )
            return

        if hotkey.key_code is None or key_code != hotkey.key_code:
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

    def _handle_double_modifier(
        self,
        event_type: int,
        key_code: int,
        flags: int,
    ) -> None:
        modifier = self.settings.hotkey.modifiers
        key_modifier = MODIFIER_KEY_CODES.get(key_code)
        other_modifiers = flags & (MODIFIER_MASK & ~modifier)

        if event_type == KEY_DOWN and flags & modifier:
            self._modifier_was_chorded = True
            return
        if (
            event_type == FLAGS_CHANGED
            and key_modifier != modifier
            and flags & modifier
        ):
            self._modifier_was_chorded = True
            return
        if (
            event_type != FLAGS_CHANGED
            or key_modifier != modifier
            or flags & modifier
        ):
            return
        if self._modifier_was_chorded or other_modifiers:
            self._modifier_was_chorded = False
            self._last_tap_at = 0.0
            return

        self._register_tap()

    def _handle_double_key(
        self,
        event_type: int,
        key_code: int,
        flags: int,
        *,
        is_repeat: bool,
    ) -> None:
        hotkey = self.settings.hotkey
        if (
            event_type != KEY_DOWN
            or is_repeat
            or key_code != hotkey.key_code
            or flags & MODIFIER_MASK
        ):
            return

        self._register_tap()

    def _register_tap(self) -> None:
        now = time.monotonic()
        with self._lock:
            if now - self._last_tap_at <= self.max_interval:
                self._last_tap_at = 0.0
                self._invoke(self.on_toggle)
            else:
                self._last_tap_at = now

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
