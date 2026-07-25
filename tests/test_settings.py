from __future__ import annotations

import stat
from pathlib import Path

from stt.settings import (
    COMMAND,
    CONTROL,
    OPTION,
    SHIFT,
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


def test_double_modifier_labels() -> None:
    assert HotkeyBinding.double_modifier(COMMAND).label == "⌘  ⌘"
    assert HotkeyBinding.double_modifier(OPTION).label == "⌥  ⌥"
    assert HotkeyBinding.double_modifier(CONTROL).label == "⌃  ⌃"
    assert HotkeyBinding.double_modifier(SHIFT).label == "⇧  ⇧"
    assert HotkeyBinding.double_key(35).label == "P  P"


def test_double_modifier_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    expected = AppSettings(hotkey=HotkeyBinding.double_modifier(CONTROL))

    save_settings(expected, path)

    assert load_settings(path) == expected


def test_double_key_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    expected = AppSettings(hotkey=HotkeyBinding.double_key(35))

    save_settings(expected, path)

    assert load_settings(path) == expected


def test_legacy_double_command_settings_are_migrated(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"activation_mode":"toggle","hotkey":{"kind":"double_command"}}',
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.hotkey == HotkeyBinding.double_modifier(COMMAND)
