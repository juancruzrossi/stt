@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "HF_HOME=%ROOT_DIR%.cache\huggingface"
set "XDG_CACHE_HOME=%ROOT_DIR%.cache"
set "STT_MODEL_PATH=%ROOT_DIR%.models\faster-whisper-small"
set "HF_HUB_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "HF_HUB_DISABLE_IMPLICIT_TOKEN=1"
set "DO_NOT_TRACK=1"

if not exist "%ROOT_DIR%.venv\Scripts\python.exe" (
  echo STT environment is missing. Run install.ps1 first.
  exit /b 1
)

cd /d "%ROOT_DIR%"
"%ROOT_DIR%.venv\Scripts\python.exe" -m stt %*
