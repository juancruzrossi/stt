from __future__ import annotations

import shutil
import subprocess
import sys
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


ARECORD_DEVICE = "default"
ARECORD_CHUNK_BYTES = 1600  # 50 ms of 16 kHz mono int16 audio.


def _arecord_command(sample_rate: int, channels: int) -> list[str]:
    arecord = shutil.which("arecord")
    if arecord is None:
        raise MicrophoneUnavailableError("arecord was not found. Install alsa-utils.")
    return [
        arecord,
        "-q",
        "-D",
        ARECORD_DEVICE,
        "-t",
        "raw",
        "-f",
        "S16_LE",
        "-r",
        str(sample_rate),
        "-c",
        str(channels),
    ]


def _pcm16_to_float32(data: bytes) -> np.ndarray:
    usable = len(data) - len(data) % 2
    samples = np.frombuffer(data[:usable], dtype="<i2")
    return (samples.astype(np.float32) / 32768.0).reshape(-1, 1)


class ArecordRecorder:
    """Linux microphone recorder backed by ALSA's arecord (no PortAudio needed)."""

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
        self._process_lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._started_at = 0.0

    @property
    def is_recording(self) -> bool:
        with self._process_lock:
            return self._process is not None

    def start(self) -> None:
        with self._process_lock:
            if self._process is not None:
                return
            with self._lock:
                self._chunks = []
            command = _arecord_command(self.sample_rate, self.channels)
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as exc:
                raise MicrophoneUnavailableError from exc
            self._started_at = time.monotonic()
            self._process = process
            self._reader = threading.Thread(
                target=self._read_loop, args=(process,), daemon=True
            )
            self._reader.start()

    def _read_loop(self, process: subprocess.Popen[bytes]) -> None:
        stdout = process.stdout
        if stdout is None:
            return
        while True:
            data = stdout.read1(ARECORD_CHUNK_BYTES)  # type: ignore[attr-defined]
            if not data:
                return
            chunk = _pcm16_to_float32(data)
            if chunk.size == 0:
                continue
            if self._on_level is not None:
                rms = float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64))))
                self._on_level(rms)
            with self._lock:
                self._chunks.append(chunk)

    def _terminate(self) -> tuple[subprocess.Popen[bytes] | None, float]:
        with self._process_lock:
            process = self._process
            reader = self._reader
            self._process = None
            self._reader = None
        if process is None:
            return None, 0.0
        duration = time.monotonic() - self._started_at
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
        if reader is not None:
            reader.join(timeout=1)
        if process.stdout is not None:
            with suppress(OSError):
                process.stdout.close()
        return process, duration

    def stop(self) -> tuple[np.ndarray, float]:
        process, duration = self._terminate()
        if process is None:
            return np.array([], dtype=np.float32), 0.0
        with self._lock:
            chunks = self._chunks
            self._chunks = []
        if not chunks:
            if process.returncode not in (0, -15):
                raise MicrophoneUnavailableError("arecord failed to record audio.")
            return np.array([], dtype=np.float32), duration
        waveform = np.concatenate(chunks, axis=0).reshape(-1).astype(np.float32)
        return waveform, duration

    def close(self) -> None:
        """Release the microphone without returning buffered audio."""
        self._terminate()
        with self._lock:
            self._chunks = []


def create_recorder(
    *, on_level: Callable[[float], None] | None = None
) -> MicrophoneRecorder | ArecordRecorder:
    if sys.platform.startswith("linux"):
        return ArecordRecorder(on_level=on_level)
    return MicrophoneRecorder(on_level=on_level)


def _probe_arecord(sample_rate: int, channels: int) -> MicrophoneProbe:
    device = f"ALSA {ARECORD_DEVICE}"
    try:
        command = _arecord_command(sample_rate, channels)
        result = subprocess.run(
            [*command, "-d", "1"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (MicrophoneUnavailableError, OSError, subprocess.TimeoutExpired):
        return MicrophoneProbe(ok=False, device=device)
    return MicrophoneProbe(ok=result.returncode == 0 and bool(result.stdout), device=device)


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
    if sys.platform.startswith("linux"):
        return _probe_arecord(sample_rate, channels)
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
