from __future__ import annotations

from contextlib import nullcontext

import pytest

import stt.paste as paste


class FakeController:
    def pressed(self, _modifier: object) -> nullcontext[None]:
        return nullcontext()

    def press(self, _key: str) -> None:
        pass

    def release(self, _key: str) -> None:
        pass


def configure_paste(
    monkeypatch: pytest.MonkeyPatch, clipboard_reads: list[str]
) -> list[str]:
    writes: list[str] = []
    monkeypatch.setattr(paste, "read_clipboard", lambda: clipboard_reads.pop(0))
    monkeypatch.setattr(paste, "write_clipboard", writes.append)
    monkeypatch.setattr(paste.keyboard, "Controller", FakeController)
    monkeypatch.setattr(paste.time, "sleep", lambda _seconds: None)
    return writes


def test_paste_restores_unchanged_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    writes = configure_paste(monkeypatch, ["previous", "transcript"])

    paste.paste_text("transcript")

    assert writes == ["transcript", "previous"]


def test_paste_preserves_concurrent_clipboard_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes = configure_paste(monkeypatch, ["previous", "new value"])

    paste.paste_text("transcript")

    assert writes == ["transcript"]
