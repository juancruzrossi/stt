from __future__ import annotations

import pytest
import sounddevice as sd

from stt.audio import MicrophoneRecorder, MicrophoneUnavailableError


def test_start_wraps_portaudio_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenInputStream:
        def __init__(self, **_kwargs: object) -> None:
            raise sd.PortAudioError("boom", -9986)

    monkeypatch.setattr(sd, "InputStream", BrokenInputStream)

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

    monkeypatch.setattr(sd, "InputStream", input_stream)

    recorder = MicrophoneRecorder()
    recorder.start()

    recorder.close()
    recorder.close()

    assert not recorder.is_recording
    assert streams[0].stopped
    assert streams[0].closed
