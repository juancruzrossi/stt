from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from typing import Any

import numpy as np


class MicrophoneUnavailableError(RuntimeError):
    """Raised when the input device cannot be opened or used."""


@dataclass(frozen=True)
class MicrophoneProbe:
    ok: bool
    device: str


def _sounddevice() -> Any:
    try:
        return import_module("sounddevice")
    except (ImportError, OSError) as exc:
        raise MicrophoneUnavailableError from exc


class MicrophoneRecorder:
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._on_level = on_level
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream_lock = threading.Lock()
        self._stream: Any | None = None
        self._started_at = 0.0

    @property
    def is_recording(self) -> bool:
        with self._stream_lock:
            return self._stream is not None

    def start(self) -> None:
        with self._stream_lock:
            if self._stream is not None:
                return
            with self._lock:
                self._chunks = []
            self._started_at = time.monotonic()
            sd = _sounddevice()
            stream: Any | None = None
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
        with self._stream_lock:
            if self._stream is None:
                return np.array([], dtype=np.float32), 0.0
            stream = self._stream
            self._stream = None
        sd = _sounddevice()
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

    def close(self) -> None:
        """Release the microphone stream without returning buffered audio."""
        with self._stream_lock:
            if self._stream is None:
                return
            stream = self._stream
            self._stream = None
        sd = _sounddevice()
        with suppress(sd.PortAudioError):
            stream.stop()
        with suppress(sd.PortAudioError):
            stream.close()
        with self._lock:
            self._chunks = []

    def _callback(
        self,
        indata: np.ndarray[Any, Any],
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        if status:
            print(f"Audio warning: {status}", flush=True)
        if self._on_level is not None:
            rms = float(np.sqrt(np.mean(np.square(indata, dtype=np.float64))))
            self._on_level(rms)
        with self._lock:
            self._chunks.append(indata.copy())


def default_input_device_name() -> str:
    sd = _sounddevice()
    try:
        device = sd.query_devices(kind="input")
    except sd.PortAudioError as exc:
        raise MicrophoneUnavailableError from exc

    if isinstance(device, dict):
        return str(device.get("name") or "Unknown")
    return str(device)


def probe_microphone(*, sample_rate: int = 16000, channels: int = 1) -> MicrophoneProbe:
    device = "Unknown"
    stream: Any | None = None
    try:
        sd = _sounddevice()
        device = default_input_device_name()
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
        )
        stream.start()
        stream.stop()
    except MicrophoneUnavailableError:
        return MicrophoneProbe(ok=False, device=device)
    except Exception as exc:
        if not isinstance(exc, sd.PortAudioError):
            raise
        return MicrophoneProbe(ok=False, device=device)
    finally:
        if stream is not None:
            with suppress(sd.PortAudioError):
                stream.close()

    return MicrophoneProbe(ok=True, device=device)
