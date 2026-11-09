# Open3DS

An open-source hub for 3ds Max that bundles everyday tools into **one install**.
When a new 3ds Max version comes out, you reinstall a single package and every
tool is back: in a dockable panel, in a searchable command palette, and as
macros you can bind to hotkeys.

- 3ds Max 2025 and later (Python 3 / PySide6 + MAXScript, no compiled plugins)
- Every tool is a folder with a small `tool.json` manifest; the hub builds itself from them
- Tools load lazily and run isolated: one broken tool never takes the others down
- Settings live in `%APPDATA%\Open3DS`, so they survive 3ds Max upgrades

> Status: early (v0.4.0). The hub, palette and macros work, with 27 tools: scene
> checks and repairs (Forensic), asset, proxy and XRef managers, modeling and DWG helpers,
> material copy / paste and an object clipboard with network targets. The interface and icons
> are provisional.
> What each version adds: [CHANGELOG.md](CHANGELOG.md) (in Spanish).

## Install

1. Copy the `Open3DS.bundle` folder to `%APPDATA%\Autodesk\ApplicationPlugins\`
   (create the folder if it does not exist).
2. Start 3ds Max. The Open3DS panel docks on the right: tool buttons (icon and name)
   in foldable sections by category, with category filters and a search box on top. Click
   a button to run the tool; right-click it to add it to favorites. Icon size and names are
   in the `⋯` menu. The panel and the tool windows take their colors from the 3ds Max theme.
   The **Open3DS** menu in the main menu bar shows or hides the panel (if you close it, that
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
4. Optional: in *Customize > Hotkey Editor*, category **Open3DS**, bind
   `Open3DS Command Palette` (for example to `Ctrl+Space`) and any tool you use often.

To uninstall, delete that folder.

## Layout

```
Open3DS.bundle/                Autodesk ApplicationPlugins package (what users install)
  PackageContents.xml
  Contents/
    scripts/open3ds_startup.ms Boots the Python side after 3ds Max starts
    python/open3ds/            Core: registry, runner, macros, settings, UI, dev bridge
    tools/<tool_id>/           One folder per tool: tool.json + code
dev/                           Developer scripts (dev install, bridge client, test runner)
tests/                         Offline tests that run without 3ds Max
```

## Adding a tool

Create `Open3DS.bundle/Contents/tools/<tool_id>/tool.json`:

```json
{
  "id": "select_instances",
  "name": "Select Instances",
  "category": "Selection",
  "description": "Selects every instance of the selected object.",
  "entry": "select_instances.ms",
  "keywords": ["instance", "select"],
  "author": "Your Name",
  "license": "MIT"
}
```

| Field | Required | Notes |
|---|---|---|
| `id` | yes | lowercase letters, digits and `_`; must be unique. The macro is named `Open3DS_<id>` |
| `name` | yes | shown in the hub, palette and Hotkey Editor |
| `entry` | yes | `file.ms` (MAXScript, run with `fileIn`) or `file.py:function` (Python) |
| `category` | no | groups tools in the hub (default `General`) |
| `description`, `keywords` | no | used by search and tooltips |
| `icon` | no | image file inside the tool folder (SVG or PNG). Without it, an `icon.svg` / `icon.png` next to `tool.json` is used; otherwise the hub draws a badge with the tool's initials in its category color |
| `min_max`, `max_max` | no | supported 3ds Max years, e.g. `2025` |
| `author`, `license`, `source_url` | no | credit and licensing of the tool |

Python tools are loaded as a package, so a tool can split its code into several
files and use relative imports (`from . import helpers`).

Only add code you wrote yourself or code whose license allows redistribution
under this repository's license, and credit it in `author`/`license`/`source_url`.

## Development

Requirements: 3ds Max 2025+ on Windows. The Python bundled with 3ds Max is enough.

```powershell
# Load Open3DS straight from this checkout (instead of a copied bundle) and enable the dev bridge
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
runs when Open3DS was loaded through `dev/install_dev.ps1`.

## License

MIT, see [LICENSE](LICENSE).
