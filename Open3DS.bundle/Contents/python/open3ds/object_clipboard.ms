/*
    Open3DS - Object Clipboard helpers (MIT, Open3DS contributors).

    - O3DS_PlaceTool: interactive placement of pasted objects. They follow the mouse
      (on surfaces when the cursor is over an object, else on the active grid);
      click to place, drag up/down while the button is held to scale. In stamp mode
      every click leaves an instance and a new one follows the mouse; right-click or
      Esc ends (the copy still following the mouse is removed).
    - O3DS_Clip: replace targets, material copy/paste, HUD drawing.
*/

global O3DS_Place_All = #()     -- the set of nodes following the mouse
global O3DS_Place_Roots = #()   -- its top-level nodes
global O3DS_Place_Rel = #()     -- each root's transform relative to the anchor
global O3DS_Place_Scale = 1.0
global O3DS_Place_Stamp = false
global O3DS_Place_Align = false
global O3DS_Place_Placed = 0
global O3DS_Place_Done = #()    -- every set that was placed

struct O3DS_ClipStruct
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
        O3DS_Place_All = nodes
        O3DS_Place_Roots = rootsOf nodes
        O3DS_Place_Rel = #()
        for r in O3DS_Place_Roots do append O3DS_Place_Rel (r.transform * inverse anchorTM)
    ),

    -- ---------------------------------------------------------- placement
    fn place nodes stamp:false align:false =
    (
        if nodes.count == 0 then 0 else
        (
            O3DS_Place_Scale = 1.0
            O3DS_Place_Stamp = stamp
            O3DS_Place_Align = align
            O3DS_Place_Placed = 0
            O3DS_Place_Done = #()
            prepare nodes (transMatrix (bottomCenter nodes))
            clearSelection()
            startTool O3DS_PlaceTool prompt:(if stamp then "Open3DS: click to stamp copies (drag up/down to scale) - right-click or Esc to finish" \
                                                     else "Open3DS: click to place (drag up/down to scale) - right-click or Esc to cancel")
            local placed = #()
            for s in O3DS_Place_Done do for n in s where isValidNode n do append placed n
            if placed.count > 0 then select placed else clearSelection()
            O3DS_Place_Placed
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
                    if sme.GetNumViews() == 0 do sme.CreateView "Open3DS"
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
    )
)
global O3DS_Clip = O3DS_ClipStruct()


tool O3DS_PlaceTool
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
            if not n.isHidden and findItem O3DS_Place_All n == 0 do
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
        if O3DS_Place_Align and hit != undefined then
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
        local anchor = (scaleMatrix [O3DS_Place_Scale, O3DS_Place_Scale, O3DS_Place_Scale]) * placeTM
        for i = 1 to O3DS_Place_Roots.count do
            if isValidNode O3DS_Place_Roots[i] do O3DS_Place_Roots[i].transform = O3DS_Place_Rel[i] * anchor
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
        O3DS_Place_Placed += 1
        append O3DS_Place_Done O3DS_Place_All
        if O3DS_Place_Stamp then
        (
            local nn = #()
            undo "Stamp" on (maxOps.cloneNodes O3DS_Place_All cloneType:#instance newNodes:&nn)
            O3DS_Clip.prepare nn ((scaleMatrix [O3DS_Place_Scale, O3DS_Place_Scale, O3DS_Place_Scale]) * placeTM)
            O3DS_Place_Scale = 1.0
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
            baseScale = O3DS_Place_Scale
        )
    )

    on mouseMove clickno do
    (
        if lbutton and dragging then
        (
            O3DS_Place_Scale = amax 0.01 (baseScale * (exp ((pressY - viewPoint.y) / 150.0)))
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
        if O3DS_Place_Stamp or O3DS_Place_Placed == 0 do
        (
            local loose = for n in O3DS_Place_All where isValidNode n and findItem O3DS_Place_Done O3DS_Place_All == 0 collect n
            if loose.count > 0 do undo "Stamp" on (delete loose)
        )
    )
)


-- ------------------------------------------------------------------ HUD
-- rows: #(#(title, active, #(#(filled, mb, locked) x 8)), ...) set by Python
global O3DS_ClipHUD_Rows = #()
global O3DS_ClipHUD_Mode = "objects"

fn O3DS_ClipHUD_Slot =
(
    local bits = (if keyboard.shiftPressed then 1 else 0) + (if keyboard.controlPressed then 2 else 0) + (if keyboard.altPressed then 4 else 0)
    #(1, 2, 3, 5, 4, 6, 7, 8)[bits + 1]
)

fn O3DS_ClipHUD_Draw =
(
    try
    (
        if O3DS_ClipHUD_Rows.count > 0 do
        (
            gw.setTransform (matrix3 1)
            local current = O3DS_ClipHUD_Slot()
            local cell = 62
            local rowH = 20
            local x0 = 12
            local y = gw.getWinSizeY() - 18 - rowH * O3DS_ClipHUD_Rows.count
            local width = 190 + cell * 8
            gw.wRect (box2 (x0 - 6) (y - 18) width (rowH * O3DS_ClipHUD_Rows.count + 8)) (color 30 30 30)
            gw.wText [x0, y - 4, 0] ("Open3DS clipboard: " + O3DS_ClipHUD_Mode + "   (hold Shift / Ctrl / Alt to pick the slot)") color:(color 150 150 150)
            for r in O3DS_ClipHUD_Rows do
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
