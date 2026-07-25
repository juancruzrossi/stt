"""Local speech-to-text dictation using Faster Whisper."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("stt")
except PackageNotFoundError:
    __version__ = "0+unknown"
