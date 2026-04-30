#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${STT_REPO_URL:-https://github.com/juancruzrossi/stt.git}"
INSTALL_DIR="${STT_INSTALL_DIR:-$HOME/.local/share/stt}"
BIN_DIR="${STT_BIN_DIR:-$HOME/.local/bin}"
OS_NAME="$(uname -s)"

log() {
  printf '\n==> %s\n' "$1"
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

script_dir() {
  local source_path="${BASH_SOURCE[0]:-}"
  if [[ -n "$source_path" && -f "$source_path" ]]; then
    cd -- "$(dirname -- "$source_path")" && pwd -P
  fi
}

is_project_dir() {
  [[ -f "$1/pyproject.toml" && -d "$1/src/stt_app" ]]
}

install_uv_if_missing() {
  if command_exists uv; then
    return
  fi

  log "Installing uv"
  case "$OS_NAME" in
    Darwin)
      if command_exists brew; then
        brew install uv
      else
        curl -LsSf https://astral.sh/uv/install.sh | sh
      fi
      ;;
    Linux)
      curl -LsSf https://astral.sh/uv/install.sh | sh
      ;;
    *)
      fail "Unsupported OS for install.sh: $OS_NAME. Use install.ps1 on Windows."
      ;;
  esac

  export PATH="$HOME/.local/bin:$PATH"
  command_exists uv || fail "uv installation completed but uv is still not on PATH."
}

install_system_dependencies() {
  log "Checking system audio dependencies"
  case "$OS_NAME" in
    Darwin)
      command_exists brew || fail "Homebrew is required on macOS: https://brew.sh"
      if ! brew list portaudio >/dev/null 2>&1; then
        brew install portaudio
      fi
      ;;
    Linux)
      if command_exists apt-get; then
        sudo apt-get update
        sudo apt-get install -y portaudio19-dev xclip xsel
      elif command_exists dnf; then
        sudo dnf install -y portaudio-devel xclip xsel
      elif command_exists pacman; then
        sudo pacman -S --needed portaudio xclip xsel
      else
        echo "Could not detect apt, dnf, or pacman."
        echo "Install PortAudio and xclip/xsel manually if microphone or paste fails."
      fi
      ;;
    *)
      fail "Unsupported OS for install.sh: $OS_NAME. Use install.ps1 on Windows."
      ;;
  esac
}

resolve_project_dir() {
  local dir
  dir="$(script_dir || true)"

  if [[ -n "$dir" ]] && is_project_dir "$dir"; then
    echo "$dir"
    return
  fi

  command_exists git || fail "git is required to install from $REPO_URL"

  log "Installing STT into $INSTALL_DIR"
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" pull --ff-only
  else
    mkdir -p "$(dirname -- "$INSTALL_DIR")"
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi

  echo "$INSTALL_DIR"
}

sync_python_environment() {
  local project_dir="$1"

  log "Installing Python dependencies with uv"
  cd "$project_dir"
  export HF_HOME="${STT_HF_HOME:-$project_dir/.cache/huggingface}"
  export XDG_CACHE_HOME="${STT_XDG_CACHE_HOME:-$project_dir/.cache}"
  export UV_CACHE_DIR="${STT_UV_CACHE_DIR:-$project_dir/.cache/uv}"
  uv sync --python 3.12 --no-dev
}

download_model() {
  local project_dir="$1"

  log "Downloading local STT model if needed"
  cd "$project_dir"
  uv run --no-dev python - <<'PY'
from stt_app.transcriber import load_model

load_model("small", device="cpu", compute_type="int8")
print("Model ready: Systran/faster-whisper-small")
PY
}

install_launcher() {
  local project_dir="$1"

  log "Installing stt command"
  mkdir -p "$BIN_DIR"
  ln -sfn "$project_dir/stt" "$BIN_DIR/stt"

  echo "Installed: $BIN_DIR/stt"
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo
    echo "Add this to your shell profile if 'stt' is not found:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
  fi
}

main() {
  install_uv_if_missing
  install_system_dependencies

  local project_dir
  project_dir="$(resolve_project_dir)"

  sync_python_environment "$project_dir"
  download_model "$project_dir"
  install_launcher "$project_dir"

  cat <<EOF

STT is installed.

Next:
  1. Grant Microphone, Accessibility, and Input Monitoring permissions to your terminal.
  2. Restart the terminal.
  3. Run:

     stt listen

EOF
}

main "$@"
