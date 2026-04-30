#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
OS_NAME="$(uname -s)"

require_command() {
  local -r command_name="$1"
  local -r install_hint="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    echo "$install_hint" >&2
    exit 1
  fi
}

install_uv_if_missing() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  case "$OS_NAME" in
    Darwin)
      require_command brew "Install Homebrew from https://brew.sh, then rerun this script."
      echo "Installing uv..."
      brew install uv
      ;;
    Linux)
      echo "uv is not installed." >&2
      echo "Install it from https://docs.astral.sh/uv/getting-started/installation/ and rerun this script." >&2
      exit 1
      ;;
    *)
      echo "Unsupported OS for setup.sh: $OS_NAME" >&2
      echo "Use setup.ps1 on Windows." >&2
      exit 1
      ;;
  esac
}

install_portaudio_if_missing() {
  case "$OS_NAME" in
    Darwin)
      require_command brew "Install Homebrew from https://brew.sh, then rerun this script."
      if ! brew list portaudio >/dev/null 2>&1; then
        echo "Installing PortAudio for microphone capture..."
        brew install portaudio
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        echo "Installing PortAudio and clipboard helpers with apt..."
        sudo apt-get update
        sudo apt-get install -y portaudio19-dev xclip xsel
      elif command -v dnf >/dev/null 2>&1; then
        echo "Installing PortAudio and clipboard helpers with dnf..."
        sudo dnf install -y portaudio-devel xclip xsel
      elif command -v pacman >/dev/null 2>&1; then
        echo "Installing PortAudio and clipboard helpers with pacman..."
        sudo pacman -S --needed portaudio xclip xsel
      else
        echo "Could not detect a supported Linux package manager." >&2
        echo "Install PortAudio and a clipboard helper such as xclip/xsel manually." >&2
      fi
      ;;
  esac
}

install_uv_if_missing
install_portaudio_if_missing

cd "$ROOT_DIR"
export HF_HOME="${STT_HF_HOME:-$ROOT_DIR/.cache/huggingface}"
export XDG_CACHE_HOME="${STT_XDG_CACHE_HOME:-$ROOT_DIR/.cache}"
export UV_CACHE_DIR="${STT_UV_CACHE_DIR:-$ROOT_DIR/.cache/uv}"

uv sync --python 3.12

cat <<EOF

Setup complete.

Try:
  cd "$ROOT_DIR"
  ./stt doctor
  ./stt preload
  ./stt listen

EOF
