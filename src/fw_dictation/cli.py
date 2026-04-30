from __future__ import annotations

import argparse
import platform
import queue
import shutil
import sys
import threading
import time
from pathlib import Path

from .cache import (
    faster_whisper_cache_entries,
    human_size,
    huggingface_hub_cache,
    model_to_repo_id,
    repo_id_to_cache_dir,
)


DEFAULT_MODEL = "small"
DEFAULT_HOTKEY = "ctrl+option+cmd"
DEFAULT_MODE = "double-tap"
DEFAULT_LANGUAGE = "auto"


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stt")
    sub = parser.add_subparsers(required=True)

    doctor = sub.add_parser("doctor", help="Check dependencies and cache paths.")
    doctor.set_defaults(func=cmd_doctor)

    preload = sub.add_parser("preload", help="Download/load a model.")
    add_model_args(preload)
    preload.set_defaults(func=cmd_preload)

    models = sub.add_parser("models", help="Show cached models and disk usage.")
    models.set_defaults(func=cmd_models)

    transcribe = sub.add_parser("transcribe", help="Transcribe an audio file.")
    transcribe.add_argument("audio", type=Path)
    add_model_args(transcribe)
    transcribe.add_argument("--output", "-o", type=Path, help="Output .txt file.")
    transcribe.set_defaults(func=cmd_transcribe)

    listen = sub.add_parser("listen", help="Run global hotkey dictation.")
    add_model_args(listen)
    listen.add_argument("--mode", choices=("hold", "double-tap"), default=DEFAULT_MODE)
    listen.add_argument("--hotkey", default=DEFAULT_HOTKEY)
    listen.add_argument("--tap-key", default="cmd")
    listen.add_argument("--tap-interval", type=float, default=0.45)
    listen.add_argument("--min-seconds", type=float, default=0.35)
    listen.add_argument("--keep-clipboard", action="store_true")
    listen.set_defaults(func=cmd_listen)

    test_mic = sub.add_parser("test-mic", help="Record a few seconds and transcribe without hotkeys.")
    add_model_args(test_mic)
    test_mic.add_argument("--seconds", type=float, default=5.0)
    test_mic.set_defaults(func=cmd_test_mic)

    test_keys = sub.add_parser("test-keys", help="Print captured keys to validate permissions.")
    test_keys.add_argument("--seconds", type=float, default=10.0)
    test_keys.set_defaults(func=cmd_test_keys)

    return parser


def add_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help="Language code such as es/en, or auto for language detection.",
    )
    parser.add_argument(
        "--task",
        choices=("transcribe", "translate"),
        default="transcribe",
        help="transcribe keeps the source language; translate outputs English.",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use local model files only; fail instead of downloading.",
    )


def cmd_doctor(args: argparse.Namespace) -> None:  # noqa: ARG001
    print(f"macOS: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Architecture: {platform.machine()}")
    print(f"Homebrew: {shutil.which('brew') or 'not found'}")
    print(f"Hugging Face cache: {huggingface_hub_cache()}")
    print()
    print("macOS permissions needed:")
    print("- Microphone: record audio.")
    print("- Accessibility/Input Monitoring: global hotkeys and paste.")
    print()
    cmd_models(args)


def cmd_preload(args: argparse.Namespace) -> None:
    from .transcriber import load_model

    repo_id = model_to_repo_id(args.model)
    print(f"Loading model {args.model} ({repo_id})...", flush=True)
    load_model(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        local_files_only=args.offline,
    )
    path = repo_id_to_cache_dir(repo_id)
    print("Model ready.", flush=True)
    print(f"Expected path: {path}")
    cmd_models(args)


def cmd_models(args: argparse.Namespace) -> None:  # noqa: ARG001
    entries = faster_whisper_cache_entries()
    if not entries:
        print("No cached Faster Whisper models found.")
        print(f"Checked cache: {huggingface_hub_cache()}")
        return
    print("Cached Faster Whisper models:")
    for entry in entries:
        print(f"- {entry.repo_id}")
        print(f"  Path: {entry.path}")
        print(f"  Size: {human_size(entry.size_bytes)}")


def cmd_transcribe(args: argparse.Namespace) -> None:
    from .transcriber import transcribe_audio

    if not args.audio.exists():
        raise FileNotFoundError(args.audio)
    language = normalize_language(args.language)
    text, info = transcribe_audio(
        args.audio,
        model_name=args.model,
        language=language,
        task=args.task,
        device=args.device,
        compute_type=args.compute_type,
        local_files_only=args.offline,
    )
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Saved to: {args.output}")
    else:
        print(text)
    print(
        f"\nLanguage: {getattr(info, 'language', '?')} "
        f"({getattr(info, 'language_probability', 0.0):.2f})"
    )


def cmd_listen(args: argparse.Namespace) -> None:
    from .audio import MicrophoneRecorder
    from .hotkey import DoubleTapToggleListener, HoldHotkeyListener, parse_hotkey
    from .paste import paste_text
    from .transcriber import load_model

    hotkey = parse_hotkey(args.hotkey)
    language = normalize_language(args.language)
    recorder = MicrophoneRecorder()
    jobs: queue.Queue[tuple[object, float] | None] = queue.Queue()
    stop_event = threading.Event()

    print(f"Preloading model {args.model}...", flush=True)
    model = load_model(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        local_files_only=args.offline,
    )
    if args.mode == "double-tap":
        print(
            f"Ready. Double-tap {args.tap_key} to start; "
            f"double-tap {args.tap_key} again to stop.",
            flush=True,
        )
    else:
        print(f"Ready. Hold {hotkey.raw} to speak; release to transcribe.", flush=True)

    def on_start() -> None:
        if recorder.is_recording:
            return
        print("Recording...", flush=True)
        recorder.start()

    def on_stop() -> None:
        waveform, duration = recorder.stop()
        if duration < args.min_seconds or waveform.size == 0:
            print("Audio too short; ignored.", flush=True)
            return
        print(f"Processing {duration:.1f}s...", flush=True)
        jobs.put((waveform, duration))

    def on_toggle() -> None:
        if recorder.is_recording:
            on_stop()
        else:
            on_start()

    def worker() -> None:
        while not stop_event.is_set():
            item = jobs.get()
            if item is None:
                return
            waveform, _duration = item
            try:
                segments, info = model.transcribe(
                    waveform,
                    language=language,
                    task=args.task,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 350},
                    condition_on_previous_text=False,
                )
                text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
                if not text:
                    print("No text detected.", flush=True)
                    continue
                paste_text(text, restore_clipboard=not args.keep_clipboard)
                print(
                    f"Pasted: {text} "
                    f"[{getattr(info, 'language', '?')} "
                    f"{getattr(info, 'language_probability', 0.0):.2f}]",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"Transcription error: {exc}", file=sys.stderr, flush=True)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    if args.mode == "double-tap":
        listener = DoubleTapToggleListener(
            args.tap_key,
            on_toggle=on_toggle,
            max_interval=args.tap_interval,
        )
    else:
        listener = HoldHotkeyListener(hotkey, on_start=on_start, on_stop=on_stop)
    try:
        listener.run()
    finally:
        stop_event.set()
        jobs.put(None)
        thread.join(timeout=2)


def cmd_test_mic(args: argparse.Namespace) -> None:
    from .audio import MicrophoneRecorder
    from .transcriber import transcribe_waveform

    recorder = MicrophoneRecorder()
    print(f"Recording {args.seconds:.1f}s. Speak now...", flush=True)
    recorder.start()
    time.sleep(args.seconds)
    waveform, duration = recorder.stop()
    print(f"Processing {duration:.1f}s...", flush=True)
    language = normalize_language(args.language)
    text, info = transcribe_waveform(
        waveform,
        model_name=args.model,
        language=language,
        task=args.task,
        device=args.device,
        compute_type=args.compute_type,
        local_files_only=args.offline,
    )
    print(text or "No text detected.")
    print(
        f"Language: {getattr(info, 'language', '?')} "
        f"({getattr(info, 'language_probability', 0.0):.2f})"
    )


def cmd_test_keys(args: argparse.Namespace) -> None:
    from pynput import keyboard

    deadline = time.monotonic() + args.seconds

    print(
        f"For {args.seconds:.1f}s, captured keys will be printed.",
        flush=True,
    )
    print("Press Ctrl+Option+Command. If nothing appears, permissions are missing.", flush=True)

    def on_press(key) -> bool | None:  # noqa: ANN001
        print(f"press: {key!r}", flush=True)
        if time.monotonic() >= deadline:
            return False
        return None

    def on_release(key) -> bool | None:  # noqa: ANN001
        print(f"release: {key!r}", flush=True)
        if time.monotonic() >= deadline:
            return False
        return None

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        while time.monotonic() < deadline and listener.running:
            time.sleep(0.05)
        listener.stop()


def normalize_language(language: str) -> str | None:
    value = language.strip().lower()
    if value in {"", "auto", "detect", "none"}:
        return None
    return value
