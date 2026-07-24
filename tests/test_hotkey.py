from __future__ import annotations

import pytest

from stt import hotkey


def test_double_command_release_toggles_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toggles: list[None] = []
    times = iter([1.0, 1.3])
    monkeypatch.setattr(hotkey.time, "monotonic", lambda: next(times))
    listener = hotkey.DoubleTapCommandListener(lambda: toggles.append(None))

    listener._on_command_release()
    listener._on_command_release()

    assert toggles == [None]
