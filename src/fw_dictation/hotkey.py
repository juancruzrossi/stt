from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from pynput import keyboard


SPECIAL_KEYS = {
    "ctrl": keyboard.Key.ctrl,
    "control": keyboard.Key.ctrl,
    "cmd": keyboard.Key.cmd,
    "command": keyboard.Key.cmd,
    "meta": keyboard.Key.cmd,
    "option": keyboard.Key.alt,
    "opt": keyboard.Key.alt,
    "alt": keyboard.Key.alt,
    "shift": keyboard.Key.shift,
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "return": keyboard.Key.enter,
    "tab": keyboard.Key.tab,
}

for number in range(1, 21):
    SPECIAL_KEYS[f"f{number}"] = getattr(keyboard.Key, f"f{number}")


@dataclass(frozen=True)
class Hotkey:
    raw: str
    keys: frozenset[object]


def parse_hotkey(value: str) -> Hotkey:
    keys: set[object] = set()
    for part in value.lower().replace("+", " ").split():
        if part in SPECIAL_KEYS:
            keys.add(SPECIAL_KEYS[part])
        elif len(part) == 1:
            keys.add(keyboard.KeyCode.from_char(part))
        else:
            raise ValueError(f"Tecla no soportada en hotkey: {part}")
    if not keys:
        raise ValueError("La hotkey no puede estar vacia.")
    return Hotkey(raw=value, keys=frozenset(keys))


class HoldHotkeyListener:
    def __init__(self, hotkey: Hotkey, on_start, on_stop, *, suppress: bool = False) -> None:  # noqa: ANN001
        self.hotkey = hotkey
        self.on_start = on_start
        self.on_stop = on_stop
        self.suppress = suppress
        self._pressed: set[object] = set()
        self._active = False
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None

    def run(self) -> None:
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=self.suppress,
        ) as listener:
            self._listener = listener
            listener.join()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def _canonical(self, key) -> object:  # noqa: ANN001
        if self._listener is None:
            return key
        return self._listener.canonical(key)

    def _on_press(self, key) -> None:  # noqa: ANN001
        with self._lock:
            self._pressed.add(self._canonical(key))
            should_start = not self._active and self.hotkey.keys.issubset(self._pressed)
            if should_start:
                self._active = True
        if should_start:
            self.on_start()

    def _on_release(self, key) -> None:  # noqa: ANN001
        with self._lock:
            self._pressed.discard(self._canonical(key))
            should_stop = self._active and not self.hotkey.keys.issubset(self._pressed)
            if should_stop:
                self._active = False
        if should_stop:
            self.on_stop()


class DoubleTapToggleListener:
    def __init__(
        self,
        key: str,
        on_toggle,
        *,
        max_interval: float = 0.45,
        suppress: bool = False,
    ) -> None:  # noqa: ANN001
        self.key = parse_single_key(key)
        self.on_toggle = on_toggle
        self.max_interval = max_interval
        self.suppress = suppress
        self._last_release = 0.0
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None

    def run(self) -> None:
        with keyboard.Listener(
            on_release=self._on_release,
            suppress=self.suppress,
        ) as listener:
            self._listener = listener
            listener.join()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def _canonical(self, key) -> object:  # noqa: ANN001
        if self._listener is None:
            return key
        return self._listener.canonical(key)

    def _on_release(self, key) -> None:  # noqa: ANN001
        now = time.monotonic()
        if self._canonical(key) != self.key:
            return

        should_toggle = False
        with self._lock:
            if now - self._last_release <= self.max_interval:
                should_toggle = True
                self._last_release = 0.0
            else:
                self._last_release = now

        if should_toggle:
            self.on_toggle()


def parse_single_key(value: str) -> object:
    hotkey = parse_hotkey(value)
    if len(hotkey.keys) != 1:
        raise ValueError("El modo double-tap acepta una sola tecla.")
    return next(iter(hotkey.keys))
