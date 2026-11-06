# Open3DS – notes for Claude

Open-source, single-install hub for 3ds Max (2025+). The user's environment: 3ds Max 2027,
Python 3.13 (bundled with Max), PySide6, Corona. The repo lives on a NAS share (`Z:` maps to
`\\192.168.2.10\...`). Talk to the user in Spanish; code, comments and docs in English.

## Layout
- `Open3DS.bundle/` – the ApplicationPlugins package users install. Version lives in
  `PackageContents.xml` (AppVersion + ComponentEntry Version) **and** `open3ds/__init__.py`; keep them equal.
  Max 2027 silently ignores a package whose RuntimeRequirements lack `SeriesMax` (we use `2099` = no cap).
- In non-interactive sessions (3dsmaxbatch, render nodes) only tools and macros load; no hub, no bridge.
- `Open3DS.bundle/Contents/python/open3ds/` – core. Modules without Qt/pymxs imports at top level
  (`registry`, `search`, `macros.macro_source`, `settings`, `runner`) must stay importable outside Max:
  the offline tests rely on it. Anything touching 3ds Max goes through `maxhost.py`.
- `Open3DS.bundle/Contents/tools/<id>/tool.json` – one folder per tool; schema in README.
- `dev/` – `install_dev.ps1` (dev shim bundle in `%APPDATA%\Autodesk\ApplicationPlugins\Open3DS-dev.bundle`
  that loads this checkout and enables the bridge), `bridge.py` (client), `run_tests.py`.

## Commands
Max's Python: `C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe` (always run with `-I`).
- Tests: `python -I dev\run_tests.py`
- Live Max: `python -I dev\bridge.py ping | reload | -c "code" | file.py` (code gets `rt`, `pymxs`, `open3ds`;
  assign `_result` to return a value). After editing core code, run `reload`; tool code reloads on every run in dev mode.
- `3dsmaxbatch.exe` is available for headless checks.

## Rules
- Before adding a script the user hands over, ask where it comes from and its license. Own or permissively
  licensed code goes in with attribution; proprietary/unlicensed scripts are reimplemented clean-room from a
  description of behaviour, never from their source. Never decrypt `.mse` or bundle `.dlo/.gup`.
- No SiNi/IgNite names, icons or text.
- Git: `C:\Program Files\Git\cmd\git.exe` (may not be on PATH in older shells). Branch `main`.
  The repo is on a NAS, so it is listed in the global `safe.directory`.
