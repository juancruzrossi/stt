from __future__ import annotations

import pytest

from stt import hotkey
from stt.settings import OPTION, ActivationMode, AppSettings, HotkeyBinding


def test_double_command_release_toggles_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toggles: list[None] = []
    times = iter([1.0, 1.3])
    monkeypatch.setattr(hotkey.time, "monotonic", lambda: next(times))
    listener = hotkey.GlobalHotkeyListener(
        AppSettings(),
        on_toggle=lambda: toggles.append(None),
        on_start=lambda: None,
        on_stop=lambda: None,
    )

    listener.handle_event(
        event_type=hotkey.FLAGS_CHANGED,
        key_code=55,
        flags=0,
    )
    listener.handle_event(
        event_type=hotkey.FLAGS_CHANGED,
        key_code=55,
        flags=0,
    )

    assert toggles == [None]


def test_custom_toggle_ignores_repeated_keydown() -> None:
    toggles: list[None] = []
    listener = hotkey.GlobalHotkeyListener(
        AppSettings(hotkey=HotkeyBinding.key_combination(49, OPTION)),
        on_toggle=lambda: toggles.append(None),
        on_start=lambda: None,
        on_stop=lambda: None,
    )

    listener.handle_event(
        event_type=hotkey.KEY_DOWN,
        key_code=49,
        flags=OPTION,
    )
    listener.handle_event(
        event_type=hotkey.KEY_DOWN,
        key_code=49,
        flags=OPTION,
        is_repeat=True,
    )

    assert toggles == [None]


def test_hold_shortcut_starts_and_stops() -> None:
    states: list[str] = []
    listener = hotkey.GlobalHotkeyListener(
        AppSettings(
            activation_mode=ActivationMode.HOLD,
            hotkey=HotkeyBinding.key_combination(49, OPTION),
        ),
        on_toggle=lambda: None,
        on_start=lambda: states.append("start"),
        on_stop=lambda: states.append("stop"),
    )

    listener.handle_event(
        event_type=hotkey.KEY_DOWN,
        key_code=49,
        flags=OPTION,
    )
    listener.handle_event(
        event_type=hotkey.KEY_UP,
        key_code=49,
        flags=0,
    )

    assert states == ["start", "stop"]


def test_event_callback_defers_dictation_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toggles: list[None] = []
    times = iter([1.0, 1.3])
    monkeypatch.setattr(hotkey.time, "monotonic", lambda: next(times))
    listener = hotkey.GlobalHotkeyListener(
        AppSettings(),
        on_toggle=lambda: toggles.append(None),
        on_start=lambda: None,
        on_stop=lambda: None,
    )
    listener._defer_actions = True

    for _ in range(2):
        listener.handle_event(
            event_type=hotkey.FLAGS_CHANGED,
            key_code=55,
            flags=0,
        )

    assert toggles == []
    action = listener._actions.get_nowait()
    assert action is not None
    action()
    assert toggles == [None]


def test_disabled_event_tap_is_reenabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled: list[object] = []

    class FakeApplicationServices:
        kCGEventTapDisabledByTimeout = -2
        kCGEventTapDisabledByUserInput = -1

        @staticmethod
        def CGEventTapEnable(event_tap: object, enabled_value: bool) -> None:
            if enabled_value:
                enabled.append(event_tap)

    listener = hotkey.GlobalHotkeyListener(
        AppSettings(),
        on_toggle=lambda: None,
        on_start=lambda: None,
        on_stop=lambda: None,
    )
    event_tap = object()
    listener._event_tap = event_tap
    monkeypatch.setattr(
        hotkey,
        "_application_services",
        lambda: FakeApplicationServices,
    )

    event = object()
    assert listener._handle_event(None, -2, event, None) is event
    assert enabled == [event_tap]
