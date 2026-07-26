from __future__ import annotations

import platform
import sys
from pathlib import Path

from setuptools import setup

from stt import __version__

sys.setrecursionlimit(10_000)

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
MODEL_PATH = PROJECT_ROOT / ".models" / "faster-whisper-base"
BUNDLED_AV = (
    PROJECT_ROOT
    / "dist"
    / "STT.app"
    / "Contents"
    / "Resources"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "av"
)

setup(
    name="STT",
    version=__version__,
    app=[str(ROOT / "STT.py")],
    options={
        "py2app": {
            "arch": platform.machine(),
            "argv_emulation": False,
            "dylib_excludes": [str(BUNDLED_AV)],
            "extra_scripts": [str(ROOT / "stt-overlay.py")],
            "iconfile": str(ROOT / "STT.icns"),
            "includes": [
                "AppKit",
                "ApplicationServices",
                "CoreFoundation",
                "Foundation",
                "objc",
                "sounddevice",
            ],
            "packages": ["faster_whisper", "stt"],
            "resources": [str(MODEL_PATH)],
            "plist": {
                "CFBundleDisplayName": "STT",
                "CFBundleIdentifier": "com.juancruzrossi.stt",
                "CFBundleName": "STT",
                "CFBundleShortVersionString": __version__,
                "CFBundleVersion": __version__,
                "LSMinimumSystemVersion": "13.0",
                "LSUIElement": False,
                "NSHighResolutionCapable": True,
                "NSMicrophoneUsageDescription": (
                    "STT needs microphone access to transcribe speech locally."
                ),
            },
        }
    },
)
