"""Scene material bar: a layer-like list of the scene's materials.

Works like the layer drop-down of AutoCAD, but for materials: choose a "current"
material from the list (or pick it from an object with the eyedropper), apply it to
the selection, or select every object that uses it. Only top-level materials are
listed (what an object has in its material slot), never their maps or sub-materials.

Materials are identified by their 3ds Max animatable handle, which is unique and
stable for the whole session; NONE stands for "no material".

The helpers at the top are pure Python (tested offline); everything that talks to
3ds Max is at the bottom and runs through one MAXScript struct.
"""

import re
from dataclasses import dataclass, field

NONE = 0  # "no material" (objects with an empty material slot)
NONE_LABEL = "(no material)"


@dataclass
class MaterialEntry:
    handle: int
    name: str
    kind: str = ""  # MAXScript class name, e.g. "CoronaPhysicalMtl"
    count: int = 0  # objects that use it
    colors: list = field(default_factory=list)  # up to 4 (r, g, b) swatch colors
    has_map: bool = False  # the main color slot holds a texture map
    in_scene: bool = True

    @property
    def is_none(self):
        return self.handle == NONE


def none_entry(count=0):
    return MaterialEntry(handle=NONE, name=NONE_LABEL, count=count)


def plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def natural_key(name):
    """Sort key so that "Wood 2" comes before "Wood 10" (case-insensitive)."""
    parts = re.split(r"(\d+)", name.casefold())
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in parts if p != ""]


def sort_entries(entries):
    return sorted(entries, key=lambda e: (natural_key(e.name), e.handle))


def tooltip(entry):
    if entry.is_none:
        if entry.count < 0:
            return "Objects without a material"
        return "Objects without a material · %s" % plural(entry.count, "object")
    lines = [entry.name, entry.kind or "Material"]
    if not entry.in_scene:
        lines.append("Not used in the scene")
    elif entry.count >= 0:  # -1: not counted (read for the selection only)
        lines.append(plural(entry.count, "object"))
    if entry.has_map:
        lines.append("Color from a texture map")
    return "\n".join(lines)


def _color(value):
    """(r, g, b) clamped to 0..255 from a MAXScript array, or None."""
    try:
        r, g, b = (max(0, min(255, int(round(float(v))))) for v in list(value)[:3])
    except (TypeError, ValueError):
        return None
    return (r, g, b)


def entry_from_row(row, in_scene=True):
    """MaterialEntry from one row of O3DS_Materials.describe: #(handle, name, class,
    count, #(colors), hasMap)."""
    handle, name, kind, count, colors, has_map = list(row)[:6]
    swatches = [c for c in (_color(v) for v in list(colors or [])) if c is not None]
    return MaterialEntry(
        handle=int(handle),
        name=str(name),
        kind=str(kind).lstrip("_"),  # Corona reports "_CoronaPhysicalMtl"
        count=int(count),
        colors=swatches[:4],
        has_map=bool(has_map),
        in_scene=in_scene,
    )


# --------------------------------------------------------------------- 3ds Max
_STRUCT_MS = r"""
struct O3DS_MaterialsStruct
(
    -- (color property, map property, map-enabled property) of common materials:
    -- Corona Physical, Physical, Corona Legacy, Standard, V-Ray, Corona Light.
    slots = #(
        #(#baseColor, #baseTexmap, #baseTexmapOn),
        #(#base_color, #base_color_map, #base_color_map_on),
        #(#colorDiffuse, #texmapDiffuse, #texmapOnDiffuse),
        #(#diffuse, #diffuseMap, #diffuseMapEnable),
        #(#diffuse, #texmap_diffuse, #texmap_diffuse_on),
        #(#color, #texmap, #texmapOn),
        #(#color, undefined, undefined)
    ),

    fn canTake n =
    (
        isValidNode n and classOf n != TargetObject and \
        (superClassOf n == GeometryClass or superClassOf n == Shape)
    ),

    fn byHandle h =
    (
        if h == 0 then undefined else
        (
            local m = getAnimByHandle h
            if m != undefined and superClassOf m == material then m else undefined
        )
    ),

    fn propOf m p = (if p != undefined and isProperty m p then (try (getProperty m p) catch undefined) else undefined),

    -- #(#(r,g,b) color, hasMap) of a material's main color, or undefined
    fn mainColor m depth:0 =
    (
        local result = undefined
        for s in slots while result == undefined do
        (
            -- the color and its map must both exist: some materials expose aliases
            -- (e.g. Physical answers to #baseColor) that would pair with the wrong map
            local c = propOf m s[1]
            if classOf c == Color and (s[2] == undefined or isProperty m s[2]) do
            (
                local tex = propOf m s[2]
                local enabled = propOf m s[3]
                local hasMap = tex != undefined and enabled != false
                result = #(#(c.r, c.g, c.b), hasMap)
            )
        )
        -- Blend, Shell, layered... use their first sub-material
        if result == undefined and depth < 3 do
        (
            local n = try (getNumSubMtls m) catch 0
            for i = 1 to n while result == undefined do
            (
                local sub = try (getSubMtl m i) catch undefined
                if sub != undefined do result = mainColor sub depth:(depth + 1)
            )
        )
        result
    ),

    fn describe m count =
    (
        local colors = #()
        local hasMap = false
        if classOf m == Multimaterial then
        (
            for sub in m.materialList where sub != undefined while colors.count < 4 do
            (
                local c = mainColor sub
                if c != undefined do append colors c[1]
            )
        )
        else
        (
            local c = mainColor m
            if c != undefined do (append colors c[1] ; hasMap = c[2])
        )
        #((getHandleByAnim m) as integer, m.name, (classOf m) as string, count, colors, hasMap)
    ),

    -- #(rows, objects without material)
    fn listAll =
    (
        local counts = Dictionary #integer
        local mats = #()
        local none = 0
        for n in objects where canTake n do
        (
            local m = n.material
            if m == undefined then none += 1 else
            (
                local h = (getHandleByAnim m) as integer
                if hasDictValue counts h then counts[h] = counts[h] + 1 else (counts[h] = 1 ; append mats m)
            )
        )
        #(for m in mats collect describe m counts[(getHandleByAnim m) as integer], none)
    ),

    fn usersOf m =
    (
        local users = #()
        for n in objects do if canTake n and n.material == m do append users n
        users
    ),

    -- withCount:false skips counting the users (a walk over the whole scene)
    fn infoOf h withCount:true =
    (
        local m = byHandle h
        if m == undefined then undefined else describe m (if withCount then (usersOf m).count else -1)
    ),

    fn nameOf h = (local m = byHandle h ; if m == undefined then undefined else m.name),

    -- What the bar shows for the selection, without walking the scene: the handle of
    -- the material of the only geometry or shape selected (0 = it has none), -1 when
    -- several (or none of them) are selected, -2 when nothing is selected.
    fn selectedHandle =
    (
        local count = selection.count
        local found = undefined
        local many = false
        if count == 1 then (if canTake selection[1] do found = selection[1])
        else if count > 1 do
        (
            -- stops at the second one: a closed group of one object still counts as one.
            -- Indexed: "for n in selection" copies the whole selection first.
            for i = 1 to count while not many do
            (
                local n = selection[i]
                if canTake n do (if found == undefined then found = n else many = true)
            )
        )
        case of
        (
            (count == 0): -2
            (many or found == undefined): -1
            (found.material == undefined): 0
            default: (getHandleByAnim found.material) as integer
        )
    ),

    -- #(applied, skipped); h == 0 clears the material
    fn applyTo h =
    (
        local m = byHandle h
        if h != 0 and m == undefined then #(-1, 0) else
        (
            local nodes = for n in selection where canTake n collect n
            if nodes.count > 0 do undo "Apply Material" on (for n in nodes do n.material = m)
            #(nodes.count, selection.count - nodes.count)
        )
    ),

    -- #(selected, skipped hidden or frozen)
    fn selectBy h add:false =
    (
        local m = byHandle h
        if h != 0 and m == undefined then #(-1, 0) else
        (
            local users = usersOf m
            local nodes = #()
            for n in users do if not n.isHiddenInVpt and not n.isFrozen do append nodes n
            if nodes.count > 0 do undo "Select by Material" on
            (
                if add then selectMore nodes else select nodes
            )
            #(nodes.count, users.count - nodes.count)
        )
    ),

    -- #(true, handle) after a pick (0 = the object has no material), #(false) if cancelled
    fn pickMtl =
    (
        local n = pickObject message:"Open3DS: pick an object to take its material (right-click to cancel)"
        if isValidNode n then #(true, (if n.material == undefined then 0 else (getHandleByAnim n.material) as integer))
        else #(false)
    ),

    -- handle of the material in the Material Editor (Slate: the one in the parameter
    -- editor; Compact: the active slot), or 0
    fn fromEditor =
    (
        local m = if MatEditor.mode == #advanced then sme.GetMtlInParamEditor() else meditMaterials[activeMeditSlot]
        if m != undefined and superClassOf m == material then (getHandleByAnim m) as integer else 0
    ),

    fn editMtl h =
    (
        local m = byHandle h
        if m == undefined then false else
        (
            if MatEditor.mode == #advanced then
            (
                sme.Open()
                if sme.GetNumViews() == 0 do sme.CreateView "Open3DS"
                local view = sme.GetView sme.activeView
                if view != undefined and (view.GetNodeByRef m) == undefined do view.CreateNode m [0, 0]
                sme.SetMtlInParamEditor m
            )
            else
            (
                meditMaterials[activeMeditSlot] = m
                MatEditor.Open()
            )
            true
        )
    ),

    fn showPrompt text = (displayTempPrompt ("Open3DS: " + text) 4000)
)
"""

_defined = False


def _api():
    """The MAXScript struct, defined on first use (and again after an Open3DS reload)."""
    global _defined
    from pymxs import runtime as rt

    if not _defined or rt.O3DS_Materials is None:
        rt.execute(_STRUCT_MS + "\nglobal O3DS_Materials = O3DS_MaterialsStruct()")
        _defined = True
    return rt.O3DS_Materials


def scene_entries():
    """(materials used in the scene, sorted naturally; objects without a material)."""
    rows, none_count = _api().listAll()
    return sort_entries(entry_from_row(r) for r in rows), int(none_count)


def entry(handle, count=True):
    """Fresh MaterialEntry for a handle, or None if that material is gone.
    count=False is cheap (no walk over the scene): the entry's count is then -1."""
    if handle == NONE:
        return none_entry(-1 if not count else 0)
    row = _api().infoOf(handle, withCount=count)
    if row is None:
        return None
    result = entry_from_row(row)
    result.in_scene = result.count != 0
    return result


def name_of(handle):
    """Current name of a material, or None if it is gone. Cheap."""
    name = _api().nameOf(handle)
    return None if name is None else str(name)


SELECTION_EMPTY = -2
SELECTION_OTHER = -1  # several objects, or none that can take a material


def selected_handle():
    """Material handle of the only selected geometry/shape (NONE if it has none),
    SELECTION_OTHER or SELECTION_EMPTY. One cheap call: the scene is not walked."""
    return int(_api().selectedHandle())


def apply(handle):
    """Assign the material to the selected geometry and shapes: (applied, skipped)."""
    applied, skipped = (int(v) for v in _api().applyTo(handle))
    return applied, skipped


def select(handle, add=False):
    """Select the visible, unfrozen objects that use the material: (selected, skipped)."""
    selected, skipped = (int(v) for v in _api().selectBy(handle, add=add))
    return selected, skipped


def pick():
    """Interactive eyedropper: handle of the picked object's material (NONE if it has
    none), or None if the user cancelled."""
    result = list(_api().pickMtl())
    if not result or not result[0]:
        return None
    return int(result[1])


def from_editor():
    """Handle of the material shown in the Material Editor, or None."""
    handle = int(_api().fromEditor())
    return handle or None


def edit(handle):
    """Show the material in the Material Editor (Slate or Compact)."""
    return bool(_api().editMtl(handle))


def prompt(text):
    _api().showPrompt(text)
