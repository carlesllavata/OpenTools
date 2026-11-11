# OpenTools

An open-source hub for 3ds Max that bundles everyday tools into **one install**.
When a new 3ds Max version comes out, you reinstall a single package and every
tool is back: in a dockable panel, in a searchable command palette, and as
macros you can bind to hotkeys.

- 3ds Max 2025 and later (Python 3 / PySide6 + MAXScript, no compiled plugins)
- Every tool is a folder with a small `tool.json` manifest; the hub builds itself from them
- Tools load lazily and run isolated: one broken tool never takes the others down
- Settings live in `%APPDATA%\OpenTools` (clipboard slots in `%LOCALAPPDATA%\OpenTools`), so they
  survive 3ds Max upgrades

OpenTools is part of [Open3D](https://github.com/carlesllavata/Open3D), a suite of open-source tools for
3D work. It was called **Open3DS** until version 0.5.0.

> Status: early (v0.5.2). The hub, palette and macros work, with 28 tools: scene
> checks and repairs (Auditor), relinking and collecting the scene's files (Relink Assets, Collect Assets),
> proxy and XRef managers, modeling and DWG helpers, material copy / paste and a clipboard of objects,
> materials and more with network targets. The interface and icons
> are provisional.
> What each version adds: [CHANGELOG.md](CHANGELOG.md).

## Install

1. The easy way: install the [Open3D Launcher](https://github.com/carlesllavata/Open3D/releases/latest)
   and click **Install** next to OpenTools, with 3ds Max closed. The launcher also tells you when a new
   version is out and updates it. By hand instead: with 3ds Max closed, copy the `OpenTools.bundle` folder
   to `%APPDATA%\Autodesk\ApplicationPlugins\` (create the folder if it does not exist). Either way, if an
   old `Open3DS.bundle` is there, delete it.
2. Start 3ds Max. The OpenTools panel docks on the right: tool buttons (icon and name)
   in foldable sections by category, with category filters and a search box on top. Click
   a button to run the tool; right-click it to add it to favorites. Icon size and names are
   in the `⋯` menu. The panel and the tool windows take their colors from the 3ds Max theme.
   The **OpenTools** menu in the main menu bar shows or hides the panel (if you close it, that
   is where it comes back), opens the command palette and lists every tool by category.
3. The **Materials** section holds the material bar, a layer-style drop-down of the
   scene's materials (like the AutoCAD layer list): choose a material or pick it from an
   object with the eyedropper, then apply it to the selection or select every object
   that uses it (Shift+click adds). A thin row above it shows the material of the selected
   object ("—" when several are selected) without touching the one you work with: ↓ makes
   it the working material, double-click selects the objects that use it. Type in the
   drop-down to filter; right-click it for the Material Editor and the "apply when chosen"
   and "show the selected object's material" options. Hide it from the `⋯` menu.
   Below the bar, the Copy / Paste Material buttons copy an object's material and mapping
   modifiers and paste them onto other objects; "Paste Material Copy" pastes an independent
   copy of the material and makes it the current one in the bar, ready to edit.
4. Optional: in *Customize > Hotkey Editor*, category **OpenTools**, bind
   `OpenTools Command Palette` (for example to `Ctrl+Space`) and any tool you use often.

To uninstall, choose **Uninstall…** in OpenTools' menu in the launcher, or delete the `OpenTools.bundle` folder
with 3ds Max closed. Your settings stay in `%APPDATA%\OpenTools` and
`%LOCALAPPDATA%\OpenTools`; delete those too for a clean removal.

## Layout

```
OpenTools.bundle/                Autodesk ApplicationPlugins package (what users install)
  PackageContents.xml
  Contents/
    scripts/opentools_startup.ms Boots the Python side after 3ds Max starts
    python/opentools/            Core: registry, runner, macros, settings, UI, dev bridge
    tools/<tool_id>/             One folder per tool: tool.json + code
dev/                             Developer scripts (dev install, bridge client, test runner)
tests/                           Offline tests that run without 3ds Max
```

## Adding a tool

Create `OpenTools.bundle/Contents/tools/<tool_id>/tool.json`:

```json
{
  "id": "select_instances",
  "name": "Select Instances",
  "category": "Selection",
  "description": "Selects every instance of the selected object.",
  "entry": "select_instances.ms",
  "keywords": ["instance", "select"],
  "author": "Your Name",
  "license": "GPL-3.0-or-later"
}
```

| Field | Required | Notes |
|---|---|---|
| `id` | yes | 2–48 lowercase letters, digits and `_`, starting with a letter; must be unique. The macro is named `OpenTools_<id>` |
| `name` | yes | shown in the hub, palette and Hotkey Editor |
| `entry` | yes | `file.ms` (MAXScript, run with `fileIn`) or `file.py:function` (Python) |
| `category` | no | groups tools in the hub (default `General`) |
| `description`, `keywords` | no | used by search and tooltips |
| `icon` | no | image file inside the tool folder (SVG or PNG). Without it, an `icon.svg` / `icon.png` next to `tool.json` is used; otherwise the hub draws a badge with the tool's initials in its category color |
| `min_max`, `max_max` | no | supported 3ds Max years, e.g. `2025` |
| `author`, `license`, `source_url` | no | credit and licensing of the tool |

Python tools are loaded as a package, so a tool can split its code into several
files and use relative imports (`from . import helpers`).

Only add code that may be distributed under this repository's license
(GPL-3.0-or-later): code you wrote yourself, public-domain code or code under a
GPL-compatible license. `license` states the tool's license.

## Development

Requirements: 3ds Max 2025+ on Windows. The Python bundled with 3ds Max is enough.

```powershell
# Load OpenTools straight from this checkout (instead of a copied bundle) and enable the dev bridge.
# Don't keep OpenTools.bundle installed at the same time: 3ds Max loads only one of them.
# Remove it again with dev\uninstall_dev.ps1. Restart 3ds Max after either.
powershell -ExecutionPolicy Bypass -File dev\install_dev.ps1

# Run the offline tests
& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -I dev\run_tests.py

# Talk to the running 3ds Max (needs the dev install)
& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -I dev\bridge.py ping
& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -I dev\bridge.py -c "print(rt.objects.count)"
& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -I dev\bridge.py reload
```

The dev bridge watches `.devbridge/inbox` in this checkout, runs each `.py` file
dropped there inside 3ds Max and writes the result to `.devbridge/outbox`. It only
runs when OpenTools was loaded through `dev/install_dev.ps1`.

## License

Copyright (C) 2026 Carles Llavata and OpenTools contributors.

OpenTools is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option)
any later version. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See [LICENSE](LICENSE) for the full
text of the GNU General Public License v3 (SPDX: `GPL-3.0-or-later`).
