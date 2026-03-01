$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Ensure venv exists and is activated in this shell.
. (Join-Path $PSScriptRoot "activate_venv.ps1")

Write-Host "Starting bot..."
python bot.py
