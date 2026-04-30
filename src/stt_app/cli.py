from __future__ import annotations

import argparse
import platform
import queue
import sys
import threading
from pathlib import Path

from .cache import (
    faster_whisper_cache_entries,
    human_size,
    huggingface_hub_cache,
)


DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "auto"
MIN_SECONDS = 0.35


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

    models = sub.add_parser("models", help="Show cached models and disk usage.")
    models.set_defaults(func=cmd_models)

    transcribe = sub.add_parser("transcribe", help="Transcribe an audio file.")
    transcribe.add_argument("audio", type=Path)
    add_model_args(transcribe)
    transcribe.add_argument("--output", "-o", type=Path, help="Output .txt file.")
    transcribe.set_defaults(func=cmd_transcribe)

    listen = sub.add_parser("listen", help="Run global hotkey dictation.")
    add_model_args(listen)
    listen.add_argument("--tap-interval", type=float, default=0.45)
    listen.add_argument("--keep-clipboard", action="store_true")
    listen.set_defaults(func=cmd_listen)

    return parser


def add_model_args(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--device", default="cpu", help=argparse.SUPPRESS)
    parser.add_argument("--compute-type", default="int8", help=argparse.SUPPRESS)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use local model files only; fail instead of downloading.",
    )


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
        model_name=DEFAULT_MODEL,
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
    from .hotkey import DoubleTapToggleListener
    from .paste import paste_text
    from .transcriber import load_model

    language = normalize_language(args.language)
    trigger_key = default_trigger_key()
    recorder = MicrophoneRecorder()
    jobs: queue.Queue[tuple[object, float] | None] = queue.Queue()
    stop_event = threading.Event()

    print("Loading local STT model. First run may download about 464 MB...", flush=True)
    model = load_model(
        DEFAULT_MODEL,
        device=args.device,
        compute_type=args.compute_type,
        local_files_only=args.offline,
    )
    print(
        f"Ready. Double-tap {trigger_key_label(trigger_key)} to start; "
        f"double-tap {trigger_key_label(trigger_key)} again to stop.",
        flush=True,
    )

    def on_start() -> None:
        if recorder.is_recording:
            return
        print("Recording...", flush=True)
        recorder.start()

    def on_stop() -> None:
        waveform, duration = recorder.stop()
        if duration < MIN_SECONDS or waveform.size == 0:
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
    listener = DoubleTapToggleListener(
        trigger_key,
        on_toggle=on_toggle,
        max_interval=args.tap_interval,
    )
    try:
        listener.run()
    finally:
        stop_event.set()
        jobs.put(None)
        thread.join(timeout=2)


def normalize_language(language: str) -> str | None:
    value = language.strip().lower()
    if value in {"", "auto", "detect", "none"}:
        return None
    return value


def default_trigger_key() -> str:
    if platform.system() == "Darwin":
        return "cmd"
    return "ctrl"


def trigger_key_label(key: str) -> str:
    return "Command" if key == "cmd" else "Control"
