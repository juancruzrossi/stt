$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir = if ($env:STT_BIN_DIR) { $env:STT_BIN_DIR } else { Join-Path $env:USERPROFILE ".local\bin" }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing uv with winget..."
        winget install --id astral-sh.uv -e
    } else {
        throw "uv is not installed. Install it from https://docs.astral.sh/uv/getting-started/installation/ and rerun this script."
    }
}

Set-Location $RootDir

$env:HF_HOME = if ($env:STT_HF_HOME) { $env:STT_HF_HOME } else { Join-Path $RootDir ".cache\huggingface" }
$env:XDG_CACHE_HOME = if ($env:STT_XDG_CACHE_HOME) { $env:STT_XDG_CACHE_HOME } else { Join-Path $RootDir ".cache" }
$env:UV_CACHE_DIR = if ($env:STT_UV_CACHE_DIR) { $env:STT_UV_CACHE_DIR } else { Join-Path $RootDir ".cache\uv" }

Write-Host "Installing Python dependencies with uv..."
uv sync --python 3.12

Write-Host "Downloading local STT model if needed..."
uv run python -c "from stt_app.transcriber import load_model; load_model('small', device='cpu', compute_type='int8'); print('Model ready: Systran/faster-whisper-small')"

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
