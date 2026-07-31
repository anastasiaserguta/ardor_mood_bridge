$ErrorActionPreference = "Stop"

$exportsFile = Join-Path $PSScriptRoot "exports.txt"
$defFile = Join-Path $PSScriptRoot "CChromaEditorLibrary64.def"
$sourceFile = Join-Path $PSScriptRoot "stub.cpp"
$outFile = Join-Path $PSScriptRoot "CChromaEditorLibrary64.dll"

if (-not (Test-Path $exportsFile)) {
    throw "exports.txt not found"
}

if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    throw "cl.exe not found. Run this from 'x64 Native Tools Command Prompt for VS 2022' or install Visual Studio Build Tools with Desktop development with C++."
}

$exports = Get-Content $exportsFile | Where-Object { $_.Trim() }
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("LIBRARY CChromaEditorLibrary64")
$lines.Add("EXPORTS")

foreach ($name in $exports) {
    $target = "StubReturnZero"

    if ($name -match "^(PluginCoreInit|PluginInit|PluginInitD)$") {
        $target = "StubInit"
    } elseif ($name -match "^(PluginCoreUnInit|PluginUninit|PluginUninitD)$") {
        $target = "StubUninit"
    } elseif ($name -match "^(PluginIsInitialized|PluginIsInitializedD|PluginIsPlatformSupported|PluginIsPlatformSupportedD)$") {
        $target = "StubReturnOne"
    } elseif ($name -match "^(PluginPlayAnimationName|PluginPlayAnimationNameD|PluginPlayAnimationLoop|PluginPlayAnimation|PluginPlayAnimationD|PluginOpenEditorDialogAndPlay|PluginOpenEditorDialogAndPlayD|PluginUseIdleAnimation|PluginUseIdleAnimations|PluginUseIdleAnimationName|PluginSetIdleAnimation|PluginSetIdleAnimationName|PluginLoadAnimationName|PluginLoadAnimation|PluginLoadAnimationD|PluginOpenAnimation|PluginOpenAnimationD)$") {
        $target = "StubAnimationName"
    } elseif ($name -match "^(PluginStopAll|PluginStopAnimation|PluginStopAnimationD|PluginStopAnimationName|PluginStopAnimationNameD|PluginStopAnimationType|PluginStopAnimationTypeD|PluginStopComposite|PluginStopCompositeD|PluginCloseAll)$") {
        $target = "StubStop"
    }

    $lines.Add("    $name=$target")
}

Set-Content -Path $defFile -Value $lines -Encoding ASCII

Push-Location $PSScriptRoot
try {
    cl.exe /nologo /LD /EHsc /O2 $sourceFile /link /nologo /DEF:$defFile /OUT:$outFile ws2_32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "cl.exe failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

if (-not (Test-Path $outFile)) {
    throw "Build finished without creating $outFile"
}

Write-Host ""
Write-Host "Built: $outFile"
Write-Host "Log file at runtime: $env:TEMP\ardor_chroma_stub.log"
