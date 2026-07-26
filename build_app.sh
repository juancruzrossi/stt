#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BUILD_DIR="$ROOT_DIR/.build/app"
DIST_DIR="$ROOT_DIR/dist"
APP_PATH="$DIST_DIR/STT.app"
MODEL_PATH="$ROOT_DIR/.models/faster-whisper-base"
SIGNING_DIR="${STT_SIGNING_DIR:-$HOME/.config/stt/signing}"
SIGNING_KEYCHAIN="$SIGNING_DIR/local-signing.keychain-db"
SIGNING_PASSWORD="$SIGNING_DIR/keychain-password"
SIGNING_IDENTITY="STT Local Code Signing"
SIGNING_TEMP_DIR=""
SIGNING_SEARCH_LIST_CHANGED=false
ORIGINAL_SIGNING_KEYCHAINS=()

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "$SIGNING_TEMP_DIR" && -d "$SIGNING_TEMP_DIR" ]]; then
    find "$SIGNING_TEMP_DIR" -depth -delete
  fi
  if [[ "$SIGNING_SEARCH_LIST_CHANGED" == true ]]; then
    /usr/bin/security list-keychains -d user -s \
      "${ORIGINAL_SIGNING_KEYCHAINS[@]}"
  fi
}

include_signing_keychain() {
  local keychain
  local line

  while IFS= read -r line; do
    keychain="${line#*\"}"
    keychain="${keychain%\"*}"
    [[ -n "$keychain" ]] || continue
    [[ "$keychain" == "$SIGNING_KEYCHAIN" ]] && return
    ORIGINAL_SIGNING_KEYCHAINS+=("$keychain")
  done < <(/usr/bin/security list-keychains -d user)

  /usr/bin/security list-keychains -d user -s \
    "$SIGNING_KEYCHAIN" \
    "${ORIGINAL_SIGNING_KEYCHAINS[@]}"
  SIGNING_SEARCH_LIST_CHANGED=true
}

create_local_signing_identity() {
  local password="$1"

  SIGNING_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/stt-signing.XXXXXX")"
  /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$SIGNING_TEMP_DIR/key.pem" \
    -out "$SIGNING_TEMP_DIR/certificate.pem" \
    -days 3650 \
    -subj "/CN=$SIGNING_IDENTITY/O=STT Local Development" \
    -addext "keyUsage=critical,digitalSignature" \
    -addext "extendedKeyUsage=critical,codeSigning" >/dev/null 2>&1
  /usr/bin/openssl pkcs12 -export \
    -inkey "$SIGNING_TEMP_DIR/key.pem" \
    -in "$SIGNING_TEMP_DIR/certificate.pem" \
    -out "$SIGNING_TEMP_DIR/identity.p12" \
    -passout "pass:$password" >/dev/null 2>&1
  /usr/bin/security import "$SIGNING_TEMP_DIR/identity.p12" \
    -k "$SIGNING_KEYCHAIN" \
    -P "$password" \
    -T /usr/bin/codesign >/dev/null
  /usr/bin/security add-trusted-cert \
    -r trustRoot \
    -p codeSign \
    -k "$SIGNING_KEYCHAIN" \
    "$SIGNING_TEMP_DIR/certificate.pem"
  /usr/bin/security set-key-partition-list \
    -S apple-tool:,apple:,codesign: \
    -s \
    -k "$password" \
    "$SIGNING_KEYCHAIN" >/dev/null
}

ensure_local_signing_identity() {
  local password

  mkdir -p "$SIGNING_DIR"
  chmod 700 "$SIGNING_DIR"
  if [[ ! -f "$SIGNING_PASSWORD" ]]; then
    /usr/bin/openssl rand -hex 32 -out "$SIGNING_PASSWORD"
    chmod 600 "$SIGNING_PASSWORD"
  fi
  IFS= read -r password <"$SIGNING_PASSWORD"
  [[ -n "$password" ]] || fail "Local signing password is empty."

  if [[ ! -f "$SIGNING_KEYCHAIN" ]]; then
    /usr/bin/security create-keychain -p "$password" "$SIGNING_KEYCHAIN"
    create_local_signing_identity "$password"
  fi

  /usr/bin/security unlock-keychain -p "$password" "$SIGNING_KEYCHAIN"
  /usr/bin/security set-keychain-settings -lut 3600 "$SIGNING_KEYCHAIN"
  /usr/bin/security find-identity -v -p codesigning "$SIGNING_KEYCHAIN" |
    /usr/bin/grep -F "\"$SIGNING_IDENTITY\"" >/dev/null ||
    fail "Local STT signing identity is unavailable."
}

sign_app() {
  local identity="${STT_CODESIGN_IDENTITY:-}"

  if [[ -z "$identity" && "${CI:-}" == "true" ]]; then
    identity="-"
  elif [[ -z "$identity" ]]; then
    ensure_local_signing_identity
    include_signing_keychain
    identity="$SIGNING_IDENTITY"
  fi
  /usr/bin/codesign --force --deep \
    --sign "$identity" \
    "$APP_PATH"
}

trap cleanup EXIT

[[ "$(uname -s)" == "Darwin" ]] || fail "STT supports macOS only."
command -v uv >/dev/null 2>&1 || fail "uv is required to build STT."
[[ -f "$MODEL_PATH/model.bin" ]] || fail "Bundled model is missing."

if [[ -e "$BUILD_DIR" ]]; then
  rm -rf -- "$BUILD_DIR"
fi
if [[ -e "$APP_PATH" ]]; then
  rm -rf -- "$APP_PATH"
fi
mkdir -p -- "$BUILD_DIR" "$DIST_DIR"

cd "$ROOT_DIR/app"
uv run --isolated --frozen --no-dev --group build \
  python setup.py py2app \
  --bdist-base "$BUILD_DIR" \
  --dist-dir "$DIST_DIR"

sign_app
printf 'Built: %s\n' "$APP_PATH"
