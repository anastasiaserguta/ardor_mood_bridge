$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$src = Join-Path $root "src\ardor_mood.py"
$out = Join-Path $root "ArdorMood.ts4script"
$staging = Join-Path $root "build"

if (-not (Test-Path $src)) {
    throw "Missing source file: $src"
}

$python = $null

try {
    $candidate = & py -3.7 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $candidate) {
        $python = $candidate.Trim()
    }
} catch {
}

if (-not $python) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python37\python.exe",
        "C:\Python37\python.exe",
        "C:\Program Files\Python37\python.exe",
        "C:\Program Files (x86)\Python37\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $python = $candidate
            break
        }
    }
}

if (-not $python) {
    throw "Python 3.7 not found. Install Python 3.7 x64, then run: py -0p"
}

Write-Host "Using Python: $python"
& $python -c "import sys; assert sys.version_info[:2] == (3, 7), sys.version; print(sys.version)"
if ($LASTEXITCODE -ne 0) {
    throw "Selected Python is not 3.7"
}

$cacheDir = Join-Path (Split-Path $src) "__pycache__"
if (Test-Path $cacheDir) {
    Remove-Item $cacheDir -Recurse -Force
}

& $python -m py_compile $src
if ($LASTEXITCODE -ne 0) {
    throw "py_compile failed"
}

$pyc = Get-ChildItem $cacheDir -Filter "ardor_mood.cpython-37.pyc" | Select-Object -First 1
if (-not $pyc) {
    throw "Compiled cpython-37 pyc not found in $cacheDir"
}

if (Test-Path $out) {
    Remove-Item $out -Force
}

if (Test-Path $staging) {
    Remove-Item $staging -Recurse -Force
}

& $python -c "import sys, zipfile; pyc=sys.argv[1]; out=sys.argv[2]; z=zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED); z.write(pyc, 'ardor_mood/__init__.pyc'); z.close()" $pyc.FullName $out
if ($LASTEXITCODE -ne 0) {
    throw "zip packaging failed"
}

Write-Host "Built: $out"
Write-Host "Contents:"
& $python -c "import sys, zipfile; z=zipfile.ZipFile(sys.argv[1]); [print('  %s %s bytes' % (i.filename, i.file_size)) for i in z.infolist()]" $out
