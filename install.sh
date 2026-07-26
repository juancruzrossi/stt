#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BIN_DIR="${STT_BIN_DIR:-$HOME/.local/bin}"
APP_DIR="${STT_APP_DIR:-$HOME/Applications}"

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
  [[ -f "$1/pyproject.toml" && -d "$1/src/stt" ]]
}

require_uv() {
  command_exists uv || fail \
    "uv is required. Install it through your approved package manager, then rerun install.sh."
}

check_platform() {
  [[ "$(uname -s)" == "Darwin" ]] || fail "STT supports macOS only."
}

resolve_project_dir() {
  local dir
  dir="$(script_dir || true)"

  if [[ -z "$dir" ]] || ! is_project_dir "$dir"; then
    fail "Run install.sh from a reviewed local STT checkout; remote pipe installs are disabled."
  fi
  echo "$dir"
}

sync_python_environment() {
  local project_dir="$1"

  log "Installing Python dependencies with uv"
  cd "$project_dir"
  export HF_HOME="${STT_HF_HOME:-$project_dir/.cache/huggingface}"
  export XDG_CACHE_HOME="${STT_XDG_CACHE_HOME:-$project_dir/.cache}"
  export UV_CACHE_DIR="${STT_UV_CACHE_DIR:-$project_dir/.cache/uv}"
  export UV_NO_MODIFY_PATH=1
  export UV_PYTHON_DOWNLOADS=never
  export HF_HUB_DISABLE_TELEMETRY=1
  export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
  export DO_NOT_TRACK=1
  uv python find 3.12 >/dev/null 2>&1 || fail \
    "Python 3.12 is required. Install it through your approved package manager."
  uv sync --locked --python 3.12 --no-dev --group build
}

download_model() {
  local project_dir="$1"

  log "Downloading local STT model if needed"
  cd "$project_dir"
  export STT_MODEL_PATH="${STT_MODEL_PATH:-$project_dir/.models/faster-whisper-base}"
  uv run --frozen --no-sync --no-dev python -m stt.install_model "$STT_MODEL_PATH"
  chmod go-rwx \
    "$project_dir/.venv" \
    "$STT_MODEL_PATH" \
    "$STT_MODEL_PATH/config.json" \
    "$STT_MODEL_PATH/model.bin" \
    "$STT_MODEL_PATH/tokenizer.json" \
    "$STT_MODEL_PATH/vocabulary.txt"
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

install_app() {
  local project_dir="$1"
  local source_app="$project_dir/dist/STT.app"
  local destination="$APP_DIR/STT.app"
  local bundle_id="com.juancruzrossi.stt"
  local old_requirement=""
  local new_requirement

  log "Building STT.app for $(uname -m)"
  "$project_dir/build_app.sh"
  [[ -d "$source_app" ]] || fail "STT.app build did not produce an application."
  new_requirement="$(
    /usr/bin/codesign -d -r- "$source_app" 2>&1 |
      /usr/bin/tail -n 1
  )"

  [[ -n "$APP_DIR" && "$APP_DIR" != "/" ]] || fail "Invalid app directory."
  mkdir -p "$APP_DIR"
  if [[ -e "$destination" || -L "$destination" ]]; then
    [[ -d "$destination" && -f "$destination/Contents/Info.plist" ]] || \
      fail "Refusing to replace a non-application path: $destination"
    old_requirement="$(
      /usr/bin/codesign -d -r- "$destination" 2>&1 |
        /usr/bin/tail -n 1
    )"
    rm -rf -- "$destination"
  fi
  /usr/bin/ditto "$source_app" "$destination"
  /usr/bin/codesign --verify --deep --strict "$destination"
  if [[ -n "$old_requirement" && "$old_requirement" != "$new_requirement" ]]; then
    /usr/bin/tccutil reset Accessibility "$bundle_id" >/dev/null
  fi
  echo "Installed: $destination"
}

main() {
  require_uv
  check_platform

  local project_dir
  project_dir="$(resolve_project_dir)"

  sync_python_environment "$project_dir"
  download_model "$project_dir"
  install_launcher "$project_dir"
  install_app "$project_dir"

  cat <<EOF

STT is installed in:

  $APP_DIR/STT.app

Next:
  1. Open STT from your Applications folder.
  2. Grant Microphone and Accessibility permissions to STT.
  3. Choose your shortcut and activation mode in Settings.

EOF
}

main "$@"
