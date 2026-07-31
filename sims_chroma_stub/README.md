# Sims Chroma Stub for ARDOR Bridge

This is a replacement `CChromaEditorLibrary64.dll` for The Sims 4 experiments.
It logs Chroma animation calls and forwards coarse colors to the Python ARDOR bridge at `127.0.0.1:54235`.

## Build on Windows

Install Visual Studio Build Tools 2022 with:

```text
Desktop development with C++
```

Open:

```text
x64 Native Tools Command Prompt for VS 2022
```

Then run:

```powershell
cd path\to\sims_chroma_stub
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The output should be:

```text
CChromaEditorLibrary64.dll
```

## Install into Sims

Close The Sims 4.

In the Sims `Game\Bin` folder, back up the original:

```powershell
cd "D:\Games\The Sims 4\Game\Bin"
ren CChromaEditorLibrary64.dll CChromaEditorLibrary64.original.dll
```

Copy the newly built `CChromaEditorLibrary64.dll` into that same folder.

Start the Python bridge first:

```powershell
python ardor_chroma_bridge.py --path-index 4 --protocol official_static --transport write --debug
```

Then start The Sims 4, enable the lighting checkbox, and load into a household.

## Check Logs

The stub writes:

```text
%TEMP%\ardor_chroma_stub.log
```

Quick check:

```powershell
Get-Content "$env:TEMP\ardor_chroma_stub.log" -Tail 80 -Wait
```

If the log says `loaded`, the DLL replacement is being used.
If it says `animation ...`, Sims is calling Chroma animation playback.
If it says `bridge GET ... -> ok`, the Python bridge received the color request.
If it says `trace ...`, Sims called a lower-level color/effect/frame API; send those lines back so the stub can be taught to use the real RGB values instead of only animation names.

## Restore Original

Close The Sims 4, then:

```powershell
cd "D:\Games\The Sims 4\Game\Bin"
del CChromaEditorLibrary64.dll
ren CChromaEditorLibrary64.original.dll CChromaEditorLibrary64.dll
```
