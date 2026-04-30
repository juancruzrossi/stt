from __future__ import annotations

import platform
import queue
import threading
from pathlib import Path

import click

from . import __version__
from .cache import faster_whisper_cache_entries, human_size, huggingface_hub_cache


DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "auto"
MIN_SECONDS = 0.35


@click.group(name="stt", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="stt")
def main() -> None:
    """Local speech-to-text dictation."""


def common_options(command):
    command = click.option(
        "--offline",
        is_flag=True,
        help="Use local model files only; fail instead of downloading.",
    )(command)
    command = click.option("--compute-type", default="int8", hidden=True)(command)
    command = click.option("--device", default="cpu", hidden=True)(command)
    command = click.option(
        "--task",
        type=click.Choice(["transcribe", "translate"]),
        default="transcribe",
        show_default=True,
        help="Transcribe source language or translate speech to English.",
    )(command)
    command = click.option(
        "--language",
        default=DEFAULT_LANGUAGE,
        show_default=True,
        help="Language code such as es/en, or auto for detection.",
    )(command)
    return command


@main.command()
def models() -> None:
    """Show cached model size."""
    entries = faster_whisper_cache_entries()
    if not entries:
        click.echo("No cached Faster Whisper models found.")
        click.echo(f"Checked cache: {huggingface_hub_cache()}")
        return

    click.echo("Cached Faster Whisper models:")
    for entry in entries:
        click.echo(f"- {entry.repo_id}")
        click.echo(f"  Path: {entry.path}")
        click.echo(f"  Size: {human_size(entry.size_bytes)}")


@main.command()
@click.argument("audio", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=Path), help="Output .txt file.")
@common_options
def transcribe(
    audio: Path,
    output: Path | None,
    language: str,
    task: str,
    device: str,
    compute_type: str,
    offline: bool,
) -> None:
    """Transcribe an audio file."""
    from .transcriber import transcribe_audio

    try:
        text, info = transcribe_audio(
            audio,
            model_name=DEFAULT_MODEL,
            language=normalize_language(language),
            task=task,
            device=device,
            compute_type=compute_type,
            local_files_only=offline,
        )
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc

    if output:
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"Saved to: {output}")
    else:
        click.echo(text)

    click.echo(
        f"\nLanguage: {getattr(info, 'language', '?')} "
        f"({getattr(info, 'language_probability', 0.0):.2f})"
    )


@main.command()
@click.option("--tap-interval", type=float, default=0.45, show_default=True)
@click.option("--keep-clipboard", is_flag=True, help="Do not restore the previous clipboard value.")
@common_options
def listen(
    language: str,
    task: str,
    device: str,
    compute_type: str,
    offline: bool,
    tap_interval: float,
    keep_clipboard: bool,
) -> None:
    """Run global hotkey dictation."""
    from .audio import MicrophoneRecorder
    from .hotkey import DoubleTapToggleListener
    from .paste import paste_text
    from .transcriber import load_model

    trigger_key = default_trigger_key()
    recorder = MicrophoneRecorder()
    jobs: queue.Queue[tuple[object, float] | None] = queue.Queue()
    stop_event = threading.Event()

    click.echo("Loading local STT model. First run may download about 464 MB...")
    try:
        model = load_model(
            DEFAULT_MODEL,
            device=device,
            compute_type=compute_type,
            local_files_only=offline,
        )
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc

    click.echo(
        f"Ready. Double-tap {trigger_key_label(trigger_key)} to start; "
        f"double-tap {trigger_key_label(trigger_key)} again to stop."
    )

    def on_start() -> None:
        if recorder.is_recording:
            return
        click.echo("Recording...")
        recorder.start()

    def on_stop() -> None:
        waveform, duration = recorder.stop()
        if duration < MIN_SECONDS or waveform.size == 0:
            click.echo("Audio too short; ignored.")
            return
        click.echo(f"Processing {duration:.1f}s...")
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
                    language=normalize_language(language),
                    task=task,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 350},
                    condition_on_previous_text=False,
                )
                text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
                if not text:
                    click.echo("No text detected.")
                    continue

                paste_text(text, restore_clipboard=not keep_clipboard)
                click.echo(
                    f"Pasted: {text} "
                    f"[{getattr(info, 'language', '?')} "
                    f"{getattr(info, 'language_probability', 0.0):.2f}]"
                )
            except Exception as exc:  # noqa: BLE001
                click.echo(f"Transcription error: {exc}", err=True)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    listener = DoubleTapToggleListener(
        trigger_key,
        on_toggle=on_toggle,
        max_interval=tap_interval,
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
