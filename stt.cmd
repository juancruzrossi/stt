@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "HF_HOME=%ROOT_DIR%.cache\huggingface"
set "XDG_CACHE_HOME=%ROOT_DIR%.cache"
set "UV_CACHE_DIR=%ROOT_DIR%.cache\uv"

where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed. Run install.ps1 first.
  exit /b 1
)

cd /d "%ROOT_DIR%"
uv run python -m stt_app %*
