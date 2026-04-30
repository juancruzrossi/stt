from __future__ import annotations

import threading
import time

from pynput import keyboard


KEYS = {
    "ctrl": keyboard.Key.ctrl,
    "cmd": keyboard.Key.cmd,
}


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
    if key := KEYS.get(value.lower()):
        return key
    raise ValueError(f"Unsupported trigger key: {value}")
