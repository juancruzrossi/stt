#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BUILD_DIR="$ROOT_DIR/.build/app"
DIST_DIR="$ROOT_DIR/dist"
APP_PATH="$DIST_DIR/STT.app"
MODEL_PATH="$ROOT_DIR/.models/faster-whisper-base"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ "$(uname -s)" == "Darwin" ]] || fail "STT supports macOS only."
command -v uv >/dev/null 2>&1 || fail "uv is required to build STT."
[[ -f "$MODEL_PATH/model.bin" ]] || fail "Run ./install.sh to download the model."

if [[ -e "$BUILD_DIR" ]]; then
  rm -rf -- "$BUILD_DIR"
fi
if [[ -e "$APP_PATH" ]]; then
  rm -rf -- "$APP_PATH"
fi
mkdir -p -- "$BUILD_DIR" "$DIST_DIR"

cd "$ROOT_DIR/app"
uv run --frozen --no-sync --group build \
  python setup.py py2app \
  --bdist-base "$BUILD_DIR" \
  --dist-dir "$DIST_DIR"

/usr/bin/codesign --force --deep --sign - "$APP_PATH"
printf 'Built: %s\n' "$APP_PATH"
