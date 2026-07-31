$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Invoke-BridgePython {
  if (Get-Command python -ErrorAction SilentlyContinue) {
    python @args
  } else {
    py -3 @args
  }

  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed: $args"
  }
}

Invoke-BridgePython -m pip install --upgrade pip

if (Test-Path "$root\requirements.txt") {
  Invoke-BridgePython -m pip install -r requirements.txt
} else {
  Write-Host "requirements.txt not found, installing bridge dependencies directly."
  Invoke-BridgePython -m pip install flask hidapi
}

Invoke-BridgePython -m pip install pyinstaller

if (!(Test-Path "$root\ardor_mood_bridge_gui.py")) {
  throw "Missing ardor_mood_bridge_gui.py. Build from the folder that contains all bridge .py files."
}

Invoke-BridgePython -m PyInstaller `
  --clean `
  --onefile `
  --windowed `
  --collect-all hid `
  --name ArdorMoodBridge `
  ardor_mood_bridge_gui.py

Write-Host ""
Write-Host "Built: $root\dist\ArdorMoodBridge.exe"
Write-Host "Run it, press 'Тест focused', then 'Старт' for Sims mood watching."
