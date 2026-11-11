# OpenTools – notes for Claude

Open-source, single-install hub for 3ds Max (2025+). The user's environment: 3ds Max 2027,
Python 3.13 (bundled with Max), PySide6, Corona. The repo lives on a NAS share (`Z:` maps to
`\\192.168.2.10\...`).

Called **Open3DS** until 10 November 2026 (prefix `O3DS_`, package `open3ds`, `Open3DS.bundle`); renamed to
OpenTools as a clean cut, with no compatibility layer. Old names in the git history, older changelog entries
and `.devbridge` logs refer to that. Part of the Open3D suite: see `..\..\CLAUDE.md`.

## Open3D suite standards
<!-- Shared block: keep it word for word the same in every Open3D CLAUDE.md (suite root, launcher, each app).
     Any change here is made in all of them in the same session. -->
- **One repo per tool.** Every tool of the Open3D suite, and the launcher, has its own git repository.
  Everything in it is in English: code, comments, docs, app text, commit messages and release notes.
- **Version diary.** Every series of changes to a tool is recorded in `CHANGELOG.md` at the root of its repo,
  in English, newest first, written for users (what changed for them, not code details). Changes not yet
  released go under `## In development`.
- **Language with the user.** Claude always talks to the user in Spanish (castellano).
- **License: GNU GPL v3 or later** (`GPL-3.0-or-later`) for every tool of the suite and the launcher: the full
  text in `LICENSE`, the license named in the README, and `SPDX-License-Identifier: GPL-3.0-or-later` as the
  first comment line of every source file (after a shebang or BOM). Only code that may be distributed under
  it goes in: the user's own, public-domain or GPL-compatible code.
- **README check on every release.** Each time a new version of a tool is published on GitHub (tag and
  release), review its `README.md` against the code and the state of that version first: version, install and
  uninstall steps, features, limits, commands, paths and links. Fix what is out of date in that same release.
- **Keeping these in sync.** This block is identical in the `CLAUDE.md` of the suite root, `launcher/` and
  every app in `apps/` (today `OpenTools` and `OpenManager`). When it changes in one of them, make the same
  change in all of them; every new tool's `CLAUDE.md` starts with this block.

## Layout
- `OpenTools.bundle/` – the ApplicationPlugins package users install. Version lives in
  `PackageContents.xml` (AppVersion + ComponentEntry Version) **and** `opentools/__init__.py`; keep them equal.
  Max 2027 silently ignores a package whose RuntimeRequirements lack `SeriesMax` (we use `2099` = no cap).
- `CHANGELOG.md` – the version diary (see the suite standards; it was Spanish until 9 November 2026).
  After every commit ask whether to publish an entry or make a new version (bump
  both version places, tag `vX.Y.Z`, push, `gh release create` with that version's notes, also in English). gh lives in `%LOCALAPPDATA%\Programs\GitHubCLI\bin\gh.exe`.
  Since 0.5.1 (2026-11-11) OpenTools is in the Open3D Launcher's public catalog: after a release, publishing it
  there is `python -I tools\publish.py opentools` in `..\..\launcher` (ask the user first). That makes the
  bundle's code public.
- In non-interactive sessions (3dsmaxbatch, render nodes) only tools and macros load; no hub, no bridge.
- `OpenTools.bundle/Contents/python/opentools/` – core. Modules without Qt/pymxs imports at top level
  (`registry`, `search`, `macros.macro_source`, `settings`, `runner`) must stay importable outside Max:
  the offline tests rely on it. Anything touching 3ds Max goes through `maxhost.py`.
- `OpenTools.bundle/Contents/tools/<id>/tool.json` – one folder per tool; schema in README.
- Tool ids never change when a tool is renamed (macros, toolbars and saved options hang on them).
  The Auditor (called Forensic until 2026-11-11) lives in `tools/scene_summary` (id kept from Scene
  Inspector). Random Replace lives in `tools/ignite` (id kept from the old Ignite panel, whose copy/paste
  part moved to the Clipboard dashboard, `tools/object_clipboard`, called Object Clipboard until 2026-11-11:
  its paste options show per mode there). The Asset Manager was split on 2026-11-11: Relink Assets keeps
  its id and folder (`tools/asset_manager`), Collect Assets is `tools/collect_assets`; both build on the file
  list in `opentools/ui/assetlist.py`. The card look (`opentools/ui/cards.py`) is provisional.
- `dev/` – `install_dev.ps1` (dev shim bundle in `%APPDATA%\Autodesk\ApplicationPlugins\OpenTools-dev.bundle`
  that loads this checkout and enables the bridge), `bridge.py` (client), `run_tests.py`.

## Commands
Max's Python: `C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe` (always run with `-I`).
- Tests: `python -I dev\run_tests.py`
- Live Max: `python -I dev\bridge.py ping | reload | -c "code" | file.py` (code gets `rt`, `pymxs`, `opentools`;
  assign `_result` to return a value). After editing core code, run `reload`; tool code reloads on every run in dev mode.
  From Windows PowerShell 5.1, `-c` mangles embedded double quotes: write anything non-trivial to a .py file
  (scratchpad) and pass the file. Avoid code that opens modal dialogs (messageBox) – it blocks the bridge
  until the user clicks.
- `3dsmaxbatch.exe` is available for headless checks.

## 3ds Max gotchas (verified in 2027)
- `with pymxs.undo(...)` silently swallows every exception raised inside it. Always use
  `opentools.maxhost.undo(label, enabled=True)`, which closes the undo record and re-raises.
- MAXScript is case-insensitive: a parameter or local named like a built-in function
  (`centerPivot` vs `CenterPivot`) shadows it ("Call needs function or class, got: true").
- Undo a viewport change with `actionMan.executeAction 0 "40104"` (Undo Viewport Operation);
  `max view undo` does not exist.
- Live tests: never create bitmaps pointing at fake image bytes - 3ds Max opens modal "error loading
  bitmap" dialogs and the bridge hangs. Write real images (QImage.save). Operations that may touch
  broken files run inside `maxhost.quiet()`.
- `ResetXForm` on a mirrored (negative scale) object already keeps faces outwards in 2027;
  do not add a Normal flip.
- An unsaved scene created from a template has `maxFileName == ""` but a non-empty `maxFilePath`;
  Asset Tracking then lists the template .max as its first file.
- Inside MAXScript struct methods, a local used in a `where` clause of a `for` that is itself
  an argument (`f (for n in objects where n.material == m collect n)`) fails with "Bad free thunk
  local member index". Write those loops with an explicit `if`.
- Live tests of scene-wide fixes (delete empty layers, ungroup all...) must only run when every
  item found belongs to the test (names `OTL_t*`): the user's open scene is real work (it
  keeps empty template layers like `00_INPUTS`...`ZZ_AUX` on purpose).
- Layer deletion is undoable only inside an undo record. Outside one it is permanent, and an
  earlier undoable move of objects out of that layer then CRASHES 3ds Max 2027 on Ctrl+Z (it
  puts them back on the deleted layer; reproduced in 3dsmaxbatch). Delete layers inside the
  same `maxhost.undo` / `undo on` as the moves. Test risky undo paths in `3dsmaxbatch` first
  (log each step to a file; `local` needs a block there), never in the user's Max.
- A .max file does not record who saved it (the summary's Author/Last Saved By are empty unless
  typed in File Properties); the Windows file owner is the best proxy (empty on the NAS).
- XRef-ing a file made with `saveNodes` opens a modal "obsolete format" warning that hangs the
  bridge: add/update XRefs in live tests inside `maxhost.quiet()`.
- V-Ray and Corona proxies remember the last display value set while their Modify panel is open
  as the default for new proxies (defaults: VRayProxy.display 3, CProxy.previzType 1). Do not
  probe parameters through the Modify panel without setting them back.
- Objects inside an XRef scene cannot be selected; XRef object records can.
- Live tests of the clipboard must point every clipboard folder setting at a temp dir first:
  the default folder holds the user's real slots. Give every scratchpad probe a new file
  name; Write refuses to overwrite an unread file and the old script would run instead.
- `on` is a reserved word in MAXScript (`local on = ...` is a syntax error). Inside a struct, a member
  function must be defined above the members that call it.
- A `.ms` tool whose block does `fileIn core` and then calls a struct the core defines must
  declare that global *above* the block (`global OTL_X` then `( fileIn ...; OTL_X.f() )`):
  the block compiles before the fileIn runs, so on the first run of a session the name becomes
  an empty local ("Unknown property ... in undefined"). Live tests that already loaded the core
  hide this: remove the global first (`globalVars.remove #OTL_X`).
- `getHandleByAnim` returns an IntegerPtr: `as string` gives "30043P". Strip the "P" before
  building Python code for `python.Execute` (a MAXScript tool selects a material in the bar with
  `python.Execute "import opentools.ui.hub as h; h.show_material(<handle>)"`).
- Live tests of `.ms` tools: run the entry with `rt.fileIn(tool.entry_file)`, not `runner.run`;
  the runner shows a modal error dialog on failure, which hangs the bridge.
- `NodeEventCallback` (accepts Python callables) batches events and fires after the operation,
  so a live test must change the scene in one bridge call and read the result in the next. A
  node created and selected in one operation only reports `added`, never `selectionChanged`.
  `for n in selection` copies the whole selection first; index `selection[i]` to stop early.
- Viewport HUDs: `registerRedrawViewsCallback` + `gw.wText` works in 2027 (and shows in
  `gw.getViewportDib`); text drawn inside a `gw.wRect` is hidden, so highlight with color.
- PySide6: `QAction` / `QActionGroup` live in QtGui, not QtWidgets. Qt never opens an empty
  QMenu, so a menu filled only in `aboutToShow` never appears: fill it once when created.
- Tool windows: subclass `opentools.ui.toolwindow.ToolWindow` (one instance, remembered position,
  options in settings `tool_options`; a `"size"` in DEFAULTS is restored and saved by the base,
  `self.confirm(title, text)` asks Yes/Cancel) and wrap button actions with `self.guard(...)`, otherwise
  errors in Qt slots are lost. Settings of the running app: `opentools.app.current_settings()`.
- Look: every OpenTools window gets `ui/theme.py` (`theme.apply(root)`; ToolWindow does it). Colors come
  from the 3ds Max palette (`theme.tokens()`); only the orange accent and status colors are fixed.
  No hard-coded greys or `color: gray` in tools: use `theme.dim_label()` / objectName `OTL_Dim`.
  Buttons follow the Auditor's style; the user wants the Auditor's layout left as it is. Heavy geometry loops go in a MAXScript `*_core.ms` next to the tool.

## Rules
- Before adding a script the user hands over, ask where it comes from and its license. Only code that may go
  under GPL-3.0-or-later goes in (see the suite standards); proprietary/unlicensed scripts are reimplemented
  clean-room from a description of behaviour, never from their source. Never decrypt `.mse` or bundle `.dlo/.gup`.
- Licensed MIT until 10 November 2026, then GPL-3.0-or-later. The tools that started from public-domain
  scripts (Turn to Instance, Copy/Paste Material (+ UVW), Clean DWG, 3-Point Rotate/Scale) carry no third-party
  author credits, by the user's decision: their authors waived authorship. Don't add credits back.
- No SiNi/IgNite names, icons or text.
- Git: `C:\Program Files\Git\cmd\git.exe` (may not be on PATH in older shells). Branch `main`.
  The repo is on a NAS, so it is listed in the global `safe.directory`.
- Remote `origin` = https://github.com/carlesllavata/OpenTools (renamed from Open3DS on 2026-11-10; private
  until the user decides to publish).
  Commits use hello@carlesllavata.com on purpose. Claude's shell is non-interactive, so if Git Credential
  Manager needs to sign in again, push with `$env:GIT_TERMINAL_PROMPT='1'; $env:GCM_INTERACTIVE='always'`
  so its sign-in window can appear for the user.
