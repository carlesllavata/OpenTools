-- SPDX-License-Identifier: GPL-3.0-or-later
/*
    OpenTools - Copy / Paste Material and Mapping, shared core.

    OTL_CPM.copyFrom()                     stores the first selected object's material and
                                            its mapping modifiers (UVW Map, Unwrap UVW,
                                            UVW Xform, UVW Mapping Add / Clear / Paste)
    OTL_CPM.pasteOnto withMapping asCopy   applies them to the selected objects, one undo step:
        withMapping  the object's own mapping modifiers are removed and the stored ones are
                     added on top of its stack, in their original order, as instances
                     (tweaking one updates every object that got them)
        asCopy       the objects get one independent copy of the material ("Copy-<name>"),
                     which becomes the current material in the OpenTools material bar

    Differences from the original: no message boxes (status-bar prompts instead), the
    Instance Manager's material propagation setting is left as the user has it, and the
    command panel is not switched.
*/
global OTL_CPM_Material
global OTL_CPM_Mapping
global OTL_CPM_Source

struct OTL_CPM
(
    fn say text = displayTempPrompt ("OpenTools: " + text) 5000,

    fn plural count word = (count as string) + " " + word + (if count == 1 then "" else "s"),

    fn isMapping m =
    (
        local c = classOf m
        c == Uvwmap or c == Unwrap_UVW or c == UVW_Xform or c == MapChannelAdd or \
            c == UVW_Mapping_Clear or c == UVW_Mapping_Paste
    ),

    fn pickTargets =
    (
        for n in selection where isValidNode n and not isGroupHead n and canConvertTo n Editable_mesh collect n
    ),

    fn copyFrom =
    (
        local nodes = for n in selection where isValidNode n and not isGroupHead n collect n
        if nodes.count == 0 then
            say "select the object to copy the material and mapping from."
        else if nodes[1].material == undefined then
            say (nodes[1].name + " has no material to copy.")
        else
        (
            local n = nodes[1]
            OTL_CPM_Material = n.material
            OTL_CPM_Mapping = for m in n.modifiers where isMapping m collect m
            OTL_CPM_Source = n
            local text = "copied material \"" + OTL_CPM_Material.name + "\""
            if OTL_CPM_Mapping.count > 0 then
                text += " and " + (plural OTL_CPM_Mapping.count "mapping modifier")
            else
                text += " (no mapping modifiers)"
            say (text + " from " + n.name + ".")
        )
        ok
    ),

    fn replaceMapping n =
    (
        for i = n.modifiers.count to 1 by -1 do
            if isMapping n.modifiers[i] do deleteModifier n i
        -- OTL_CPM_Mapping runs top to bottom; adding bottom first keeps the order
        for i = OTL_CPM_Mapping.count to 1 by -1 do addModifier n OTL_CPM_Mapping[i]
    ),

    fn showInMaterialBar mat =
    (
        -- quiet no-op when the OpenTools panel or its material bar is not there
        -- getHandleByAnim gives an IntegerPtr, which prints with a trailing "P" (30043P)
        local handle = substituteString ((getHandleByAnim mat) as string) "P" ""
        try (python.Execute ("import opentools.ui.hub as h; h.show_material(" + handle + ")")) catch ()
    ),

    fn pasteOnto withMapping asCopy =
    (
        local nodes = pickTargets()
        if OTL_CPM_Material == undefined then
            say "copy a material first (Copy Material + UVW)."
        else if nodes.count == 0 then
            say "select the objects to paste onto."
        else
        (
            if OTL_CPM_Mapping == undefined do OTL_CPM_Mapping = #()
            local mat
            undo "Paste Material" on
            (
                mat = if asCopy then copy OTL_CPM_Material else OTL_CPM_Material
                if asCopy do mat.name = "Copy-" + OTL_CPM_Material.name
                for n in nodes do
                (
                    n.material = mat
                    -- the source keeps its own stack (its modifiers are the stored ones)
                    if withMapping and n != OTL_CPM_Source do replaceMapping n
                )
            )
            local text = "pasted material \"" + mat.name + "\""
            if withMapping do text += " and " + (plural OTL_CPM_Mapping.count "mapping modifier")
            say (text + " onto " + (plural nodes.count "object") + ".")
            -- the new copy is what the user wants to edit next: make it current in the bar
            if asCopy do showInMaterialBar mat
            redrawViews()
        )
        ok
    )
)
