$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw ".venv was not found. Follow the setup steps in README.md first."
}

Set-Location $projectRoot
& $venvPython -m uvicorn classroom_simulator.main:app --reload --host 127.0.0.1 --port 8000

