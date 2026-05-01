from __future__ import annotations

import platform
import queue
import shutil
import sys
import threading
from pathlib import Path
from collections.abc import Callable
from typing import Any, cast

import click

from . import __version__
from .cache import faster_whisper_cache_entries, human_size, huggingface_hub_cache


DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "auto"
MIN_SECONDS = 0.35


class StatusLine:
    def __init__(self, message: str) -> None:
        self.message = message
        self._enabled = sys.stdout.isatty()

    def __enter__(self) -> None:
        if not self._enabled:
            return
        sys.stdout.write(f"{self.message}\n")
        sys.stdout.flush()

    def __exit__(self, *_exc_info: object) -> None:
        if not self._enabled:
            return
        sys.stdout.write("\033[F\033[K")
        sys.stdout.flush()


@click.group(name="stt", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="stt")
def main() -> None:
    """Local speech-to-text dictation."""


def common_options(command: Callable[..., Any]) -> Callable[..., Any]:
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
    return cast(Callable[..., Any], command)


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
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Check install, model, and microphone."""
    from .audio import probe_microphone

    issues: list[str] = []
    uv_path = shutil.which("uv")
    entries = faster_whisper_cache_entries()
    microphone = probe_microphone()

    if uv_path is None:
        issues.append("uv was not found in PATH.")
    if not entries:
        issues.append("Faster Whisper model was not found.")
    if not microphone.ok:
        issues.append("Microphone could not be opened.")

    click.echo("STT Doctor")
    click.echo()
    click.echo("System")
    click.echo(f"  stt: {__version__}")
    click.echo(f"  Python: {platform.python_version()}")
    click.echo(f"  Platform: {platform.system()} {platform.machine()}")
    click.echo()
    click.echo("Install")
    click.echo(f"  uv: {'OK' if uv_path else 'Missing'}")
    click.echo()
    click.echo("Model")
    if entries:
        click.echo("  Status: OK")
    else:
        click.echo("  Status: Missing")
        click.echo(f"  Checked: {huggingface_hub_cache()}")
    click.echo()
    click.echo("Audio")
    click.echo(f"  Status: {'OK' if microphone.ok else 'Failed'}")
    click.echo(f"  Default input: {microphone.device}")
    click.echo()
    click.echo("Result")
    if issues:
        click.echo("  Issues found:")
        for issue in issues:
            click.echo(f"  - {issue}")
        ctx.exit(1)

    click.echo("  OK: stt is ready.")


@main.command()
@click.argument(
    "audio",
    metavar="AUDIO_FILE",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output .txt file.",
)
@common_options
def transcribe(
    audio: Path,
    output: Path | None,
    language: str,
    task: str,
    device: str,
    compute_type: str,
) -> None:
    """Transcribe a local audio/video file to text."""
    from .transcriber import transcribe_audio

    try:
        text, info = transcribe_audio(
            audio,
            model_name=DEFAULT_MODEL,
            language=normalize_language(language),
            task=task,
            device=device,
            compute_type=compute_type,
            local_files_only=True,
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
@click.option(
    "--tap-interval",
    type=click.FloatRange(min=0.1),
    default=0.45,
    show_default=True,
)
@click.option(
    "--keep-clipboard",
    is_flag=True,
    help="Do not restore the previous clipboard value.",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Print each transcription in the terminal.",
)
@common_options
def listen(
    language: str,
    task: str,
    device: str,
    compute_type: str,
    tap_interval: float,
    keep_clipboard: bool,
    verbose: bool,
) -> None:
    """Run global hotkey dictation."""
    from .audio import MicrophoneRecorder, MicrophoneUnavailableError
    from .hotkey import DoubleTapToggleListener
    from .paste import paste_text
    from .transcriber import load_model

    trigger_key = default_trigger_key()
    recorder = MicrophoneRecorder()
    jobs: queue.Queue[tuple[object, float] | None] = queue.Queue()
    stop_event = threading.Event()

    try:
        with StatusLine("Initializing stt..."):
            model = load_model(
                DEFAULT_MODEL,
                device=device,
                compute_type=compute_type,
                local_files_only=True,
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
        recorder.start()

    def on_stop() -> None:
        waveform, duration = recorder.stop()
        if duration < MIN_SECONDS or waveform.size == 0:
            return
        jobs.put((waveform, duration))

    def on_toggle() -> None:
        try:
            if recorder.is_recording:
                on_stop()
            else:
                on_start()
        except MicrophoneUnavailableError:
            click.echo("Microphone unavailable. Try again.", err=True)

    def worker() -> None:
        while not stop_event.is_set():
            item = jobs.get()
            if item is None:
                return

            waveform, _duration = item
            try:
                segments, _info = model.transcribe(
                    waveform,
                    language=normalize_language(language),
                    task=task,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 350},
                    condition_on_previous_text=False,
                )
                text = " ".join(
                    segment.text.strip() for segment in segments if segment.text.strip()
                )
                if not text:
                    continue

                paste_text(text, restore_clipboard=not keep_clipboard)
                if verbose:
                    print_verbose_text(text)
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


def print_verbose_text(text: str) -> None:
    click.echo("----")
    click.echo(text)


def default_trigger_key() -> str:
    if platform.system() == "Darwin":
        return "cmd"
    return "ctrl"


def trigger_key_label(key: str) -> str:
    return "Command" if key == "cmd" else "Control"
