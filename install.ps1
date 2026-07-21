$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir = if ($env:STT_BIN_DIR) { $env:STT_BIN_DIR } else { Join-Path $env:USERPROFILE ".local\bin" }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it through your approved package manager and rerun this script."
}

Set-Location $RootDir

$env:HF_HOME = if ($env:STT_HF_HOME) { $env:STT_HF_HOME } else { Join-Path $RootDir ".cache\huggingface" }
$env:XDG_CACHE_HOME = if ($env:STT_XDG_CACHE_HOME) { $env:STT_XDG_CACHE_HOME } else { Join-Path $RootDir ".cache" }
$env:UV_CACHE_DIR = if ($env:STT_UV_CACHE_DIR) { $env:STT_UV_CACHE_DIR } else { Join-Path $RootDir ".cache\uv" }
$env:STT_MODEL_PATH = if ($env:STT_MODEL_PATH) { $env:STT_MODEL_PATH } else { Join-Path $RootDir ".models\faster-whisper-small" }
$env:UV_NO_MODIFY_PATH = "1"
$env:UV_PYTHON_DOWNLOADS = "never"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = "1"
$env:DO_NOT_TRACK = "1"

uv python find 3.12 *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 is required. Install it through your approved package manager."
}

Write-Host "Installing Python dependencies with uv..."
uv sync --locked --python 3.12 --no-dev

Write-Host "Downloading local STT model if needed..."
uv run --frozen --no-sync --no-dev python -m stt.install_model $env:STT_MODEL_PATH

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$CmdPath = Join-Path $BinDir "stt.cmd"
Set-Content -Path $CmdPath -Value "@echo off`r`n`"$RootDir\stt.cmd`" %*`r`n"

Write-Host ""
Write-Host "STT is installed."
Write-Host "Installed command: $CmdPath"
Write-Host ""
Write-Host "If 'stt' is not found, add this directory to PATH:"
Write-Host "  $BinDir"
Write-Host ""
Write-Host "Then run:"
Write-Host "  stt listen"
