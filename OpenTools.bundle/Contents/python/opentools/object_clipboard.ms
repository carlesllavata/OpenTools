-- SPDX-License-Identifier: GPL-3.0-or-later
/*
    OpenTools - Object Clipboard helpers.

    - OTL_PlaceTool: interactive placement of pasted objects. They follow the mouse
      (on surfaces when the cursor is over an object, else on the active grid);
      click to place, drag up/down while the button is held to scale. In stamp mode
      every click leaves an instance and a new one follows the mouse; right-click or
      Esc ends (the copy still following the mouse is removed).
    - OTL_Clip: replace targets, material copy/paste, HUD drawing.
*/

global OTL_Place_All = #()     -- the set of nodes following the mouse
global OTL_Place_Roots = #()   -- its top-level nodes
global OTL_Place_Rel = #()     -- each root's transform relative to the anchor
global OTL_Place_Scale = 1.0
global OTL_Place_Stamp = false
global OTL_Place_Align = false
global OTL_Place_Placed = 0
global OTL_Place_Done = #()    -- every set that was placed

struct OTL_ClipStruct
(
    fn rootsOf nodes =
    (
        local roots = #()
        for n in nodes do if isValidNode n and (n.parent == undefined or findItem nodes n.parent == 0) do append roots n
        roots
    ),

    fn bottomCenter nodes =
    (
        local mn = copy nodes[1].min
        local mx = copy nodes[1].max
        for n in nodes do
        (
            mn.x = amin mn.x n.min.x ; mn.y = amin mn.y n.min.y ; mn.z = amin mn.z n.min.z
            mx.x = amax mx.x n.max.x ; mx.y = amax mx.y n.max.y ; mx.z = amax mx.z n.max.z
        )
        [(mn.x + mx.x) / 2.0, (mn.y + mx.y) / 2.0, mn.z]
    ),

    fn prepare nodes anchorTM =
    (
        OTL_Place_All = nodes
        OTL_Place_Roots = rootsOf nodes
        OTL_Place_Rel = #()
        for r in OTL_Place_Roots do append OTL_Place_Rel (r.transform * inverse anchorTM)
    ),

    -- ---------------------------------------------------------- placement
    fn place nodes stamp:false align:false =
    (
        if nodes.count == 0 then 0 else
        (
            OTL_Place_Scale = 1.0
            OTL_Place_Stamp = stamp
            OTL_Place_Align = align
            OTL_Place_Placed = 0
            OTL_Place_Done = #()
            prepare nodes (transMatrix (bottomCenter nodes))
            clearSelection()
            startTool OTL_PlaceTool prompt:(if stamp then "OpenTools: click to stamp copies (drag up/down to scale) - right-click or Esc to finish" \
                                                     else "OpenTools: click to place (drag up/down to scale) - right-click or Esc to cancel")
            local placed = #()
            for s in OTL_Place_Done do for n in s where isValidNode n do append placed n
            if placed.count > 0 then select placed else clearSelection()
            OTL_Place_Placed
        )
    ),

    -- ---------------------------------------------------- replace targets
    fn replaceTargets src targets =
    (
        local roots = rootsOf src
        local anchor = transMatrix (bottomCenter src)
        local rels = for r in roots collect (r.transform * inverse anchor)
        local result = #()
        undo "Replace Targets" on
        (
            for t in targets where isValidNode t do
            (
                local nn = #()
                maxOps.cloneNodes src cloneType:#instance newNodes:&nn
                local newRoots = rootsOf nn
                for i = 1 to (amin newRoots.count rels.count) do newRoots[i].transform = rels[i] * t.transform
                join result nn
            )
            delete (for t in targets where isValidNode t collect t)
            delete src
        )
        select result
        result
    ),

    -- ---------------------------------------------------------- materials
    fn editorMaterials =
    (
        local mats = #()
        if MatEditor.isOpen() do
        (
            if MatEditor.mode == #advanced then
            (
                local view = if sme.activeView > 0 then sme.GetView sme.activeView else undefined
                if view != undefined do
                    for n in (view.GetSelectedNodes()) do
                    (
                        local r = n.reference
                        if r != undefined and superClassOf r == material do appendIfUnique mats r
                    )
                if mats.count == 0 do
                (
                    local m = sme.GetMtlInParamEditor()
                    if m != undefined and superClassOf m == material do append mats m
                )
            )
            else
            (
                local m = meditMaterials[activeMeditSlot]
                if m != undefined do append mats m
            )
        )
        mats
    ),

    fn selectionMaterials =
    (
        local mats = #()
        for n in selection do if n.material != undefined do appendIfUnique mats n.material
        mats
    ),

    -- #(materials, #editor | #selection)
    fn materialsToCopy =
    (
        local fromEditor = editorMaterials()
        if fromEditor.count > 0 then #(fromEditor, #editor) else #(selectionMaterials(), #selection)
    ),

    fn saveMaterials mats path =
    (
        local lib = materialLibrary()
        for m in mats do append lib m
        saveTempMaterialLibrary lib path
    ),

    fn canTake n = (isValidNode n and classOf n != TargetObject and (superClassOf n == GeometryClass or superClassOf n == Shape)),

    -- #(where: #editor | #selection | #none, count)
    fn pasteMaterials path =
    (
        local lib = loadTempMaterialLibrary path
        if lib == undefined or lib.count == 0 then #(#none, 0) else
        (
            local mats = for i = 1 to lib.count collect lib[i]
            if MatEditor.isOpen() then
            (
                if MatEditor.mode == #advanced then
                (
                    if sme.GetNumViews() == 0 do sme.CreateView "OpenTools"
                    if sme.activeView == 0 do sme.activeView = 1
                    local view = sme.GetView sme.activeView
                    for i = 1 to mats.count do
                        if view.GetNodeByRef mats[i] == undefined do view.CreateNode mats[i] [(i - 1) * 260, 0]
                    sme.SetMtlInParamEditor mats[1]
                )
                else
                    for i = 1 to (amin mats.count 24) do meditMaterials[1 + mod (activeMeditSlot - 1 + i - 1) 24] = mats[i]
                #(#editor, mats.count)
            )
            else
            (
                local nodes = for n in selection where canTake n collect n
                if nodes.count == 0 then #(#none, mats.count) else
                (
                    undo "Paste Material" on (for n in nodes do n.material = mats[1])
                    #(#selection, nodes.count)
                )
            )
        )
    ),

    -- -------------------------------------------- carriers (modifiers, keys)
    -- Modifiers and keys travel on a temporary carrier node saved to the slot's .max;
    -- paste merges it, takes what it carries and deletes it. Neither the carrier nor
    -- the merge end up in the undo history: only the change to the targets does.
    fn saveNodesTo nodes path saveAs =
    (
        if saveAs > 0 then saveNodes nodes path quiet:true saveAsVersion:saveAs
        else saveNodes nodes path quiet:true
    ),

    -- merge a carrier file and give the selection back; returns the merged nodes
    fn mergeCarrier path =
    (
        local keep = selection as array
        mergeMAXFile path #select #autoRenameDups #neverReparent #useSceneMtlDups quiet:true
        local merged = selection as array
        if keep.count > 0 then select keep else clearSelection()
        merged
    ),

    fn dropCarrier merged = (with undo off (delete (for n in merged where isValidNode n collect n))),

    -- #(source name, #(modifier names, top first)) or undefined
    fn saveModifiers path saveAs =
    (
        local src = undefined
        for n in selection do if src == undefined and n.modifiers.count > 0 do src = n
        if src == undefined then undefined else
        (
            local names = for m in src.modifiers collect m.name
            with undo off
            (
                local carrier = copy src
                carrier.name = "OTL_ModifierCarrier"
                carrier.parent = undefined
                carrier.material = undefined
                saveNodesTo #(carrier) path saveAs
                delete carrier
            )
            #(src.name, names)
        )
    ),

    -- adds the carried stack on top of each target's stack, in the same order
    -- #(targets, modifiers carried, placements that did not fit)
    fn pasteModifiers path instance =
    (
        local targets = for n in selection where canTake n collect n
        local carried = 0, skipped = 0
        if targets.count > 0 do
        (
            local merged = #()
            with undo off (merged = mergeCarrier path)
            local carrier = undefined
            for n in merged do if carrier == undefined and n.modifiers.count > 0 do carrier = n
            if carrier != undefined do
            (
                carried = carrier.modifiers.count
                undo "Paste Modifiers" on
                    for i = carried to 1 by -1 do
                    (
                        local m = carrier.modifiers[i]
                        local shared = copy m
                        for t in targets do
                            if validModifier t m then addModifier t (if instance then shared else copy m)
                            else skipped += 1
                    )
            )
            dropCarrier merged
        )
        #(targets.count, carried, skipped)
    ),

    -- every key time below a controller
    fn keyTimes ctrl acc depth:0 =
    (
        if ctrl != undefined and depth < 8 do
        (
            local ks = try (ctrl.keys) catch undefined
            if ks != undefined do for k in ks do appendIfUnique acc k.time
            for i = 1 to (try (ctrl.numSubs) catch 0) do
            (
                local s = try (ctrl[i]) catch undefined
                if s != undefined do keyTimes s.controller acc depth:(depth + 1)
            )
        )
        acc
    ),

    -- #(source name, keyframes, first frame, last frame) or undefined
    fn saveKeys path saveAs =
    (
        local src = undefined
        local times = #()
        for n in selection do
            if src == undefined do
            (
                times = keyTimes n.controller #()
                if times.count > 0 do src = n
            )
        if src == undefined then undefined else
        (
            sort times
            with undo off
            (
                local carrier = Point name:"OTL_KeyCarrier"
                carrier.controller = copy src.controller
                saveNodesTo #(carrier) path saveAs
                delete carrier
            )
            #(src.name, times.count, (times[1].frame as integer), (times[times.count].frame as integer))
        )
    ),

    -- add d to a controller's keys (or to its value when it has none)
    fn shiftValue ctrl d =
    (
        local ks = try (ctrl.keys) catch undefined
        if ks == undefined then false
        else if ks.count == 0 then (ctrl.value += d ; true)
        else (for k in ks do k.value += d ; true)
    ),

    fn offsetPosition t d =
    (
        local c = try (t.position.controller) catch undefined
        if c == undefined then false
        else if classOf c == Position_XYZ then
        (
            local done = true
            for i = 1 to 3 do if not (shiftValue c[i].controller d[i]) do done = false
            done
        )
        else shiftValue c d
    ),

    -- gives every selected object the carried transform animation, shifted by `offset`
    -- frames; relative: each object stays where it is now at frame refFrame (+ offset)
    -- #(targets, targets whose position could not be offset)
    fn pasteKeys path relative refFrame offset =
    (
        local targets = for n in selection where isValidNode n collect n
        local notMoved = 0
        if targets.count > 0 do
        (
            local merged = #()
            with undo off (merged = mergeCarrier path)
            local carrier = undefined
            for n in merged do if carrier == undefined and matchPattern n.name pattern:"OTL_KeyCarrier*" do carrier = n
            if carrier != undefined do
                undo "Paste Keys" on
                    for t in targets do
                    (
                        local before = try (t.position.controller.value) catch undefined
                        t.controller = copy carrier.controller
                        if offset != 0 do moveKeys t.controller offset
                        if relative do
                        (
                            local after = try (at time (refFrame + offset) t.position.controller.value) catch undefined
                            if before == undefined or after == undefined or not (offsetPosition t (before - after)) do
                                notMoved += 1
                        )
                    )
            dropCarrier merged
        )
        #(targets.count, notMoved)
    )
)
global OTL_Clip = OTL_ClipStruct()


tool OTL_PlaceTool
(
    local dragging = false
    local pressY = 0
    local baseScale = 1.0
    local placeTM = matrix3 1

    fn surfaceHit =
    (
        local r = mapScreenToWorldRay viewPoint
        local best = undefined
        local bestD = 1e30
        for h in (intersectRayScene r) do
        (
            local n = h[1]
            if not n.isHidden and findItem OTL_Place_All n == 0 do
            (
                local d = distance r.pos h[2].pos
                if d < bestD do (bestD = d ; best = h[2])
            )
        )
        best
    )

    fn targetTM =
    (
        local hit = surfaceHit()
        local pos = if hit != undefined then hit.pos else worldPoint
        local tm = matrix3 1
        if OTL_Place_Align and hit != undefined then
        (
            local z = normalize hit.dir
            local x = if abs (dot z [0, 0, 1]) > 0.99 then normalize (cross [0, 1, 0] z) else normalize (cross [0, 0, 1] z)
            local y = normalize (cross z x)
            tm = matrix3 x y z pos
        )
        else tm.row4 = pos
        tm
    )

    fn applyTM =
    (
        local anchor = (scaleMatrix [OTL_Place_Scale, OTL_Place_Scale, OTL_Place_Scale]) * placeTM
        for i = 1 to OTL_Place_Roots.count do
            if isValidNode OTL_Place_Roots[i] do OTL_Place_Roots[i].transform = OTL_Place_Rel[i] * anchor
    )

    fn follow =
    (
        placeTM = targetTM()
        applyTM()
    )

    -- the set under the mouse is placed: keep it, and in stamp mode start a new one
    fn finishOne =
    (
        dragging = false
        OTL_Place_Placed += 1
        append OTL_Place_Done OTL_Place_All
        if OTL_Place_Stamp then
        (
            local nn = #()
            undo "Stamp" on (maxOps.cloneNodes OTL_Place_All cloneType:#instance newNodes:&nn)
            OTL_Clip.prepare nn ((scaleMatrix [OTL_Place_Scale, OTL_Place_Scale, OTL_Place_Scale]) * placeTM)
            OTL_Place_Scale = 1.0
            placeTM = matrix3 1
            follow()
            #continue
        )
        else #stop
    )

    on start do (dragging = false)

    on freeMove do (if not dragging do follow())

    on mousePoint clickno do
    (
        if dragging and finishOne() == #stop then #stop else
        (
            follow()
            dragging = true
            pressY = viewPoint.y
            baseScale = OTL_Place_Scale
        )
    )

    on mouseMove clickno do
    (
        if lbutton and dragging then
        (
            OTL_Place_Scale = amax 0.01 (baseScale * (exp ((pressY - viewPoint.y) / 150.0)))
            applyTM()
        )
        else if dragging then
        (
            if finishOne() == #stop then #stop
        )
        else follow()
    )

    on mouseAbort clickno do
    (
        -- right-click / Esc: drop the copy still following the mouse
        if dragging then finishOne()
        if OTL_Place_Stamp or OTL_Place_Placed == 0 do
        (
            local loose = for n in OTL_Place_All where isValidNode n and findItem OTL_Place_Done OTL_Place_All == 0 collect n
            if loose.count > 0 do undo "Stamp" on (delete loose)
        )
    )
)


-- ------------------------------------------------------------------ HUD
-- rows: #(#(title, active, #(#(filled, mb, locked) x 8)), ...) set by Python
global OTL_ClipHUD_Rows = #()
global OTL_ClipHUD_Mode = "objects"

fn OTL_ClipHUD_Slot =
(
    local bits = (if keyboard.shiftPressed then 1 else 0) + (if keyboard.controlPressed then 2 else 0) + (if keyboard.altPressed then 4 else 0)
    #(1, 2, 3, 5, 4, 6, 7, 8)[bits + 1]
)

fn OTL_ClipHUD_Draw =
(
    try
    (
        if OTL_ClipHUD_Rows.count > 0 do
        (
            gw.setTransform (matrix3 1)
            local current = OTL_ClipHUD_Slot()
            local cell = 62
            local rowH = 20
            local x0 = 12
            local y = gw.getWinSizeY() - 18 - rowH * OTL_ClipHUD_Rows.count
            local width = 190 + cell * 8
            gw.wRect (box2 (x0 - 6) (y - 18) width (rowH * OTL_ClipHUD_Rows.count + 8)) (color 30 30 30)
            gw.wText [x0, y - 4, 0] ("OpenTools clipboard: " + OTL_ClipHUD_Mode + "   (hold Shift / Ctrl / Alt to pick the slot)") color:(color 150 150 150)
            for r in OTL_ClipHUD_Rows do
            (
                y += rowH
                local title = r[1]
                gw.wText [x0, y, 0] ((if r[2] then "> " else "   ") + title) color:(if r[2] then (color 255 255 255) else (color 150 150 150))
                for i = 1 to 8 do
                (
                    local s = r[3][i]
                    local x = x0 + 180 + (i - 1) * cell
                    local col = if s[3] then (color 230 80 70) else if s[1] then (color 110 200 120) else (color 110 110 110)
                    local text = (i as string) + (if s[1] then " " + (formattedPrint s[2] format:".1f") + "M" else " -")
                    if r[2] and i == current do
                    (
                        -- the slot the held keys pick: bright and bracketed
                        text = "[" + text + "]"
                        col = color 255 200 40
                    )
                    gw.wText [x, y, 0] text color:col
                )
            )
            gw.enlargeUpdateRect #whole
            gw.updateScreen()
        )
    )
    catch ()
)
