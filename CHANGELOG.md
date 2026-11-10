# Changelog

What each version of OpenTools (formerly Open3DS) adds, newest first.

## In development

### 10 November 2026

- **Open3DS is now OpenTools.** It is part of Open3D, a growing suite of open-source tools
  for 3D work. Everything that showed "Open3DS" now says "OpenTools": the panel, the menu in
  the menu bar, the messages and the install folder. What you need to redo once:
  - **Reinstall:** delete `Open3DS.bundle` from `%APPDATA%\Autodesk\ApplicationPlugins\` and copy
    `OpenTools.bundle` there instead.
  - **Shortcuts and toolbar buttons:** the actions are now in the **OpenTools** category
    (Customize > Hotkey Editor / Customize User Interface). Bind them again; the old Open3DS
    ones stop working.
  - **Your settings and clipboard slots** now live in `%APPDATA%\OpenTools` and
    `%LOCALAPPDATA%\OpenTools`. Move the contents of the old `Open3DS` folders there if you
    want to keep them; otherwise OpenTools starts with its defaults.

### 9 November 2026

- **Ignite is gone; its parts move elsewhere.** It repeated what the Object Clipboard already
  does (same slots, same copy and paste), so only the two things of its own stay:
  - **Paste options in the Object Clipboard.** Below the target, the options of the chosen
    mode appear: in **Modifiers**, paste as instances; in **Keys**, keep each object's
    position at a frame and offset the keys in time.
  - **New tool: Random Replace** (Modeling category). Replaces the selected objects (boxes,
    markers…) with several sources picked at random by weight, keeping position, rotation,
    scale and layer. One Ctrl+Z undoes it. If you had Ignite on a toolbar or a shortcut, it
    now opens Random Replace.
- **Open3DS menu in the 3ds Max menu bar.** Shows or hides the panel (if you close it with
  the X, this brings it back), opens the command palette and lists every tool by category.
- **The material bar tells you which material your selection has.** A thin line above the
  bar, **Selected:**, shows the selected object's material (a dash if there are several). It
  is only informative: the material you work with, the one below, does not change until you
  pick it, so the eyedropper works as always. The **↓** arrow makes it the working material
  without using the eyedropper, and a double click selects every object that uses it. It
  costs next to nothing: it only looks at the selection, never walks the scene. It can be
  hidden from the right-click menu.

## 0.4.0 — 8 November 2026

Eight new tools for everyday work, a panel you can arrange your way and two 3ds Max crashes
fixed.

- **Filter by several categories.** The category buttons under the search box now toggle on
  and off one by one, and the panel shows only the chosen categories (for example,
  Materials and Scene at once). **All** shows everything again. The filter is remembered
  between sessions.
- **Materials is a category like the others**, with its own button.
- The category color dots also show on the active button.
- **Arrange the categories your way.** Drag a category button onto another to change the
  order of the buttons and the sections, or use the right-click menu (move to the start,
  left, right, to the end). By default they are in alphabetical order, and "Default order"
  goes back to it.
- Section headers show the name as it is (in bold, no longer in capitals), like the buttons
  above.
- **Flicker fixed.** Showing or hiding categories no longer flashes an empty window for an
  instant.
- **New tool: Random Select** (Selection category). Choose a percentage and it keeps that
  share of the current selection selected, at random: 10 objects at 30 % leaves 3. Press it
  again and it draws again from the original 10, without having to select them again. Closed
  groups count as one object (they go in or out whole), at least one always stays, and one
  Ctrl+Z undoes it. The percentage is remembered between sessions.
- **New tool: Random Wire Color** (Scene category). With one click, each selected object gets
  a different object color (the color shown at the top right of the Modify panel), ideal for
  separating objects with color masks such as Mask ID. The colors are spread so that two are
  never nearly the same, and none come out grey, black or white; every click gives a new
  combination. One Ctrl+Z undoes it.
- **New tool: Turn to Instance** (Modeling category), based on Miled Rizk's script and
  included with their permission. Select the objects, launch it and click the source object:
  each one becomes a full instance of the source (geometry, modifiers, material and numbered
  name) without moving, and keeps its hierarchy and its layer. Works with geometry, splines,
  cameras and lights (objects of a different type are skipped), without breaking the FOV of
  target cameras. One Ctrl+Z undoes it.
- **New buttons: Copy / Paste Material + UVW** (Materials category), based on Aleksey
  Sheremetov's CPM Lite and included with their permission. **Copy Material + UVW** stores an
  object's material and its mapping modifiers (UVW Map, Unwrap UVW, UVW Xform…); **Paste
  Material** assigns it to the selection; **Paste Material + UVW** also replaces the objects'
  mapping with the copied one, without touching the rest of their stack. The **Copy**
  versions paste an independent copy of the material ("Copy-…") and leave it picked in the
  material bar, ready to edit. One Ctrl+Z undoes all of it.
- **Materials section tidied up.** The Materials buttons sit below the material bar, in a
  single section that folds as a whole.
- **New tool: Clean DWG** (Scene category), based on Juan Camilo Alcaraz's (Alzarac) script
  and included with their permission. For drawings imported from AutoCAD: type a name and press
  Start. It opens the groups, flattens every line to Z = 0 and deletes whatever is not a
  line; moves everything to a new layer with that name, keeping the colors; groups it; and
  deletes the DWG layers left empty. Each step can be turned off. Your empty template layers
  are left alone, and one Ctrl+Z undoes all of it, layers included.
- **New tools: 3-Point Rotate and 3-Point Scale** (Modeling category), based on Sergo
  Pogosyan's scripts and included with their permission. Like AutoCAD's rotate and scale by
  reference: three clicks with snaps (base point, a point on the object and where it should
  end up) and done. The rotation always goes the right way, with no "Flip" checkbox, and
  works in plan and in elevation. One Ctrl+Z undoes them.
- **Fixed: Turn to Instance** failed the first time it was used in a 3ds Max session
  ("Unknown property … in undefined").
- **Fixed: 3ds Max crash on undo** after Forensic had deleted empty layers. That deletion
  can now be undone too.

## 0.3.0 — 8 November 2026

One look for the whole app, following the 3ds Max colors.

- **Shared theme.** The panel and every window (Forensic, Ignite, Object Clipboard, the
  asset, proxy and XRef managers, Attach / Detach and the command palette) share the same
  look. Backgrounds, text and borders come from the 3ds Max palette: if you change the Max
  theme, Open3DS changes with it. Only the orange accent and the status colors are fixed.
- **Redesigned panel.** Search box with reload and options buttons; category filters as
  buttons with their color dot; foldable sections with a color bar, name in capitals and
  tool count; and tools as horizontal buttons with a small icon and name, laid out in
  columns that adapt to the panel width.
- **Materials section.** The material bar is no longer at the very top and becomes a
  section of its own below Clipboard (drop-down, eyedropper, apply and select). It can be
  hidden from the `⋯` menu.
- **Forensic-style buttons** everywhere, and checkboxes, drop-downs, spinners and tabs in
  the same style.
- **Internal cleanup.** Repeated and unused code removed; tool windows remember their size
  and ask for confirmation in one shared way.

## 0.2.0 — 7 November 2026

The tool collection takes shape.

- **Forensic**: the whole scene in cards (render, object states, geometry, cleanup,
  animation, materials and modifiers, references, scene health) with buttons to select and
  fix in one click, plus the modifier list and the file data.
- **Ignite**: copy and paste objects, modifier stacks, materials and animation keys between
  scenes, and replace objects with several sources at random by weight.
- **Object Clipboard**: 8 slots with thumbnails, local or in shared network folders; paste
  in place, at the cursor or as a stamp; slot locking and a viewport HUD.
- **Asset Manager**: every external file in the scene, with relinking of missing ones, path
  cleanup and collecting into a folder.
- **Proxy Display Manager** and **XRef Display Manager**.
- **Attach Objects**, **Detach Elements** and **Reset XForm + Collapse**.
- **Material bar** in the panel, in the style of AutoCAD's layer list.

## 0.1.0 — 6 November 2026

First version: the base of the hub.

- A single package to install in 3ds Max 2025 or later.
- Dockable panel with the tools by category, search and favorites.
- Command palette and macros to assign keyboard shortcuts to each tool.
- Each tool is a folder with its `tool.json`; if one fails, the others keep working.
