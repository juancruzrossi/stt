from __future__ import annotations

import sys
import time

import numpy as np
import pytest

from stt import audio, hotkey, paste


def make_listener(
    monkeypatch: pytest.MonkeyPatch, times: list[float]
) -> tuple[hotkey.DoubleTapControlListener, list[None]]:
    toggles: list[None] = []
    clock = iter(times)
    monkeypatch.setattr(hotkey.time, "monotonic", lambda: next(clock))
    return hotkey.DoubleTapControlListener(lambda: toggles.append(None)), toggles


def tap(listener: hotkey.DoubleTapControlListener) -> None:
    listener._on_control_press()
    listener._on_control_release()


def test_double_ctrl_tap_toggles_once(monkeypatch: pytest.MonkeyPatch) -> None:
    listener, toggles = make_listener(monkeypatch, [1.0, 1.3])

    tap(listener)
    tap(listener)

    assert toggles == [None]


def test_repeated_ctrl_events_count_as_one_tap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listener, toggles = make_listener(monkeypatch, [1.0, 1.01])

    listener._on_control_press()
    listener._on_control_press()
    listener._on_control_release()
    listener._on_control_release()

    assert toggles == []


def test_ctrl_shortcuts_do_not_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    listener, toggles = make_listener(monkeypatch, [1.0, 1.2])

    for _ in range(2):  # Ctrl+C then Ctrl+V in quick succession.
        listener._on_control_press()
        listener._on_other_key()
        listener._on_control_release()

    assert toggles == []


def test_slow_ctrl_taps_do_not_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    listener, toggles = make_listener(monkeypatch, [1.0, 2.0])

    tap(listener)
    tap(listener)

    assert toggles == []


def test_hotkey_factory_uses_ctrl_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hotkey.sys, "platform", "linux")

    listener = hotkey.create_hotkey_listener(lambda: None)

    assert isinstance(listener, hotkey.DoubleTapControlListener)
    assert hotkey.hotkey_name() == "Ctrl"


def test_pcm16_conversion() -> None:
    data = np.array([0, 16384, -32768], dtype="<i2").tobytes() + b"\x01"

    chunk = audio._pcm16_to_float32(data)

    assert chunk.shape == (3, 1)
    assert chunk.reshape(-1).tolist() == [0.0, 0.5, -1.0]


def test_recorder_factory_uses_arecord_on_linux(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio.sys, "platform", "linux")

    assert isinstance(audio.create_recorder(), audio.ArecordRecorder)


def test_arecord_records_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    script = (
        "import sys, time; "
        "sys.stdout.buffer.write(b'\\x00\\x40' * 1600); sys.stdout.flush(); "
        "time.sleep(30)"
    )
    monkeypatch.setattr(
        audio, "_arecord_command", lambda *_args: [sys.executable, "-c", script]
    )
    levels: list[float] = []
    recorder = audio.ArecordRecorder(on_level=levels.append)

    recorder.start()
    assert recorder.is_recording
    deadline = time.monotonic() + 5
    while not levels and time.monotonic() < deadline:
        time.sleep(0.01)
    waveform, duration = recorder.stop()

    assert not recorder.is_recording
    assert waveform.size == 1600
    assert np.allclose(waveform, 0.5)
    assert duration > 0
    assert levels


def test_missing_arecord_reports_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio.shutil, "which", lambda _name: None)

    with pytest.raises(audio.MicrophoneUnavailableError):
        audio.ArecordRecorder().start()
    assert not audio._probe_arecord(16000, 1).ok


def test_deliver_text_pastes_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    typed: list[str] = []
    monkeypatch.setattr(paste, "_is_linux", lambda: True)
    monkeypatch.setattr(paste, "paste_text_linux", typed.append)
    monkeypatch.setattr(
        paste, "write_clipboard", lambda _text: pytest.fail("clipboard used")
    )

    paste.deliver_text("hola mundo", input_was_focused=True)

    assert typed == ["hola mundo"]
    assert paste.has_focused_editable_field()
