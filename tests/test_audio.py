from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

import stt.audio as audio
from stt.audio import MicrophoneRecorder, MicrophoneUnavailableError


class FakePortAudioError(Exception):
    pass


def test_start_wraps_portaudio_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenInputStream:
        def __init__(self, **_kwargs: object) -> None:
            raise FakePortAudioError("boom", -9986)

    monkeypatch.setattr(
        audio,
        "_sounddevice",
        lambda: SimpleNamespace(
            InputStream=BrokenInputStream,
            PortAudioError=FakePortAudioError,
        ),
    )

    recorder = MicrophoneRecorder()

    with pytest.raises(MicrophoneUnavailableError):
        recorder.start()

    assert not recorder.is_recording


def test_close_releases_active_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeInputStream:
        stopped = False
        closed = False

        def __init__(self, **_kwargs: object) -> None:
            pass

        def start(self) -> None:
            pass

        def stop(self) -> None:
            self.stopped = True

        def close(self) -> None:
            self.closed = True

    streams: list[FakeInputStream] = []

    def input_stream(**kwargs: object) -> FakeInputStream:
        stream = FakeInputStream(**kwargs)
        streams.append(stream)
        return stream

    monkeypatch.setattr(
        audio,
        "_sounddevice",
        lambda: SimpleNamespace(
            InputStream=input_stream,
            PortAudioError=FakePortAudioError,
        ),
    )

    recorder = MicrophoneRecorder()
    recorder.start()

    recorder.close()
    recorder.close()

    assert not recorder.is_recording
    assert streams[0].stopped
    assert streams[0].closed


def test_probe_reports_missing_portaudio(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable() -> object:
        raise MicrophoneUnavailableError

    monkeypatch.setattr(audio, "_sounddevice", unavailable)

    assert audio.probe_microphone() == audio.MicrophoneProbe(
        ok=False,
        device="Unknown",
    )


def test_callback_reports_microphone_level() -> None:
    levels: list[float] = []
    recorder = MicrophoneRecorder(on_level=levels.append)

    recorder._callback(
        np.array([[0.25], [-0.25]], dtype=np.float32),
        frames=2,
        time_info=object(),
        status=None,
    )

    assert levels == [pytest.approx(0.25)]
