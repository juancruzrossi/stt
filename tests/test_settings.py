from __future__ import annotations

import stat
from pathlib import Path

from stt.settings import (
    OPTION,
    ActivationMode,
    AppSettings,
    HotkeyBinding,
    load_settings,
    save_settings,
)


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    expected = AppSettings(
        activation_mode=ActivationMode.HOLD,
        hotkey=HotkeyBinding.key_combination(49, OPTION),
    )

    save_settings(expected, path)

    assert load_settings(path) == expected
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_hold_mode_gets_usable_default_shortcut() -> None:
    settings = AppSettings(activation_mode=ActivationMode.HOLD).normalized()

    assert settings.hotkey == HotkeyBinding.key_combination(49, OPTION)
    assert settings.hotkey.label == "⌥Space"
