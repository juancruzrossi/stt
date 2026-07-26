from __future__ import annotations

import platform
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import click

from . import __version__
from .cache import faster_whisper_cache_entries, huggingface_hub_cache, human_size
from .model_config import MODEL_NAME

DEFAULT_LANGUAGE = "auto"


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
    entries = faster_whisper_cache_entries()
    microphone = probe_microphone()

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
    click.echo(f"  Runtime: {sys.executable}")
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
            model_name=MODEL_NAME,
            language=normalize_language(language),
            task=task,
            device=device,
            compute_type=compute_type,
            local_files_only=True,
        )
    except Exception as exc:
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
    from .dictation import DictationConfig, DictationSession

    def on_status(status: str, detail: str | None) -> None:
        if status == "ready":
            click.echo(
                "Ready. Double-tap Command to start; "
                "double-tap Command again to stop."
            )
        elif status == "error" and detail:
            click.echo(detail, err=True)

    session = DictationSession(
        DictationConfig(
            language=normalize_language(language),
            task=task,
            device=device,
            compute_type=compute_type,
            tap_interval=tap_interval,
            restore_clipboard=not keep_clipboard,
        ),
        on_status=on_status,
        on_text=print_verbose_text if verbose else None,
    )
    try:
        session.run()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def normalize_language(language: str) -> str | None:
    value = language.strip().lower()
    if value in {"", "auto", "detect", "none"}:
        return None
    return value


def print_verbose_text(text: str) -> None:
    click.echo("----")
    click.echo(text)
