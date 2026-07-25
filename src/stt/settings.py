from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

COMMAND = 1 << 20
SHIFT = 1 << 17
CONTROL = 1 << 18
OPTION = 1 << 19
MODIFIER_MASK = COMMAND | SHIFT | CONTROL | OPTION

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
    DOUBLE_COMMAND = "double_command"
    KEY_COMBINATION = "key_combination"


@dataclass(frozen=True)
class HotkeyBinding:
    kind: ShortcutKind = ShortcutKind.DOUBLE_COMMAND
    key_code: int | None = None
    modifiers: int = 0

    @classmethod
    def key_combination(cls, key_code: int, modifiers: int) -> HotkeyBinding:
        return cls(
            kind=ShortcutKind.KEY_COMBINATION,
            key_code=key_code,
            modifiers=modifiers & MODIFIER_MASK,
        )

    @property
    def label(self) -> str:
        if self.kind == ShortcutKind.DOUBLE_COMMAND:
            return "⌘  ⌘"
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
    hotkey: HotkeyBinding = HotkeyBinding()

    def normalized(self) -> AppSettings:
        if (
            self.activation_mode == ActivationMode.HOLD
            and self.hotkey.kind == ShortcutKind.DOUBLE_COMMAND
        ):
            return AppSettings(
                activation_mode=ActivationMode.HOLD,
                hotkey=HotkeyBinding.key_combination(49, OPTION),
            )
        return self


def settings_path() -> Path:
    return Path.home() / "Library" / "Application Support" / "STT" / "settings.json"


def load_settings(path: Path | None = None) -> AppSettings:
    source = path or settings_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        hotkey_payload = payload["hotkey"]
        settings = AppSettings(
            activation_mode=ActivationMode(payload["activation_mode"]),
            hotkey=HotkeyBinding(
                kind=ShortcutKind(hotkey_payload["kind"]),
                key_code=hotkey_payload.get("key_code"),
                modifiers=int(hotkey_payload.get("modifiers", 0)),
            ),
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return AppSettings()
    return settings.normalized()


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    destination = path or settings_path()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    normalized = settings.normalized()
    payload = asdict(normalized)
    payload["activation_mode"] = normalized.activation_mode.value
    payload["hotkey"]["kind"] = normalized.hotkey.kind.value

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
