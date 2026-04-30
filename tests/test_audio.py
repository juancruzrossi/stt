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
