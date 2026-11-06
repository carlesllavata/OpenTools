/*
    Open3DS - Detach Elements core (MIT, Open3DS contributors).
    Splits Editable Poly / Editable Mesh objects into one object per element or per
    material ID. Independent implementation; the UI lives in detach_elements.py.
*/
struct O3DS_DetachTool
(
    fn isEditable node =
    (
        isValidNode node and node.modifiers.count == 0 and \
        (classOf node.baseObject == Editable_Poly or classOf node.baseObject == Editable_mesh)
    ),

    -- Lowest set bit of a bitarray, or undefined.
    fn firstBit bits =
    (
        local found = undefined
        for b in bits while found == undefined do found = b
        found
    ),

    -- #(dataPair id:<int> faces:<bitarray>, ...) for every material ID used by the poly.
    fn facesById node =
    (
        local byId = #()
        for f = 1 to polyop.getNumFaces node do
        (
            local id = polyop.getFaceMatID node f
            if byId[id] == undefined then byId[id] = #{f} else byId[id][f] = true
        )
        for id = 1 to byId.count where byId[id] != undefined collect (dataPair id:id faces:byId[id])
    ),

    fn elementCount node =
    (
        local remaining = #{1..(polyop.getNumFaces node)}, count = 0
        while not remaining.isEmpty do
        (
            remaining -= polyop.getElementsUsingFace node #{(firstBit remaining)}
            count += 1
        )
        count
    ),

    -- Pieces an Editable Mesh would split into, counted without converting it.
    fn meshPieces node byId =
    (
        if byId then
        (
            local ids = #{}
            for f = 1 to getNumFaces node do ids[getFaceMatID node f] = true
            ids.numberSet
        )
        else
        (
            local remaining = #{1..(getNumFaces node)}, count = 0
            while not remaining.isEmpty do
            (
                remaining -= meshop.getElementsUsingFace node #{(firstBit remaining)}
                count += 1
            )
            count
        )
    ),

    -- Edges shared by faces of two different groups (where the split will happen).
    fn splitEdges node groups =
    (
        local seen = #{}, shared = #{}
        for g in groups do
        (
            local e = polyop.getEdgesUsingFace node g.faces
            shared += seen * e
            seen += e
        )
        shared
    ),

    -- Make the normals along the split edges explicit, so shading does not change
    -- once the faces live in separate objects.
    fn lockNormals node edges =
    (
        if edges.isEmpty do return false
        select node
        if getCommandPanelTaskMode() != #modify do setCommandPanelTaskMode #modify
        local m = Edit_Normals()
        addModifier node m
        modPanel.setCurrentObject m
        local normals = #{}
        m.ConvertEdgeSelection &edges &normals node:node
        if not normals.isEmpty do m.MakeExplicit selection:normals node:node
        maxOps.CollapseNodeTo node 1 true
        true
    ),

    fn brightColor =
    (
        local c = color 255 0 0
        c.hue = random 0.0 255.0
        c.saturation = random 140.0 220.0
        c.value = random 190.0 255.0
        c
    ),

    fn subMaterial mm id =
    (
        local index = findItem mm.materialIDList id
        if index == 0 and mm.materialList.count > 0 do index = (mod (id - 1) mm.materialList.count) as integer + 1
        if index > 0 then mm.materialList[index] else undefined
    ),

    -- Give a part only the sub-materials it uses: a single material, or a smaller
    -- Multi/Sub-Object (shared between parts that use the same IDs).
    fn trimMaterial node cache =
    (
        local mm = node.material
        if classOf mm != MultiMaterial do return false
        local groups = facesById node
        if groups.count == 1 then
        (
            local sub = subMaterial mm groups[1].id
            if sub != undefined do node.material = sub
        )
        else
        (
            local key = mm.name
            for g in groups do key += "_" + (g.id as string)
            local newMM = undefined
            for entry in cache where entry[1] == key and entry[2] == mm while newMM == undefined do newMM = entry[3]
            if newMM == undefined do
            (
                newMM = MultiMaterial numsubs:groups.count name:key
                for i = 1 to groups.count do
                (
                    newMM.materialIDList[i] = i
                    newMM.materialList[i] = subMaterial mm groups[i].id
                    local slot = findItem mm.materialIDList groups[i].id
                    if slot > 0 do newMM.names[i] = mm.names[slot]
                )
                append cache #(key, mm, newMM)
            )
            for i = 1 to groups.count do polyop.setFaceMatID node groups[i].faces i
            node.material = newMM
        )
        true
    ),

    -- Detach every element (byId:false) or every material ID (byId:true) of one poly node.
    fn splitNode node byId =
    (
        local parts = #(node)
        local baseName = node.name
        while true do
        (
            local numFaces = polyop.getNumFaces node
            if numFaces == 0 do exit
            local faces = if byId then polyop.getFacesByMatId node (polyop.getFaceMatID node 1) \
                          else polyop.getElementsUsingFace node #{1}
            if (#{1..numFaces} - faces).isEmpty do exit
            local partName = uniqueName (baseName + "_part")
            polyop.detachFaces node faces delete:true asNode:true name:partName
            local part = getNodeByName partName exact:true
            if part != undefined do append parts part
        )
        if parts.count > 1 do node.name = uniqueName (baseName + "_part")
        parts
    ),

    /*
        Returns #(parts, skippedNodes, singleNodes):
          parts        every resulting object (originals included)
          skippedNodes not Editable Poly/Mesh, or with modifiers on top
          singleNodes  nothing to split (one element / one ID)
    */
    fn run nodes byId:false randomColor:true pivotToCenter:true keepNormals:false trimMaterials:false =
    (
        local skipped = #(), single = #(), work = #(), wasMesh = #()
        for n in nodes do
        (
            if not isEditable n then append skipped n else
            (
                local mesh = classOf n.baseObject == Editable_mesh
                local pieces = if mesh then meshPieces n byId \
                               else (if byId then (facesById n).count else elementCount n)
                if pieces < 2 then append single n else
                (
                    if mesh do convertToPoly n
                    polyop.collapseDeadStructs n
                    append work n
                    append wasMesh mesh
                )
            )
        )
        local parts = #(), cache = #()
        if work.count > 0 do
        (
            if keepNormals and byId do
                for n in work do lockNormals n (splitEdges n (facesById n))
            with redraw off
            (
                for i = 1 to work.count do
                (
                    local pieces = splitNode work[i] byId
                    for p in pieces do
                    (
                        polyop.deleteIsoVerts p
                        if trimMaterials do trimMaterial p cache
                        if randomColor do p.wirecolor = brightColor()
                        if pivotToCenter do CenterPivot p
                        if wasMesh[i] do convertToMesh p
                    )
                    join parts pieces
                )
            )
            clearSelection()
            select parts
        )
        #(parts, skipped, single)
    )
)
O3DS_DetachTool = O3DS_DetachTool()
