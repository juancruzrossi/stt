from __future__ import annotations

import json
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
        toggle_hotkey=HotkeyBinding.double_modifier(COMMAND),
        hold_hotkey=HotkeyBinding.key_combination(49, OPTION),
    )

    save_settings(expected, path)

    assert load_settings(path) == expected
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_shortcuts_are_unset_and_independent_by_default(tmp_path: Path) -> None:
    settings = AppSettings()

    assert settings.hotkey is None
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "activation_mode": "toggle"
    }

    settings = settings.with_hotkey(HotkeyBinding.double_modifier(COMMAND))
    settings = settings.with_activation_mode(ActivationMode.HOLD)
    assert settings.hotkey is None

    settings = settings.with_hotkey(HotkeyBinding.key_combination(49, OPTION))
    assert settings.hotkey == HotkeyBinding.key_combination(49, OPTION)
    settings = settings.with_activation_mode(ActivationMode.TOGGLE)
    assert settings.hotkey == HotkeyBinding.double_modifier(COMMAND)


def test_double_modifier_labels() -> None:
    assert HotkeyBinding.double_modifier(COMMAND).label == "⌘  ⌘"
    assert HotkeyBinding.double_modifier(OPTION).label == "⌥  ⌥"
    assert HotkeyBinding.double_modifier(CONTROL).label == "⌃  ⌃"
    assert HotkeyBinding.double_modifier(SHIFT).label == "⇧  ⇧"
    assert HotkeyBinding.double_key(35).label == "P  P"


def test_double_modifier_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    expected = AppSettings(
        toggle_hotkey=HotkeyBinding.double_modifier(CONTROL)
    )

    save_settings(expected, path)

    assert load_settings(path) == expected


def test_double_key_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    expected = AppSettings(toggle_hotkey=HotkeyBinding.double_key(35))

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
    assert settings.hold_hotkey is None
