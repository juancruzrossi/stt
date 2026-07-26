from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

COMMAND = 1 << 20
SHIFT = 1 << 17
CONTROL = 1 << 18
OPTION = 1 << 19
MODIFIER_MASK = COMMAND | SHIFT | CONTROL | OPTION
MODIFIER_KEY_CODES = {
    54: COMMAND,
    55: COMMAND,
    56: SHIFT,
    58: OPTION,
    59: CONTROL,
    60: SHIFT,
    61: OPTION,
    62: CONTROL,
}
DOUBLE_TAP_MODIFIERS = frozenset(MODIFIER_KEY_CODES.values())

KEY_NAMES = {
    0: "A",
    1: "S",
    2: "D",
    3: "F",
    4: "H",
    5: "G",
    6: "Z",
    7: "X",
    8: "C",
    9: "V",
    11: "B",
    12: "Q",
    13: "W",
    14: "E",
    15: "R",
    16: "Y",
    17: "T",
    18: "1",
    19: "2",
    20: "3",
    21: "4",
    22: "6",
    23: "5",
    24: "=",
    25: "9",
    26: "7",
    27: "–",
    28: "8",
    29: "0",
    30: "]",
    31: "O",
    32: "U",
    33: "[",
    34: "I",
    35: "P",
    37: "L",
    38: "J",
    39: "'",
    40: "K",
    41: ";",
    42: "\\",
    43: ",",
    44: "/",
    45: "N",
    46: "M",
    47: ".",
    49: "Space",
    50: "`",
    51: "Delete",
    53: "Escape",
    76: "Enter",
    96: "F5",
    97: "F6",
    98: "F7",
    99: "F3",
    100: "F8",
    101: "F9",
    103: "F11",
    109: "F10",
    111: "F12",
    118: "F4",
    120: "F2",
    122: "F1",
    123: "←",
    124: "→",
    125: "↓",
    126: "↑",
}


class ActivationMode(StrEnum):
    TOGGLE = "toggle"
    HOLD = "hold"


class ShortcutKind(StrEnum):
    DOUBLE_MODIFIER = "double_modifier"
    DOUBLE_KEY = "double_key"
    KEY_COMBINATION = "key_combination"


@dataclass(frozen=True)
class HotkeyBinding:
    kind: ShortcutKind = ShortcutKind.DOUBLE_MODIFIER
    key_code: int | None = None
    modifiers: int = COMMAND

    @classmethod
    def double_modifier(cls, modifier: int) -> HotkeyBinding:
        if modifier not in DOUBLE_TAP_MODIFIERS:
            raise ValueError("Unsupported double-tap modifier")
        return cls(
            kind=ShortcutKind.DOUBLE_MODIFIER,
            modifiers=modifier,
        )

    @classmethod
    def double_key(cls, key_code: int) -> HotkeyBinding:
        return cls(
            kind=ShortcutKind.DOUBLE_KEY,
            key_code=key_code,
            modifiers=0,
        )

    @classmethod
    def key_combination(cls, key_code: int, modifiers: int) -> HotkeyBinding:
        return cls(
            kind=ShortcutKind.KEY_COMBINATION,
            key_code=key_code,
            modifiers=modifiers & MODIFIER_MASK,
        )

    @property
    def label(self) -> str:
        if self.kind == ShortcutKind.DOUBLE_MODIFIER:
            symbol = {
                CONTROL: "⌃",
                OPTION: "⌥",
                SHIFT: "⇧",
                COMMAND: "⌘",
            }.get(self.modifiers)
            return f"{symbol}  {symbol}" if symbol else "Not Set"
        if self.kind == ShortcutKind.DOUBLE_KEY:
            if self.key_code is None:
                return "Not Set"
            key = KEY_NAMES.get(self.key_code, f"Key {self.key_code}")
            return f"{key}  {key}"
        if self.key_code is None:
            return "Not Set"

        symbols = (
            (CONTROL, "⌃"),
            (OPTION, "⌥"),
            (SHIFT, "⇧"),
            (COMMAND, "⌘"),
        )
        modifiers = "".join(
            symbol for flag, symbol in symbols if self.modifiers & flag
        )
        return f"{modifiers}{KEY_NAMES.get(self.key_code, f'Key {self.key_code}')}"


@dataclass(frozen=True)
class AppSettings:
    activation_mode: ActivationMode = ActivationMode.TOGGLE
    toggle_hotkey: HotkeyBinding | None = None
    hold_hotkey: HotkeyBinding | None = None

    @property
    def hotkey(self) -> HotkeyBinding | None:
        if self.activation_mode == ActivationMode.TOGGLE:
            return self.toggle_hotkey
        return self.hold_hotkey

    def with_hotkey(self, hotkey: HotkeyBinding) -> AppSettings:
        if self.activation_mode == ActivationMode.TOGGLE:
            return replace(self, toggle_hotkey=hotkey)
        return replace(self, hold_hotkey=hotkey)

    def with_activation_mode(self, mode: ActivationMode) -> AppSettings:
        return replace(self, activation_mode=mode)


def settings_path() -> Path:
    return Path.home() / "Library" / "Application Support" / "STT" / "settings.json"


def load_settings(path: Path | None = None) -> AppSettings:
    source = path or settings_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        mode = ActivationMode(payload["activation_mode"])
        toggle_hotkey = _load_hotkey(payload.get("toggle_hotkey"))
        hold_hotkey = _load_hotkey(payload.get("hold_hotkey"))
        legacy_hotkey = _load_hotkey(payload.get("hotkey"))
        if legacy_hotkey is not None:
            if mode == ActivationMode.TOGGLE:
                toggle_hotkey = legacy_hotkey
            else:
                hold_hotkey = legacy_hotkey
        return AppSettings(
            activation_mode=mode,
            toggle_hotkey=toggle_hotkey,
            hold_hotkey=hold_hotkey,
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    destination = path or settings_path()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload: dict[str, object] = {
        "activation_mode": settings.activation_mode.value,
    }
    if settings.toggle_hotkey is not None:
        payload["toggle_hotkey"] = _dump_hotkey(settings.toggle_hotkey)
    if settings.hold_hotkey is not None:
        payload["hold_hotkey"] = _dump_hotkey(settings.hold_hotkey)

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=".settings-",
        suffix=".json",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2)
            output.write("\n")
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _load_hotkey(payload: object) -> HotkeyBinding | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise TypeError("Invalid shortcut")

    kind_value = payload["kind"]
    if kind_value == "double_command":
        return HotkeyBinding.double_modifier(COMMAND)

    kind = ShortcutKind(kind_value)
    if kind == ShortcutKind.DOUBLE_MODIFIER:
        return HotkeyBinding.double_modifier(int(payload.get("modifiers", 0)))

    key_code = payload.get("key_code")
    if key_code is None:
        raise ValueError("Missing shortcut key")
    if kind == ShortcutKind.DOUBLE_KEY:
        return HotkeyBinding.double_key(int(key_code))
    return HotkeyBinding.key_combination(
        int(key_code),
        int(payload.get("modifiers", 0)),
    )


def _dump_hotkey(hotkey: HotkeyBinding) -> dict[str, int | str | None]:
    return {
        "kind": hotkey.kind.value,
        "key_code": hotkey.key_code,
        "modifiers": hotkey.modifiers,
    }
