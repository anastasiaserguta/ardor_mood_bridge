$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Select-BridgePython {
  $candidates = @(
    @{ Exe = "py"; Args = @("-3.12") },
    @{ Exe = "py"; Args = @("-3.11") },
    @{ Exe = "py"; Args = @("-3.10") },
    @{ Exe = "python"; Args = @() }
  )

  foreach ($candidate in $candidates) {
    if (!(Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) {
      continue
    }

    & $candidate.Exe @($candidate.Args) -c "import sys; raise SystemExit(0 if sys.version_info < (3, 13) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
      $script:PythonExe = $candidate.Exe
      $script:PythonPrefixArgs = $candidate.Args
      & $script:PythonExe @($script:PythonPrefixArgs) -c "import sys; print('Using Python:', sys.executable); print(sys.version)"
      return
    }
  }

  throw "Python 3.12 or 3.11 is recommended for this build. Python 3.13 may try to build hidapi from source and require Visual C++ Build Tools."
}

function Invoke-BridgePython {
  & $script:PythonExe @($script:PythonPrefixArgs) @args

  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed: $args"
  }
}

Select-BridgePython
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
