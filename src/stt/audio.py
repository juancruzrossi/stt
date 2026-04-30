from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd


class MicrophoneUnavailableError(RuntimeError):
    """Raised when the input device cannot be opened or used."""


@dataclass(frozen=True)
class MicrophoneProbe:
    ok: bool
    device: str


class MicrophoneRecorder:
    def __init__(self, *, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._started_at = 0.0

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
        self._started_at = time.monotonic()
        stream: sd.InputStream | None = None
        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )
            stream.start()
        except sd.PortAudioError as exc:
            if stream is not None:
                with suppress(sd.PortAudioError):
                    stream.close()
            raise MicrophoneUnavailableError from exc

        self._stream = stream

    def stop(self) -> tuple[np.ndarray, float]:
        if self._stream is None:
            return np.array([], dtype=np.float32), 0.0
        stream = self._stream
        self._stream = None
        try:
            stream.stop()
        except sd.PortAudioError as exc:
            raise MicrophoneUnavailableError from exc
        finally:
            with suppress(sd.PortAudioError):
                stream.close()
        duration = time.monotonic() - self._started_at
        with self._lock:
            chunks = self._chunks
            self._chunks = []
        if not chunks:
            return np.array([], dtype=np.float32), duration
        waveform = np.concatenate(chunks, axis=0).reshape(-1).astype(np.float32)
        return waveform, duration

    def _callback(
        self,
        indata: np.ndarray[Any, Any],
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            print(f"Audio warning: {status}", flush=True)
        with self._lock:
            self._chunks.append(indata.copy())


def default_input_device_name() -> str:
    try:
        device = sd.query_devices(kind="input")
    except sd.PortAudioError as exc:
        raise MicrophoneUnavailableError from exc

    if isinstance(device, dict):
        return str(device.get("name") or "Unknown")
    return str(device)


def probe_microphone(*, sample_rate: int = 16000, channels: int = 1) -> MicrophoneProbe:
    device = "Unknown"
    stream: sd.InputStream | None = None
    try:
        device = default_input_device_name()
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
        )
        stream.start()
        stream.stop()
    except (MicrophoneUnavailableError, sd.PortAudioError):
        return MicrophoneProbe(ok=False, device=device)
    finally:
        if stream is not None:
            with suppress(sd.PortAudioError):
                stream.close()

    return MicrophoneProbe(ok=True, device=device)
