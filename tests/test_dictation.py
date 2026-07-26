from __future__ import annotations

from types import SimpleNamespace

import pytest

from stt import paste
from stt.dictation import DictationConfig, DictationSession


def test_stopped_session_does_not_deliver_pending_transcription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered: list[str] = []
    session = DictationSession(DictationConfig())
    session._jobs.put((object(), True))
    monkeypatch.setattr(
        paste,
        "deliver_text",
        lambda text, **_kwargs: delivered.append(text),
    )

    class Model:
        def transcribe(self, _waveform: object, **_kwargs: object) -> tuple[list[object], None]:
            session._stopped.set()
            return [SimpleNamespace(text="pending")], None

    session._transcription_worker(Model())

    assert delivered == []
