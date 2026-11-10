-- SPDX-License-Identifier: GPL-3.0-or-later
/*
    OpenTools - Clean DWG, core.

    OTL_CleanDWG.run nodes layerName flatten makeGroup
        For linework imported from DWG. Explodes the groups among `nodes`, then:
          flatten on   every shape is flattened onto Z = 0 (in place: same node, name,
                       layer settings and properties; rotation and scale reset) and every
                       other object (meshes, block parents, dummies...) is deleted
          flatten off  nothing is flattened or deleted
        Every remaining object moves to the layer `layerName` (created if needed) keeping
        the color it shows (its layer's color when it was "by layer"), and with makeGroup
        they are grouped under that name. Returns #(flattened, deleted, moved, groupHead,
        names of the layers the objects came from). The caller wraps it in an undo record.

    OTL_CleanDWG.deleteLayersIfEmpty names
        Deletes those layers when they have no objects and no sub-layers (never layer 0 or
        the current one). Returns the count. Call it inside the same undo record as `run`:
        there, undo brings the layers back; outside one, undoing the moves later makes
        3ds Max 2027 crash (it puts the objects back on a deleted layer).

    Differences from the original: only the layers the cleaned objects came from are
    deleted when empty (the original deleted every empty layer in the scene, which wipes
    template layer structures kept empty on purpose); shapes are flattened in place instead
    of being rebuilt as new lines; the shown color is kept even for "by layer" objects; the
    current layer is left as it was; status in the OpenTools window instead of message boxes.
*/
struct OTL_CleanDWG
(
    fn shownColor n = if n.colorByLayer then n.layer.wireColor else n.wireColor,

    fn isFlattenable n = superClassOf n == Shape and canConvertTo n SplineShape,

    fn expandGroups nodes =
    (
        -- selected group heads stand for all their members, at every level
        local result = #()
        local heads = #()
        for n in nodes where isValidNode n do
        (
            if isGroupHead n then
            (
                append heads n
                local stack = for c in n.children where isGroupMember c collect c
                while stack.count > 0 do
                (
                    local m = stack[stack.count]
                    stack.count = stack.count - 1
                    if isGroupHead m then append heads m else appendIfUnique result m
                    for c in m.children where isGroupMember c do append stack c
                )
            )
            else appendIfUnique result n
        )
        for h in heads where isValidNode h and isGroupHead h do explodeGroup h
        for n in result where isValidNode n and not isGroupHead n collect n
    ),

    fn flattenShape n =
    (
        convertToSplineShape n
        local data = #()
        in coordsys world
        (
            for s = 1 to numSplines n do
                append data (for k = 1 to numKnots n s collect \
                    #(getKnotPoint n s k, getInVec n s k, getOutVec n s k))
        )
        n.transform = transMatrix [n.pos.x, n.pos.y, 0]
        in coordsys world
        (
            for s = 1 to data.count do
                for k = 1 to data[s].count do
                (
                    local d = data[s][k]
                    setKnotPoint n s k [d[1].x, d[1].y, 0]
                    setInVec n s k [d[2].x, d[2].y, 0]
                    setOutVec n s k [d[3].x, d[3].y, 0]
                )
        )
        updateShape n
    ),

    fn isEmptyLayer layer =
    (
        local members = #()
        layer.nodes &members
        members.count == 0 and layer.getNumChildren() == 0 and layer != LayerManager.current and \
            layer != (LayerManager.getLayer 0)
    ),

    fn deleteLayersIfEmpty names =
    (
        local count = 0
        for lname in names do
        (
            local layer = LayerManager.getLayerFromName lname
            if layer != undefined and isEmptyLayer layer and LayerManager.deleteLayerByName lname do count += 1
        )
        count
    ),

    fn run nodes layerName flatten makeGroup =
    (
        local sourceLayers = #()
        for n in nodes where isValidNode n do appendIfUnique sourceLayers n.layer.name
        local work = expandGroups nodes
        for n in work do appendIfUnique sourceLayers n.layer.name
        local flattened = 0
        local deleted = 0
        local keep = #()
        progressStart "Clean DWG"
        for i = 1 to work.count do
        (
            local n = work[i]
            if isValidNode n do
            (
                if not flatten then append keep n
                else if isFlattenable n then
                (
                    local c = shownColor n
                    flattenShape n
                    n.colorByLayer = false
                    n.wireColor = c
                    flattened += 1
                    append keep n
                )
                else
                (
                    delete n
                    deleted += 1
                )
            )
            if (mod i 50) == 0 do progressUpdate (100.0 * i / work.count)
        )
        progressEnd()

        local layer = LayerManager.getLayerFromName layerName
        if layer == undefined do layer = LayerManager.newLayerFromName layerName
        keep = for n in keep where isValidNode n collect n
        for n in keep do
        (
            local c = shownColor n
            n.colorByLayer = false
            n.wireColor = c
            layer.addNode n
        )

        local head = undefined
        if makeGroup and keep.count > 0 do
        (
            head = group keep name:layerName
            layer.addNode head
            select head
        )
        if head == undefined do (if keep.count > 0 then select keep else clearSelection())
        #(flattened, deleted, keep.count, head, sourceLayers)
    )
)
