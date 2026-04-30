from __future__ import annotations

import threading
import time

import numpy as np
import sounddevice as sd


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
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> tuple[np.ndarray, float]:
        if self._stream is None:
            return np.array([], dtype=np.float32), 0.0
        stream = self._stream
        self._stream = None
        stream.stop()
        stream.close()
        duration = time.monotonic() - self._started_at
        with self._lock:
            chunks = self._chunks
            self._chunks = []
        if not chunks:
            return np.array([], dtype=np.float32), duration
        waveform = np.concatenate(chunks, axis=0).reshape(-1).astype(np.float32)
        return waveform, duration

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            print(f"Audio warning: {status}", flush=True)
        with self._lock:
            self._chunks.append(indata.copy())
