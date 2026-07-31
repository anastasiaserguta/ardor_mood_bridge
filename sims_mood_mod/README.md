# ArdorMood Sims 4 Script Mod

This script mod writes the active Sim mood to:

```text
Documents\Electronic Arts\The Sims 4\ardor_mood.txt
```

The bridge can read that file with `--mood-watch` and send the full Sims emotion palette to the ARDOR keyboard.

## Install

Copy:

```text
ArdorMood.ts4script
```

to:

```text
Documents\Electronic Arts\The Sims 4\Mods
```

In The Sims 4 settings, enable:

```text
Enable Custom Content and Mods
Script Mods Allowed
```

Restart the game after changing those settings.

## Run Bridge

With Flask test endpoints:

```powershell
python ardor_chroma_bridge.py --path-index 4 --protocol official_static --transport write --mood-watch --mood-interval 0.2 --debug
```

File watcher only, without Flask:

```powershell
python ardor_chroma_bridge.py --path-index 4 --protocol official_static --transport write --mood-watch --mood-interval 0.2 --no-server
```

The mod log is:

```text
Documents\Electronic Arts\The Sims 4\ardor_mood_mod.log
```

The bridge reads:

```text
Documents\Electronic Arts\The Sims 4\ardor_mood.txt
```

If `ardor_mood_mod.log` does not appear, the script mod was not loaded by the game.

## If The Mod Is Listed But Does Not Run

The first prototype may be visible in the Sims mod list but not executed, because Sims script mods usually need Python 3.7 bytecode.

Check installed Python versions:

```powershell
py -0p
```

If Python 3.7 is installed, build a compiled script:

```powershell
cd path\to\sims_mood_mod
powershell -ExecutionPolicy Bypass -File .\build_ts4script_py37.ps1
```

Then copy the rebuilt `ArdorMood.ts4script` to:

```text
Documents\Electronic Arts\The Sims 4\Mods
```

Restart the game.

The rebuilt archive should contain:

```text
ardor_mood/__init__.pyc
```

This mirrors the package-style layout used by working script mods such as `lot51_core.ts4script`.
