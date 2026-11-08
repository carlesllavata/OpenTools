# Open3DS – notes for Claude

Open-source, single-install hub for 3ds Max (2025+). The user's environment: 3ds Max 2027,
Python 3.13 (bundled with Max), PySide6, Corona. The repo lives on a NAS share (`Z:` maps to
`\\192.168.2.10\...`). Talk to the user in Spanish; code, comments and docs in English.

## Layout
- `Open3DS.bundle/` – the ApplicationPlugins package users install. Version lives in
  `PackageContents.xml` (AppVersion + ComponentEntry Version) **and** `open3ds/__init__.py`; keep them equal.
  Max 2027 silently ignores a package whose RuntimeRequirements lack `SeriesMax` (we use `2099` = no cap).
- `CHANGELOG.md` – the user's version diary, **in Spanish**, newest first. After every commit ask whether to
  publish an entry or make a new version (bump both version places, tag `vX.Y.Z`, push, `gh release create`
  with that version's notes). gh lives in `%LOCALAPPDATA%\Programs\GitHubCLI\bin\gh.exe`.
- In non-interactive sessions (3dsmaxbatch, render nodes) only tools and macros load; no hub, no bridge.
- `Open3DS.bundle/Contents/python/open3ds/` – core. Modules without Qt/pymxs imports at top level
  (`registry`, `search`, `macros.macro_source`, `settings`, `runner`) must stay importable outside Max:
  the offline tests rely on it. Anything touching 3ds Max goes through `maxhost.py`.
- `Open3DS.bundle/Contents/tools/<id>/tool.json` – one folder per tool; schema in README.
- Forensic lives in `tools/scene_summary` (id kept from Scene Inspector so users' macros and toolbars keep
  working); Ignite in `tools/ignite`, built on the Object Clipboard (modes objects / materials / modifiers /
  animation). "Forensic" and "Ignite" are provisional names the user will change; the card look
  (`open3ds/ui/cards.py`) is provisional too.
- `dev/` – `install_dev.ps1` (dev shim bundle in `%APPDATA%\Autodesk\ApplicationPlugins\Open3DS-dev.bundle`
  that loads this checkout and enables the bridge), `bridge.py` (client), `run_tests.py`.

## Commands
Max's Python: `C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe` (always run with `-I`).
- Tests: `python -I dev\run_tests.py`
- Live Max: `python -I dev\bridge.py ping | reload | -c "code" | file.py` (code gets `rt`, `pymxs`, `open3ds`;
  assign `_result` to return a value). After editing core code, run `reload`; tool code reloads on every run in dev mode.
  From Windows PowerShell 5.1, `-c` mangles embedded double quotes: write anything non-trivial to a .py file
  (scratchpad) and pass the file. Avoid code that opens modal dialogs (messageBox) – it blocks the bridge
  until the user clicks.
- `3dsmaxbatch.exe` is available for headless checks.

## 3ds Max gotchas (verified in 2027)
- `with pymxs.undo(...)` silently swallows every exception raised inside it. Always use
  `open3ds.maxhost.undo(label, enabled=True)`, which closes the undo record and re-raises.
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
  item found belongs to the test (names `O3DS_t*`): the user's open scene is real work, and
  layer deletion is not undoable.
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
  declare that global *above* the block (`global O3DS_X` then `( fileIn ...; O3DS_X.f() )`):
  the block compiles before the fileIn runs, so on the first run of a session the name becomes
  an empty local ("Unknown property ... in undefined"). Live tests that already loaded the core
  hide this: remove the global first (`globalVars.remove #O3DS_X`).
- `getHandleByAnim` returns an IntegerPtr: `as string` gives "30043P". Strip the "P" before
  building Python code for `python.Execute` (a MAXScript tool selects a material in the bar with
  `python.Execute "import open3ds.ui.hub as h; h.show_material(<handle>)"`).
- Live tests of `.ms` tools: run the entry with `rt.fileIn(tool.entry_file)`, not `runner.run`;
  the runner shows a modal error dialog on failure, which hangs the bridge.
- Viewport HUDs: `registerRedrawViewsCallback` + `gw.wText` works in 2027 (and shows in
  `gw.getViewportDib`); text drawn inside a `gw.wRect` is hidden, so highlight with color.
- PySide6: `QAction` / `QActionGroup` live in QtGui, not QtWidgets. Qt never opens an empty
  QMenu, so a menu filled only in `aboutToShow` never appears: fill it once when created.
- Tool windows: subclass `open3ds.ui.toolwindow.ToolWindow` (one instance, remembered position,
  options in settings `tool_options`; a `"size"` in DEFAULTS is restored and saved by the base,
  `self.confirm(title, text)` asks Yes/Cancel) and wrap button actions with `self.guard(...)`, otherwise
  errors in Qt slots are lost. Settings of the running app: `open3ds.app.current_settings()`.
- Look: every Open3DS window gets `ui/theme.py` (`theme.apply(root)`; ToolWindow does it). Colors come
  from the 3ds Max palette (`theme.tokens()`); only the orange accent and status colors are fixed.
  No hard-coded greys or `color: gray` in tools: use `theme.dim_label()` / objectName `O3DS_Dim`.
  Buttons follow Forensic's style; the user wants Forensic's layout left as it is. Heavy geometry loops go in a MAXScript `*_core.ms` next to the tool.

## Rules
- Before adding a script the user hands over, ask where it comes from and its license. Own or permissively
  licensed code goes in with attribution; proprietary/unlicensed scripts are reimplemented clean-room from a
  description of behaviour, never from their source. Never decrypt `.mse` or bundle `.dlo/.gup`.
- No SiNi/IgNite names, icons or text.
- Git: `C:\Program Files\Git\cmd\git.exe` (may not be on PATH in older shells). Branch `main`.
  The repo is on a NAS, so it is listed in the global `safe.directory`.
- Remote `origin` = https://github.com/carlesllavata/Open3DS (private until the user decides to publish).
  Commits use hello@carlesllavata.com on purpose. Claude's shell is non-interactive, so if Git Credential
  Manager needs to sign in again, push with `$env:GIT_TERMINAL_PROMPT='1'; $env:GCM_INTERACTIVE='always'`
  so its sign-in window can appear for the user.
