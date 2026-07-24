from __future__ import annotations

import pytest

from stt import overlay


class FakeInput:
    def __init__(self) -> None:
        self.closed = False

    def fileno(self) -> int:
        return 42

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self) -> None:
        self.stdin = FakeInput()
        self.terminated = False
        self.waited = False

    def wait(self, *, timeout: float) -> None:
        self.waited = True

    def terminate(self) -> None:
        self.terminated = True


def test_indicator_streams_level_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeProcess()
    writes: list[tuple[int, bytes]] = []
    monkeypatch.setattr(
        overlay.subprocess,
        "Popen",
        lambda *_args, **_kwargs: process,
    )
    monkeypatch.setattr(overlay.os, "set_blocking", lambda *_args: None)
    monkeypatch.setattr(
        overlay.os,
        "write",
        lambda fd, value: writes.append((fd, value)) or len(value),
    )
    monkeypatch.setattr(overlay.time, "monotonic", lambda: 1.0)

    indicator = overlay.ListeningIndicator()
    indicator.start()
    indicator.show()
    indicator.update_level(0.125)
    indicator.show_processing()
    indicator.hide()

    assert writes == [
        (42, b"listening\n"),
        (42, b"0.12500\n"),
        (42, b"processing\n"),
        (42, b"hide\n"),
    ]
    assert not process.stdin.closed

    indicator.close()

    assert process.stdin.closed
    assert process.waited
    assert not process.terminated
