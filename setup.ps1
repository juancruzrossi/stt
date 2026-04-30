$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

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

uv sync --python 3.12

Write-Host ""
Write-Host "Setup complete."
Write-Host ""
Write-Host "Try:"
Write-Host "  .\stt.cmd doctor"
Write-Host "  .\stt.cmd preload --model small"
Write-Host "  .\stt.cmd listen --model small"
