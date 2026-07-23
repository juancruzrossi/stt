from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

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
    monkeypatch.setattr(
        paste,
        "_keyboard",
        lambda: SimpleNamespace(
            Controller=FakeController,
            Key=SimpleNamespace(cmd="cmd", ctrl="ctrl"),
        ),
    )
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


def test_deliver_text_copies_without_pasting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[str] = []
    monkeypatch.setattr(paste, "write_clipboard", writes.append)
    monkeypatch.setattr(
        paste,
        "has_focused_editable_field",
        lambda: pytest.fail("focus should not be checked again"),
    )
    monkeypatch.setattr(
        paste,
        "paste_text",
        lambda *_args, **_kwargs: pytest.fail("paste_text should not be called"),
    )

    paste.deliver_text("transcript", input_was_focused=False)

    assert writes == ["transcript"]


def test_deliver_text_copies_when_focus_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[str] = []
    monkeypatch.setattr(paste, "has_focused_editable_field", lambda: False)
    monkeypatch.setattr(paste, "write_clipboard", writes.append)
    monkeypatch.setattr(
        paste,
        "paste_text",
        lambda *_args, **_kwargs: pytest.fail("paste_text should not be called"),
    )

    paste.deliver_text("transcript", input_was_focused=True)

    assert writes == ["transcript"]


def test_deliver_text_pastes_and_keeps_clipboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(paste, "has_focused_editable_field", lambda: True)
    monkeypatch.setattr(
        paste,
        "paste_text",
        lambda text, *, restore_clipboard: calls.append((text, restore_clipboard)),
    )

    paste.deliver_text(
        "transcript",
        input_was_focused=True,
        restore_clipboard=False,
    )

    assert calls == [("transcript", False)]


def test_deliver_text_keeps_transcript_when_focus_detection_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(paste, "has_focused_editable_field", lambda: None)
    monkeypatch.setattr(
        paste,
        "paste_text",
        lambda text, *, restore_clipboard: calls.append((text, restore_clipboard)),
    )

    paste.deliver_text(
        "transcript",
        input_was_focused=None,
        restore_clipboard=True,
    )

    assert calls == [("transcript", False)]


def configure_accessibility(
    monkeypatch: pytest.MonkeyPatch,
    *,
    focus_error: int = 0,
    is_focused: bool = True,
    role: str = "AXTextField",
    bundle_id: str | None = None,
    settable: bool = True,
) -> None:
    application_element = object()
    focused = object()
    application = SimpleNamespace(
        processIdentifier=lambda: 123,
        bundleIdentifier=lambda: bundle_id,
    )
    api = SimpleNamespace(
        kAXFocusedUIElementAttribute="focused",
        kAXFocusedAttribute="is_focused",
        kAXRoleAttribute="role",
        kAXSelectedTextAttribute="selected_text",
        kAXValueAttribute="value",
        AXUIElementCreateApplication=lambda _pid: application_element,
        AXUIElementCopyAttributeValue=lambda element, attribute, _value: (
            (focus_error, focused if focus_error == 0 else None)
            if element is application_element and attribute == "focused"
            else (0, is_focused)
            if attribute == "is_focused"
            else (0, role)
        ),
        AXUIElementIsAttributeSettable=lambda _element, _attribute, _value: (
            0,
            settable,
        ),
    )
    monkeypatch.setattr(paste.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(paste, "_application_services", lambda: api)
    monkeypatch.setattr(paste, "_frontmost_application", lambda: application)


def test_has_focused_editable_field_for_editable_text_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_accessibility(monkeypatch)

    assert paste.has_focused_editable_field()


def test_has_focused_editable_field_for_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_accessibility(
        monkeypatch,
        is_focused=False,
        role="AXTextArea",
        bundle_id="com.apple.Terminal",
        settable=False,
    )

    assert paste.has_focused_editable_field()


def test_has_no_focused_editable_field_for_read_only_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_accessibility(monkeypatch, settable=False)

    assert not paste.has_focused_editable_field()


def test_has_no_focused_editable_field_for_non_text_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_accessibility(monkeypatch, role="AXButton")

    assert not paste.has_focused_editable_field()


def test_has_no_focused_editable_field_when_accessibility_has_no_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_accessibility(monkeypatch, focus_error=-25204)

    assert not paste.has_focused_editable_field()


def test_has_no_focused_editable_field_for_stale_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_accessibility(monkeypatch, is_focused=False)

    assert not paste.has_focused_editable_field()


def test_has_no_focused_editable_field_when_accessibility_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(paste.platform, "system", lambda: "Darwin")

    def fail_to_load_accessibility() -> None:
        raise RuntimeError("Accessibility unavailable")

    monkeypatch.setattr(paste, "_application_services", fail_to_load_accessibility)

    assert not paste.has_focused_editable_field()


@pytest.mark.parametrize("system", ["Linux", "Windows"])
def test_focus_detection_is_unavailable_outside_macos(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
) -> None:
    monkeypatch.setattr(paste.platform, "system", lambda: system)

    assert paste.has_focused_editable_field() is None
