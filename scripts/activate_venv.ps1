$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WindowsVenv = Join-Path $ProjectRoot "venv-win"
$FallbackVenv = Join-Path $ProjectRoot "venv"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    throw "Python is not installed or not in PATH."
}

function Activate-WindowsVenv([string]$VenvPath) {
    $ActivateScript = Join-Path $VenvPath "Scripts/Activate.ps1"
    if (!(Test-Path $ActivateScript)) {
        throw "Could not find activation script at $ActivateScript"
    }
    . $ActivateScript
    Write-Host "Activated virtual environment: $VenvPath"
}

if (Test-Path (Join-Path $WindowsVenv "Scripts/Activate.ps1")) {
    Activate-WindowsVenv -VenvPath $WindowsVenv
    return
}

if (Test-Path (Join-Path $FallbackVenv "Scripts/Activate.ps1")) {
    Activate-WindowsVenv -VenvPath $FallbackVenv
    return
}

if (Test-Path (Join-Path $FallbackVenv "bin/activate")) {
    throw "Found Linux venv at '$FallbackVenv'. Create a Windows venv with: py -m venv venv-win"
}

$Python = Get-PythonCommand
Write-Host "Creating venv-win..."
& $Python -m venv $WindowsVenv

Write-Host "Installing dependencies..."
& (Join-Path $WindowsVenv "Scripts/python.exe") -m pip install -r $Requirements

Activate-WindowsVenv -VenvPath $WindowsVenv
