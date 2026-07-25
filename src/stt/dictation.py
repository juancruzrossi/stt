from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .model_config import MODEL_NAME
from .settings import AppSettings

MIN_SECONDS = 0.35

StatusCallback = Callable[[str, str | None], None]
TextCallback = Callable[[str], None]


@dataclass(frozen=True)
class DictationConfig:
    settings: AppSettings = field(default_factory=AppSettings)
    language: str | None = None
    task: str = "transcribe"
    device: str = "cpu"
    compute_type: str = "int8"
    tap_interval: float = 0.45
    restore_clipboard: bool = True


class DictationSession:
    def __init__(
        self,
        config: DictationConfig,
        *,
        on_status: StatusCallback | None = None,
        on_text: TextCallback | None = None,
    ) -> None:
        self.config = config
        self._on_status = on_status or (lambda _status, _detail: None)
        self._on_text = on_text or (lambda _text: None)
        self._jobs: queue.Queue[tuple[object, bool] | None] = queue.Queue()
        self._processing = threading.Event()
        self._stopped = threading.Event()
        self._listener: Any | None = None
        self._recorder: Any | None = None
        self._indicator: Any | None = None
        self._worker: threading.Thread | None = None

    def run(self) -> None:
        from .audio import MicrophoneRecorder
        from .hotkey import GlobalHotkeyListener, ensure_listen_event_access
        from .overlay import ListeningIndicator
        from .paste import ensure_accessibility_access
        from .transcriber import load_model

        self._on_status("initializing", None)
        indicator = ListeningIndicator()
        recorder = MicrophoneRecorder(on_level=indicator.update_level)
        self._indicator = indicator
        self._recorder = recorder
        try:
            ensure_listen_event_access()
            ensure_accessibility_access()
            indicator.start()
            model = load_model(
                MODEL_NAME,
                device=self.config.device,
                compute_type=self.config.compute_type,
                local_files_only=True,
            )
            if self._stopped.is_set():
                return

            self._worker = threading.Thread(
                target=self._transcription_worker,
                args=(model,),
                name="stt-transcription",
                daemon=True,
            )
            self._worker.start()
            listener = GlobalHotkeyListener(
                self.config.settings,
                on_toggle=self.toggle_recording,
                on_start=self.start_recording,
                on_stop=self.stop_recording,
                max_interval=self.config.tap_interval,
            )
            self._listener = listener
            self._on_status("ready", None)
            listener.run()
        except Exception:
            if not self._stopped.is_set():
                raise
        finally:
            self._stopped.set()
            recorder.close()
            indicator.close()
            self._jobs.put(None)
            if self._worker is not None:
                self._worker.join(timeout=2)
            self._listener = None
            self._recorder = None
            self._indicator = None
            self._on_status("stopped", None)

    def start_recording(self) -> None:
        from .audio import MicrophoneUnavailableError

        recorder = self._recorder
        indicator = self._indicator
        if (
            self._stopped.is_set()
            or recorder is None
            or indicator is None
            or recorder.is_recording
            or self._processing.is_set()
        ):
            return
        try:
            recorder.start()
        except MicrophoneUnavailableError as exc:
            indicator.hide()
            self._on_status("error", f"Microphone unavailable: {exc}")
            return
        indicator.show()
        self._on_status("listening", None)

    def stop_recording(self) -> None:
        from .audio import MicrophoneUnavailableError

        recorder = self._recorder
        indicator = self._indicator
        if recorder is None or indicator is None or not recorder.is_recording:
            return

        try:
            waveform, duration = recorder.stop()
        except MicrophoneUnavailableError as exc:
            indicator.hide()
            self._on_status("error", f"Microphone unavailable: {exc}")
            return
        if duration < MIN_SECONDS or waveform.size == 0:
            indicator.hide()
            self._on_status("ready", None)
            return

        from .paste import has_focused_editable_field

        self._processing.set()
        indicator.show_processing()
        self._on_status("processing", None)
        self._jobs.put((waveform, has_focused_editable_field()))

    def toggle_recording(self) -> None:
        recorder = self._recorder
        if recorder is not None and recorder.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def stop(self) -> None:
        self._stopped.set()
        listener = self._listener
        if listener is not None:
            listener.stop()
        recorder = self._recorder
        if recorder is not None:
            recorder.close()
        indicator = self._indicator
        if indicator is not None:
            indicator.hide()

    def _transcription_worker(self, model: Any) -> None:
        from .paste import deliver_text
        from .terms import load_hotwords

        while not self._stopped.is_set():
            item = self._jobs.get()
            if item is None:
                return

            waveform, input_was_focused = item
            try:
                segments, _info = model.transcribe(
                    waveform,
                    language=self.config.language,
                    task=self.config.task,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 350},
                    condition_on_previous_text=False,
                    hotwords=load_hotwords(),
                )
                text = " ".join(
                    segment.text.strip()
                    for segment in segments
                    if segment.text.strip()
                )
                if self._stopped.is_set():
                    return
                if text:
                    deliver_text(
                        text,
                        input_was_focused=input_was_focused,
                        restore_clipboard=self.config.restore_clipboard,
                    )
                    self._on_text(text)
            except Exception as exc:  # noqa: BLE001
                self._on_status("error", f"Transcription failed: {exc}")
            finally:
                indicator = self._indicator
                if indicator is not None:
                    indicator.hide()
                self._processing.clear()
                if not self._stopped.is_set():
                    self._on_status("ready", None)
