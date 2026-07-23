from __future__ import annotations

from contextlib import suppress
from importlib import import_module
import math
import os
import platform
import subprocess
import sys
import time
from typing import Any


FRAME_INTERVAL = 1 / 30
LEVEL_INTERVAL = 1 / 20
TRANSITION_SECONDS = 0.3
STATE_TRANSITION_SECONDS = 0.24
STATE_LABELS = {
    "listening": "Listening…",
    "processing": "Processing…",
}


class ListeningIndicator:
    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._input: Any | None = None
        self._last_level_at = 0.0
        self._start_attempted = False

    def start(self) -> None:
        if self._start_attempted or platform.system() != "Darwin":
            return
        self._start_attempted = True

        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "stt.overlay"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return
        if process.stdin is None:
            process.terminate()
            return

        try:
            os.set_blocking(process.stdin.fileno(), False)
        except OSError:
            process.stdin.close()
            process.terminate()
            return

        self._process = process
        self._input = process.stdin
        self._last_level_at = 0.0

    def show(self) -> None:
        self.start()
        self._write(b"listening\n")

    def show_processing(self) -> None:
        self._write(b"processing\n")

    def update_level(self, rms: float) -> None:
        now = time.monotonic()
        if now - self._last_level_at < LEVEL_INTERVAL:
            return
        self._last_level_at = now
        self._write(f"{rms:.5f}\n".encode())

    def _write(self, message: bytes) -> None:
        if self._input is None:
            return
        try:
            os.write(self._input.fileno(), message)
        except OSError:
            with suppress(OSError):
                self._input.close()
            self._input = None

    def hide(self) -> None:
        self._write(b"hide\n")

    def close(self) -> None:
        process = self._process
        input_stream = self._input
        self._process = None
        self._input = None
        if process is None:
            return

        if input_stream is not None:
            with suppress(OSError):
                input_stream.close()
        try:
            process.wait(timeout=0.6)
        except subprocess.TimeoutExpired:
            process.terminate()
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=0.4)


def _normalized_level(rms: float) -> float:
    return min(1.0, max(0.0, (rms - 0.003) / 0.07))


def _smoothstep(progress: float) -> float:
    return progress * progress * (3.0 - 2.0 * progress)


def _run_macos_overlay() -> None:
    AppKit: Any = import_module("AppKit")
    Foundation: Any = import_module("Foundation")
    objc: Any = import_module("objc")

    reduce_motion = False
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    if hasattr(workspace, "accessibilityDisplayShouldReduceMotion"):
        reduce_motion = bool(workspace.accessibilityDisplayShouldReduceMotion())
    defaults = Foundation.NSUserDefaults.alloc().initWithSuiteName_(
        "com.juancruzrossi.stt"
    )

    class IndicatorView(AppKit.NSView):
        level = 0.0
        target_level = 0.0
        started_at = 0.0
        phase = 0.0
        state = "listening"
        previous_state = "listening"
        state_changed_at = 0.0
        drag_mouse_origin: Any = None
        drag_window_origin: Any = None

        def initWithFrame_(self, frame: Any) -> Any:
            self = objc.super(IndicatorView, self).initWithFrame_(frame)
            if self is not None:
                self.started_at = time.monotonic()
            return self

        def setTargetLevel_(self, level: float) -> None:
            self.target_level = _normalized_level(level)

        def setState_(self, state: str) -> None:
            now = time.monotonic()
            if state != self.state:
                self.previous_state = self.state
                self.state = state
                self.state_changed_at = now
            self.started_at = now
            self.target_level = 0.0
            if state == "processing":
                self.level = 0.0

        def advance(self) -> None:
            if self.state == "processing":
                self.level = 0.0
            else:
                self.level += (self.target_level - self.level) * 0.28
                self.target_level *= 0.92
            if self.state == "processing":
                self.phase += 0.06 if reduce_motion else 0.18
            elif not reduce_motion:
                self.phase += 0.18
            self.setNeedsDisplay_(True)

        def acceptsFirstMouse_(self, _event: Any) -> bool:
            return True

        def resetCursorRects(self) -> None:
            self.addCursorRect_cursor_(
                self.bounds(),
                AppKit.NSCursor.openHandCursor(),
            )

        def mouseDown_(self, _event: Any) -> None:
            self.drag_mouse_origin = AppKit.NSEvent.mouseLocation()
            self.drag_window_origin = self.window().frame().origin
            AppKit.NSCursor.closedHandCursor().set()

        def mouseDragged_(self, _event: Any) -> None:
            mouse = AppKit.NSEvent.mouseLocation()
            self.window().setFrameOrigin_(
                Foundation.NSMakePoint(
                    self.drag_window_origin.x + mouse.x - self.drag_mouse_origin.x,
                    self.drag_window_origin.y + mouse.y - self.drag_mouse_origin.y,
                )
            )

        def mouseUp_(self, _event: Any) -> None:
            origin = self.window().frame().origin
            defaults.setDouble_forKey_(origin.x, "overlayX")
            defaults.setDouble_forKey_(origin.y, "overlayY")
            defaults.synchronize()
            AppKit.NSCursor.openHandCursor().set()

        def drawRect_(self, _rect: Any) -> None:
            now = time.monotonic()
            bounds = self.bounds()
            is_processing = self.state == "processing"
            processing_pulse = (
                0.5 + 0.5 * math.sin(self.phase) if is_processing else 0.0
            )
            background = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                bounds, 23.0, 23.0
            )
            background_red = 0.17 + 0.018 * processing_pulse
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                background_red, 0.17, 0.18, 0.98
            ).setFill()
            background.fill()

            if is_processing and not reduce_motion:
                shimmer_progress = ((now - self.state_changed_at) % 1.4) / 1.4
                shimmer_x = -32.0 + shimmer_progress * (bounds.size.width + 64.0)
                AppKit.NSGraphicsContext.saveGraphicsState()
                background.addClip()
                AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    1.0, 0.39, 0.27, 0.1
                ).setFill()
                AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    Foundation.NSMakeRect(shimmer_x, -8.0, 36.0, 62.0),
                    18.0,
                    18.0,
                ).fill()
                AppKit.NSGraphicsContext.restoreGraphicsState()

            if not is_processing:
                AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    0.96, 0.34, 0.29, 1.0
                ).setFill()
            for index in range(7):
                if is_processing:
                    height = 7.0
                    glow = (
                        processing_pulse
                        if reduce_motion
                        else 0.5 + 0.5 * math.sin(self.phase - index * 0.85)
                    )
                    AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.98,
                        0.34 + 0.18 * glow,
                        0.25,
                        0.62 + 0.38 * glow,
                    ).setFill()
                else:
                    variation = 0.62 + 0.38 * math.sin(self.phase + index * 1.35)
                    height = 7.0 + 17.0 * self.level * variation
                bar = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    Foundation.NSMakeRect(
                        15.0 + index * 6.0,
                        (46.0 - height) / 2,
                        3.5,
                        height,
                    ),
                    1.75,
                    1.75,
                )
                bar.fill()

            state_progress = min(
                1.0,
                (now - self.state_changed_at) / STATE_TRANSITION_SECONDS,
            )
            current_alpha = _smoothstep(state_progress)
            if self.previous_state != self.state and state_progress < 1.0:
                self._drawLabel_alpha_(
                    STATE_LABELS[self.previous_state],
                    1.0 - current_alpha,
                )
            self._drawLabel_alpha_(STATE_LABELS[self.state], current_alpha)

            if self.state == "listening":
                elapsed = int(now - self.started_at)
                timer_attributes = {
                    AppKit.NSFontAttributeName: AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(
                        12.5, AppKit.NSFontWeightRegular
                    ),
                    AppKit.NSForegroundColorAttributeName: AppKit.NSColor.colorWithCalibratedWhite_alpha_(
                        0.66, 1.0
                    ),
                }
                Foundation.NSString.stringWithString_(
                    f"{elapsed // 60}:{elapsed % 60:02d}"
                ).drawAtPoint_withAttributes_(
                    Foundation.NSMakePoint(150.0, 16.0), timer_attributes
                )

        def _drawLabel_alpha_(self, label: str, alpha: float) -> None:
            label_color = (
                AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    1.0,
                    0.82,
                    0.78,
                    alpha,
                )
                if label == STATE_LABELS["processing"]
                else AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.94, alpha)
            )
            attributes = {
                AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_weight_(
                    13.5,
                    AppKit.NSFontWeightRegular,
                ),
                AppKit.NSForegroundColorAttributeName: label_color,
            }
            Foundation.NSString.stringWithString_(label).drawAtPoint_withAttributes_(
                Foundation.NSMakePoint(63.0, 15.5),
                attributes,
            )

    class OverlayController(Foundation.NSObject):
        view: Any = None
        window: Any = None
        input_fd = -1
        input_buffer = b""
        opacity = 0.0
        visible = False
        hiding = False
        transition_started_at = 0.0
        transition_start_opacity = 0.0

        def tick_(self, _timer: Any) -> None:
            now = time.monotonic()
            try:
                chunk = os.read(self.input_fd, 4096)
            except BlockingIOError:
                chunk = None
            except OSError:
                chunk = b""

            if chunk == b"":
                AppKit.NSApp.terminate_(None)
                return
            if chunk:
                self.input_buffer += chunk
                lines = self.input_buffer.split(b"\n")
                self.input_buffer = lines.pop()
                for line in lines:
                    if line in {b"listening", b"processing"}:
                        self.view.setState_(line.decode())
                        if not self.visible or self.hiding:
                            self.transition_start_opacity = self.opacity
                            self.transition_started_at = now
                            self.hiding = False
                            self.visible = True
                            self.window.orderFrontRegardless()
                    elif line == b"hide":
                        if self.visible and not self.hiding:
                            self.transition_start_opacity = self.opacity
                            self.transition_started_at = now
                            self.hiding = True
                    else:
                        with suppress(ValueError):
                            self.view.setTargetLevel_(float(line))

            if not self.visible:
                return
            if reduce_motion:
                if self.hiding:
                    self.opacity = 0.0
                    self.hiding = False
                    self.visible = False
                    self.window.setAlphaValue_(0.0)
                    self.window.orderOut_(None)
                else:
                    self.opacity = 1.0
                    self.window.setAlphaValue_(1.0)
            elif self.hiding:
                progress = min(
                    1.0,
                    (now - self.transition_started_at) / TRANSITION_SECONDS,
                )
                self.opacity = self.transition_start_opacity * (
                    1.0 - _smoothstep(progress)
                )
                self.window.setAlphaValue_(self.opacity)
                if progress == 1.0:
                    self.hiding = False
                    self.visible = False
                    self.window.orderOut_(None)
                    return
            elif self.opacity < 1.0:
                progress = min(
                    1.0,
                    (now - self.transition_started_at) / TRANSITION_SECONDS,
                )
                self.opacity = self.transition_start_opacity + (
                    1.0 - self.transition_start_opacity
                ) * _smoothstep(progress)
                self.window.setAlphaValue_(self.opacity)
            self.view.advance()

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    frame = Foundation.NSMakeRect(0.0, 0.0, 200.0, 46.0)
    window = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
        AppKit.NSBackingStoreBuffered,
        False,
    )
    window.setOpaque_(False)
    window.setBackgroundColor_(AppKit.NSColor.clearColor())
    window.setHasShadow_(True)
    window.setIgnoresMouseEvents_(False)
    window.setLevel_(AppKit.NSFloatingWindowLevel)
    window.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    window.setAlphaValue_(0.0)

    screen_frame = AppKit.NSScreen.mainScreen().visibleFrame()
    saved_x = defaults.objectForKey_("overlayX")
    saved_y = defaults.objectForKey_("overlayY")
    if saved_x is not None and saved_y is not None:
        origin = Foundation.NSMakePoint(float(saved_x), float(saved_y))
    else:
        origin = Foundation.NSMakePoint(
            screen_frame.origin.x + (screen_frame.size.width - frame.size.width) / 2,
            screen_frame.origin.y + 20.0,
        )
    window.setFrameOrigin_(origin)
    view = IndicatorView.alloc().initWithFrame_(frame)
    window.setContentView_(view)

    input_fd = sys.stdin.buffer.fileno()
    os.set_blocking(input_fd, False)
    controller = OverlayController.alloc().init()
    controller.view = view
    controller.window = window
    controller.input_fd = input_fd
    controller.opacity = 0.0
    controller.transition_started_at = time.monotonic()
    timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        FRAME_INTERVAL,
        controller,
        "tick:",
        None,
        True,
    )
    app.run()
    timer.invalidate()
    window.orderOut_(None)


if __name__ == "__main__" and platform.system() == "Darwin":
    _run_macos_overlay()
