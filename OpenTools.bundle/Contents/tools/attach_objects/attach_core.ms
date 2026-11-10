-- SPDX-License-Identifier: GPL-3.0-or-later
/*
    OpenTools - Attach Objects core.
    Attaches many objects into one Editable Poly / Editable Mesh / Spline (or one per
    material) quickly, by attaching in batches and then attaching the batches, instead
    of growing a single object one piece at a time. Independent implementation; the UI
    lives in attach_objects.py.
*/
struct OTL_AttachTool
(
    fn isRenderableShape n = superClassOf n == Shape and (try (n.render_renderable) catch (false)),

    fn isUsable n kind includeShapes =
    (
        if not isValidNode n then false
        else if kind == #spline then superClassOf n == Shape and canConvertTo n SplineShape
        else if superClassOf n == GeometryClass then classOf n != TargetObject and canConvertTo n Editable_Mesh
        else includeShapes and isRenderableShape n
    ),

    fn toKind n kind =
    (
        if superClassOf n == Shape and kind != #spline do n.render_displayRenderMesh = true
        case kind of
        (
            #poly: if not (classOf n.baseObject == Editable_Poly and n.modifiers.count == 0) do convertToPoly n
            #mesh: if not (classOf n.baseObject == Editable_mesh and n.modifiers.count == 0) do convertToMesh n
            #spline: if not (classOf n.baseObject == SplineShape and n.modifiers.count == 0) do convertToSplineShape n
        )
    ),

    fn attachInto target src kind =
    (
        case kind of
        (
            #poly: (if superClassOf src == Shape do toKind src kind ; polyop.attach target src)
            #mesh: (if superClassOf src == Shape do toKind src kind
                    meshop.attach target src attachMat:#IDToMat condenseMat:true deleteSourceNode:true)
            #spline: (toKind src kind ; addAndWeld target src -1)
        )
    ),

    -- state: #(done, total, cancelled). Returns the resulting node.
    fn attachList nodes kind batch state =
    (
        local level = nodes
        while level.count > 1 and not state[3] do
        (
            local nextLevel = #(), i = 1
            while i <= level.count and not state[3] do
            (
                local target = level[i]
                toKind target kind
                local last = amin #(i + batch - 1, level.count)
                for j = i + 1 to last while not state[3] do
                (
                    attachInto target level[j] kind
                    state[1] += 1
                    if not (progressUpdate (100.0 * state[1] / state[2])) do state[3] = true
                )
                append nextLevel target
                i = last + 1
            )
            -- When cancelled, objects not reached yet are simply left as they are.
            level = nextLevel
        )
        if level.count == 1 do toKind level[1] kind
        level
    ),

    /*
        kind: #poly | #mesh | #spline
        Returns #(resultNodes, usedCount, skippedCount, cancelled)
    */
    fn run nodes kind:#poly byMaterial:false includeShapes:false pivotToCenter:true batch:64 =
    (
        local usable = for n in nodes where isUsable n kind includeShapes collect n
        if usable.count == 0 do return #(#(), 0, nodes.count, false)

        -- Groups to attach: everything together, or one group per material.
        local groups = #(), groupMtls = #()
        if byMaterial and kind != #spline then
        (
            for n in usable do
            (
                local index = 0
                for g = 1 to groupMtls.count where groupMtls[g] == n.material while index == 0 do index = g
                if index == 0 then (append groupMtls n.material ; append groups #(n))
                else append groups[index] n
            )
        )
        else (groups = #(usable) ; groupMtls = #(undefined))

        local state = #(0, amax #(1, usable.count - groups.count), false)
        local results = #()
        setCommandPanelTaskMode #create  -- no modify panel refresh while attaching
        progressStart "OpenTools: attaching objects"
        with redraw off
        (
            for g = 1 to groups.count while not state[3] do
            (
                local made = attachList groups[g] kind batch state
                for r in made where isValidNode r do
                (
                    if byMaterial and groupMtls[g] != undefined and made.count == 1 do
                    (
                        local wanted = groupMtls[g].name
                        local taken = getNodeByName wanted exact:true
                        r.name = if taken == undefined or taken == r then wanted else uniqueName wanted
                    )
                    if pivotToCenter do CenterPivot r
                    append results r
                )
            )
        )
        progressEnd()
        clearSelection()
        select results
        #(results, usable.count, nodes.count - usable.count, state[3])
    ),

    -- Reset or specify (lock) every normal of the selected objects.
    fn normals nodes mode =
    (
        local done = #()
        for n in nodes where isValidNode n and superClassOf n == GeometryClass and canConvertTo n Editable_Poly do
        (
            if n.modifiers.count == 0 and classOf n.baseObject != Editable_Poly do convertToPoly n
            select n
            if getCommandPanelTaskMode() != #modify do setCommandPanelTaskMode #modify
            local m = Edit_Normals()
            addModifier n m
            modPanel.setCurrentObject m
            local all = #{1..(m.GetNumNormals node:n)}
            if mode == #reset then m.Reset selection:all node:n else m.Specify selection:all node:n
            -- Collapse into the Editable Poly when nothing else is on the stack;
            -- otherwise leave the Edit Normals modifier on top (non-destructive).
            if n.modifiers.count == 1 do maxOps.CollapseNodeTo n 1 true
            append done n
        )
        clearSelection()
        select done
        done.count
    )
)
OTL_AttachTool = OTL_AttachTool()
