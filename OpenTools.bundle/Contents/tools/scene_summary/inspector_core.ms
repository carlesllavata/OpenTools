-- SPDX-License-Identifier: GPL-3.0-or-later
/*
    OpenTools - Auditor core.

    Every check returns #(count, items) where items is an array of #(label, node)
    (node may be undefined). Fixes return how many things they changed. Loops that
    use a local inside a `where` clause are written as explicit `if`s: inside struct
    methods those fail with "Bad free thunk local member index" in 3ds Max 2027.
*/
struct OTL_InspectorStruct
(
    -- ------------------------------------------------------------ helpers
    fn className obj = (if obj == undefined then "" else (classOf obj) as string),

    fn isGeo n = (superClassOf n == GeometryClass and classOf n != TargetObject and not isGroupHead n),

    fn generatesMesh n =
    (
        -- objects whose mesh is generated at render time or is legitimately empty
        local c = toLower (className n.baseObject)
        local skip = false
        for p in #("*proxy*", "*forest*", "*railclone*", "*particle*", "pf_*", "*tyflow*", "*phoenix*", \
                   "link*", "*scatter*", "*hair*", "*fur*", "*plane*", "spray", "snow", "blizzard", "parray", \
                   "pcloud", "superspray", "*sim*", "*cache*", "*populate*", "*volume*", "*fume*", "*massfx*") do
            if matchPattern c pattern:p do skip = true
        skip
    ),

    fn faceCount n = (try ((getPolygonCount n)[1]) catch -1),

    fn propOf obj p = (if obj != undefined and isProperty obj p then (try (getProperty obj p) catch undefined) else undefined),

    fn sceneMaterials =
    (
        local mats = #()
        for n in objects do if n.material != undefined do appendIfUnique mats n.material
        mats
    ),

    -- every material and map below a material (the material included)
    fn walkMaterial m acc depth:0 =
    (
        if m != undefined and depth < 12 and findItem acc m == 0 do
        (
            append acc m
            local subs = try (getNumSubMtls m) catch 0
            for i = 1 to subs do walkMaterial (try (getSubMtl m i) catch undefined) acc depth:(depth + 1)
            local maps = try (getNumSubTexmaps m) catch 0
            for i = 1 to maps do walkMaterial (try (getSubTexmap m i) catch undefined) acc depth:(depth + 1)
        )
        acc
    ),

    fn nodeItems nodes suffix:"" =
    (
        local items = #()
        for n in nodes do append items #(n.name + suffix, n)
        items
    ),

    -- -------------------------------------------------------- scene info
    fn info =
    (
        local geo = 0, shp = 0, lgt = 0, cam = 0, hlp = 0, wsm = 0, hidden = 0, frozen = 0, groups = 0
        local faces = 0, verts = 0
        local heavy = #()
        local bases = #()
        for n in objects do
        (
            local sc = superClassOf n
            if isGroupHead n then groups += 1
            else if sc == GeometryClass and classOf n != TargetObject then
            (
                geo += 1
                local pc = try (getPolygonCount n) catch #(0, 0)
                faces += pc[1] ; verts += pc[2]
                append heavy #(pc[1], n.name, n)
                appendIfUnique bases n.baseObject
            )
            else if sc == Shape then shp += 1
            else if sc == Light then lgt += 1
            else if sc == Camera then cam += 1
            else if sc == SpaceWarpObject then wsm += 1
            else if sc == Helper then hlp += 1
            if n.isHidden do hidden += 1
            if n.isFrozen do frozen += 1
        )
        fn byFaces a b = (if a[1] > b[1] then -1 else if a[1] < b[1] then 1 else 0)
        qsort heavy byFaces
        local top = #()
        for i = 1 to (amin heavy.count 15) do append top heavy[i]
        local mats = sceneMaterials()
        local allMaps = #()
        for m in mats do walkMaterial m allMaps
        local bitmaps = 0
        for t in allMaps do if superClassOf t == textureMap and isProperty t #filename do bitmaps += 1
        local xrefScenes = try (xrefs.getXRefFileCount()) catch 0
        local xrefObjects = try (objXRefMgr.recordCount) catch 0
        #(
            #("objects", objects.count), #("geometry", geo), #("shapes", shp), #("lights", lgt),
            #("cameras", cam), #("helpers", hlp), #("spacewarps", wsm), #("groups", groups),
            #("hidden", hidden), #("frozen", frozen), #("faces", faces), #("vertices", verts),
            #("unique_meshes", bases.count), #("materials", mats.count), #("bitmaps", bitmaps),
            #("layers", LayerManager.count), #("xref_scenes", xrefScenes), #("xref_objects", xrefObjects),
            #("renderer", className renderers.current),
            #("units", (units.SystemType as string) + "|" + (units.SystemScale as string) + "|" + (units.DisplayType as string) + "|" + (units.MetricType as string)),
            #("frames", (animationRange.start.frame as integer) as string + "|" + (animationRange.end.frame as integer) as string + "|" + (frameRate as string)),
            -- 3ds Max 2024+ uses OCIO color management instead of display gamma
            #("color", (try ((ColorPipelineMgr.Mode) as string) catch (try ("gamma " + IDisplayGamma.gamma as string) catch ""))),
            #("top", top)
        )
    ),

    -- ---------------------------------------------------------- security
    -- raw candidates; Python decides what is malicious. Each: #(kind, key, label, text)
    secObjects = #(),

    fn caItems owner label acc =
    (
        local n = try (custAttributes.count owner) catch 0
        for i = n to 1 by -1 do
        (
            local d = try (custAttributes.getDef owner i) catch undefined
            if d != undefined do
            (
                append secObjects #(owner, d)
                local src = try (custAttributes.getDefSource d) catch ""
                append acc #("ca", secObjects.count, label + " > attribute " + (d.name as string), src)
            )
        )
    ),

    fn securityItems =
    (
        secObjects = #()
        local acc = #()
        for g in persistents.gather() do
        (
            local v = try ((execute (g as string)) as string) catch ""
            if v.count > 4000 do v = substring v 1 4000
            append acc #("persistent", g as string, "Persistent global " + (g as string), v)
        )
        local ss = stringStream ""
        callbacks.show to:ss
        append acc #("callbacks", "", "", ss as string)
        caItems rootNode "Scene root" acc
        caItems trackViewNodes "Track View" acc
        for i = 1 to trackViewNodes.numSubs do
        (
            local s = trackViewNodes[i]
            if s != undefined do caItems s ("Track View > " + (getSubAnimName trackViewNodes i) as string) acc
        )
        caItems globalTracks "Global Tracks" acc
        for c in #(float_script, position_script, rotation_script, scale_script, point3_script, transform_script) do
            for ctrl in (getClassInstances c) do
            (
                append secObjects #(ctrl, c)
                append acc #("script", secObjects.count, (c as string) + " controller", try (ctrl.script) catch "")
            )
        for dir in #(getDir #userStartupScripts, getDir #startupScripts) do
            for f in (getFiles (dir + "\\*.ms*")) do
            (
                local text = ""
                if matchPattern f pattern:"*.ms" do
                (
                    local fs = try (openFile f mode:"r") catch undefined
                    if fs != undefined do
                    (
                        local count = 0
                        while not eof fs and count < 2000 do (text += readLine fs + "\n" ; count += 1)
                        close fs
                    )
                )
                append acc #("file", f, "Startup file " + f, text)
            )
        acc
    ),

    fn securityRemove kind key =
    (
        case kind of
        (
            "persistent": (try (persistents.remove (key as name) ; execute (key + " = undefined") ; true) catch false)
            "callback": (try (callbacks.removeScripts id:(key as name) ; true) catch false)
            "ca": (
                local pair = secObjects[key]
                try (custAttributes.delete pair[1] pair[2] ; true) catch false
            )
            "script": (
                local pair = secObjects[key]
                local neutral = case pair[2] of
                (
                    float_script: "0.0"
                    position_script: "[0,0,0]"
                    point3_script: "[0,0,0]"
                    rotation_script: "quat 0 0 0 1"
                    scale_script: "[1,1,1]"
                    default: "matrix3 1"
                )
                try (pair[1].script = neutral ; true) catch false
            )
            "file": (deleteFile key)
            default: false
        )
    ),

    -- ----------------------------------------------------------- missing
    fn c_missing_files =
    (
        local items = #()
        local wasExcluded = ATSOps.ExcludeOutputFiles
        ATSOps.ExcludeOutputFiles = true
        ATSOps.Refresh()
        local files = #()
        ATSOps.GetFiles &files
        ATSOps.ExcludeOutputFiles = wasExcluded
        local first = if maxFileName == "" and files.count > 0 and matchPattern files[1] pattern:"*.max" then 1 else 0
        for i = 1 to files.count do
            if i != first and files[i] != "" do
            (
                local st = (ATSOps.GetFileSystemStatus files[i]) as string
                if matchPattern st pattern:"*missing*" do append items #(files[i], undefined)
            )
        #(items.count, items)
    ),

    fn isMissingClass obj = (matchPattern (className obj) pattern:"*missing*"),

    fn c_missing_plugins =
    (
        local items = #()
        for n in objects do
        (
            local what = #()
            if isMissingClass n.baseObject do append what (className n.baseObject)
            for m in n.modifiers do if isMissingClass m do append what (className m)
            if n.material != undefined do
                for x in (walkMaterial n.material #()) do if isMissingClass x do appendIfUnique what (className x)
            if isMissingClass n.controller do append what (className n.controller)
            if what.count > 0 do
            (
                local text = n.name + "  ("
                for i = 1 to what.count do text += (if i > 1 then ", " else "") + what[i]
                append items #(text + ")", n)
            )
        )
        local r = className renderers.current
        if matchPattern r pattern:"*missing*" do append items #("Renderer: " + r, undefined)
        #(items.count, items)
    ),

    fn c_missing_xrefs =
    (
        local items = #()
        for i = 1 to (try (xrefs.getXRefFileCount()) catch 0) do
        (
            local x = xrefs.getXRefFile i
            if x != undefined and not doesFileExist x.filename do append items #("XRef scene: " + x.filename, undefined)
        )
        for i = 1 to (try (objXRefMgr.recordCount) catch 0) do
        (
            local rec = objXRefMgr.GetRecord i
            if rec != undefined and not doesFileExist rec.srcFileName do append items #("XRef object file: " + rec.srcFileName, undefined)
        )
        #(items.count, items)
    ),

    fn c_missing_proxies =
    (
        local items = #()
        for n in objects do
        (
            local obj = n.baseObject
            if matchPattern (className obj) pattern:"*proxy*" do
            (
                local path = undefined
                for p in #(#filename, #fileName, #file, #proxy_file, #proxyFile, #cacheFile) while path == undefined do
                (
                    local v = propOf obj p
                    if classOf v == String and v != "" do path = v
                )
                if path != undefined and not doesFileExist path do append items #(n.name + "  (" + path + ")", n)
            )
        )
        #(items.count, items)
    ),

    -- ---------------------------------------------------------- geometry
    fn c_empty_geometry =
    (
        local nodes = #()
        -- objects emptied by their modifiers are a separate check (their base has faces)
        for n in objects do
            if isGeo n and not generatesMesh n and faceCount n == 0 and \
               (n.modifiers.count == 0 or (try (n.baseObject.mesh.numFaces) catch 0) == 0) do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn f_empty_geometry =
    (
        local nodes = for item in (c_empty_geometry())[2] collect item[2]
        undo "Delete Empty Objects" on (delete nodes)
        nodes.count
    ),

    fn c_empty_shapes =
    (
        local nodes = #()
        for n in objects do if superClassOf n == Shape and (try (numSplines n) catch 1) == 0 do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn f_empty_shapes =
    (
        local nodes = for item in (c_empty_shapes())[2] collect item[2]
        undo "Delete Empty Shapes" on (delete nodes)
        nodes.count
    ),

    fn isolatedCount n =
    (
        local obj = n.baseObject
        case classOf obj of
        (
            Editable_Poly: (
                local used = polyop.getVertsUsingFace obj #{1..(polyop.getNumFaces obj)}
                (polyop.getNumVerts obj) - used.numberSet
            )
            Editable_mesh: (
                local used = meshop.getVertsUsingFace obj #{1..obj.numFaces}
                obj.numVerts - used.numberSet
            )
            default: 0
        )
    ),
    fn c_isolated_vertices =
    (
        local items = #()
        for n in objects do if isGeo n do
        (
            local k = try (isolatedCount n) catch 0
            if k > 0 do append items #(n.name + "  (" + k as string + ")", n)
        )
        #(items.count, items)
    ),
    fn f_isolated_vertices =
    (
        local nodes = for item in (c_isolated_vertices())[2] collect item[2]
        undo "Remove Isolated Vertices" on
            for n in nodes do
                if classOf n.baseObject == Editable_Poly then polyop.deleteIsoVerts n.baseObject
                else meshop.deleteIsoVerts n.baseObject
        nodes.count
    ),

    fn isEditable n = (isGeo n and (classOf n.baseObject == Editable_Poly or classOf n.baseObject == Editable_mesh)),
    fn c_normals =
    (
        local nodes = #()
        for n in objects do if isEditable n do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn f_normals =
    (
        local pool = #()
        for n in selection do if isEditable n do append pool n
        if pool.count == 0 do pool = for item in (c_normals())[2] collect item[2]
        undo "Unify Normals" on
            for n in pool do
            (
                local alone = n.modifiers.count == 0
                addModifier n (Normalmodifier unify:true flip:false)
                -- collapse only when nothing else is on the stack (it is then the same object)
                if alone do maxOps.CollapseNodeTo n 1 true
            )
        pool.count
    ),

    -- -------------------------------------------------------- references
    blockClasses = #("LinkBlockInstance", "LinkComposite"),
    linkClasses = #("LinkLeaf", "LinkOriginPtHelper"),

    fn classItems names =
    (
        local items = #()
        for n in objects do if findItem names (className n.baseObject) > 0 do
            append items #(n.name + "  (" + className n.baseObject + ")", n)
        #(items.count, items)
    ),
    fn c_cad_blocks = (classItems blockClasses),
    fn c_linked_files = (classItems linkClasses),

    fn c_xref_scenes =
    (
        local items = #()
        for i = 1 to (try (xrefs.getXRefFileCount()) catch 0) do
        (
            local x = xrefs.getXRefFile i
            if x != undefined do append items #(x.filename, undefined)
        )
        #(items.count, items)
    ),
    fn f_xref_scenes =
    (
        local n = try (xrefs.getXRefFileCount()) catch 0
        for i = n to 1 by -1 do try (delete (xrefs.getXRefFile i)) catch ()
        n - (try (xrefs.getXRefFileCount()) catch 0)
    ),

    fn c_xref_objects =
    (
        local nodes = #()
        for n in objects do if classOf n.baseObject == XRefObject do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn f_xref_objects =
    (
        local nodes = for item in (c_xref_objects())[2] collect item[2]
        undo "Delete XRef Objects" on (delete nodes)
        nodes.count
    ),

    -- materials of a class pattern: count of materials, items = the objects using them
    fn materialUsers pattern =
    (
        local found = #(), items = #()
        for n in objects do if n.material != undefined do
        (
            local hit = false
            for m in (walkMaterial n.material #()) do
                if superClassOf m == material and matchPattern (className m) pattern:pattern do
                    (appendIfUnique found m ; hit = true)
            if hit do append items #(n.name + "  (" + n.material.name + ")", n)
        )
        #(found.count, items)
    ),
    fn c_xref_materials = (materialUsers "XRef_Material"),
    fn c_autodesk_materials = (materialUsers "Autodesk*"),
    fn c_standard_materials = (materialUsers "Standardmaterial"),

    -- ----------------------------------------------------------- cleanup
    fn removeBlocks nodes =
    (
        local done = 0
        undo "Remove CAD Blocks" on
        (
            -- keep children in place, then turn blocks with geometry into Editable Poly
            -- and delete the empty ones (helpers and parents)
            for n in nodes do for c in n.children do (local tm = c.transform ; c.parent = n.parent ; c.transform = tm)
            for n in nodes do
            (
                local tm = n.transform
                if classOf n.controller != prs do try (n.controller = prs() ; n.transform = tm) catch ()
                if superClassOf n == GeometryClass and faceCount n > 0 then
                (
                    try (convertToPoly n ; done += 1) catch ()
                )
                else (delete n ; done += 1)
            )
        )
        done
    ),
    fn f_cad_blocks = (removeBlocks (for item in (c_cad_blocks())[2] collect item[2])),
    fn f_linked_files = (removeBlocks (for item in (c_linked_files())[2] collect item[2])),

    -- dummies and points that hold nothing and that no constraint, wire or rig uses
    fn isUnusedHelper n =
    (
        local c = classOf n.baseObject
        (c == Dummy or c == Point) and not isGroupHead n and n.children.count == 0 and \
            (try (custAttributes.count n.baseObject) catch 0) == 0 and \
            (try ((refs.dependentNodes n).count) catch 1) == 0
    ),
    fn c_unused_helpers =
    (
        local nodes = #()
        for n in objects do if superClassOf n == Helper and (try (isUnusedHelper n) catch false) do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn f_unused_helpers =
    (
        local nodes = for item in (c_unused_helpers())[2] collect item[2]
        undo "Delete Unused Helpers" on (delete nodes)
        nodes.count
    ),

    fn c_groups =
    (
        local nodes = #()
        for n in objects do if isGroupHead n do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn f_groups =
    (
        local count = 0
        undo "Ungroup All" on
        (
            local heads = for n in objects where isGroupHead n collect n
            while heads.count > 0 do
            (
                count += heads.count
                explodeGroup heads
                heads = for n in objects where isGroupHead n collect n
            )
        )
        count
    ),

    fn emptyLayers =
    (
        local result = #()
        for i = LayerManager.count - 1 to 1 by -1 do
        (
            local layer = LayerManager.getLayer i
            local members = #()
            layer.nodes &members
            if members.count == 0 and layer.getNumChildren() == 0 and layer != LayerManager.current do append result layer
        )
        result
    ),
    fn c_empty_layers =
    (
        local items = for l in emptyLayers() collect #(l.name, undefined)
        #(items.count, items)
    ),
    fn f_empty_layers =
    (
        local count = 0
        local layers = emptyLayers()
        -- Inside an undo record layer deletion is undoable. Outside one it is permanent, and
        -- undoing an earlier move of objects out of a deleted layer crashes 3ds Max 2027.
        undo "Delete Empty Layers" on
        (
            -- deleting can empty a parent layer: repeat until nothing changes
            while layers.count > 0 do
            (
                for l in layers do if LayerManager.deleteLayerByName l.name do count += 1
                local remaining = emptyLayers()
                layers = if remaining.count < layers.count then remaining else #()
            )
        )
        count
    ),

    fn noteOwners =
    (
        local owners = #()
        for n in objects do if numNoteTracks n > 0 do append owners n
        if (try (numNoteTracks rootNode) catch 0) > 0 do append owners rootNode
        if (try (numNoteTracks trackViewNodes) catch 0) > 0 do append owners trackViewNodes
        owners
    ),
    fn c_note_tracks =
    (
        local items = #()
        for o in noteOwners() do
            append items #((if isValidNode o and o != rootNode then o.name else if o == rootNode then "Scene root" else "Track View") + \
                           "  (" + (numNoteTracks o) as string + ")", if isValidNode o and o != rootNode then o else undefined)
        #(items.count, items)
    ),
    fn f_note_tracks =
    (
        local count = 0
        undo "Delete Note Tracks" on
            for o in noteOwners() do
                for i = numNoteTracks o to 1 by -1 do (deleteNoteTrack o (getNoteTrack o i) ; count += 1)
        count
    ),

    fn hasLayerCtrl n = (classOf n.controller == LayerMatrix3 or classOf n.pos.controller == Position_Layer or \
                         classOf n.rotation.controller == Rotation_Layer or classOf n.scale.controller == Scale_Layer),
    fn layeredNodes =
    (
        local nodes = #()
        for n in objects do if (try (hasLayerCtrl n) catch false) do append nodes n
        nodes
    ),
    fn c_anim_layers =
    (
        local nodes = layeredNodes()
        local items = nodeItems nodes
        local extra = try (AnimLayerManager.getLayerCount()) catch 0
        if nodes.count == 0 and extra > 1 do append items #("Animation layers defined: " + extra as string, undefined)
        #(items.count, items)
    ),
    fn f_anim_layers =
    (
        local nodes = layeredNodes()
        if nodes.count > 0 do undo "Remove Animation Layers" on (AnimLayerManager.disableLayerNodes &nodes)
        nodes.count
    ),

    fn c_retimers =
    (
        local items = #()
        local n = try (RetimerMan.numRetimers) catch 0
        for i = 1 to n do append items #("Retimer " + i as string, undefined)
        if (try (RetimerMan.IsGlobalRetimerActive()) catch false) do append items #("Global retimer is active", undefined)
        #(items.count, items)
    ),
    fn f_retimers =
    (
        local n = try (RetimerMan.numRetimers) catch 0
        for i = n to 1 by -1 do try (RetimerMan.DeleteRetimer i) catch ()
        try (RetimerMan.RemoveGlobalRetimer()) catch ()
        n
    ),

    -- --------------------------------------------------------- animation
    fn animatedTree anim depth:0 =
    (
        local found = false
        if anim != undefined and depth < 6 do
        (
            if (try (anim.isAnimated) catch false) do found = true
            for i = 1 to (try (anim.numSubs) catch 0) while not found do
                if animatedTree anim[i] depth:(depth + 1) do found = true
        )
        found
    ),
    fn isAnimatedNode n =
    (
        local any = n.isAnimated or animatedTree n.baseObject
        for m in n.modifiers while not any do if animatedTree m do any = true
        any
    ),
    fn c_animated =
    (
        local nodes = #()
        for n in objects do if (try (isAnimatedNode n) catch false) do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn f_animated =
    (
        local nodes = for item in (c_animated())[2] collect item[2]
        if nodes.count > 0 do
        (
            local before = selection as array
            undo "Remove Animation" on
            (
                select nodes
                maxOps.deleteSelectedAnimation()
                if before.count > 0 then select before else clearSelection()
            )
        )
        nodes.count
    ),

    fn isSimulation n =
    (
        local c = toLower (className n.baseObject)
        local hit = false
        for p in #("pf_source", "particle_view", "*tyflow*", "*phoenix*", "liquidsim", "firesmokesim", "*massfx*", \
                   "spray", "snow", "blizzard", "parray", "pcloud", "superspray", "*fume*", "*cloth*") do
            if matchPattern c pattern:p do hit = true
        for m in n.modifiers do
        (
            local mc = toLower (className m)
            if matchPattern mc pattern:"*massfx*" or matchPattern mc pattern:"*cloth*" or matchPattern mc pattern:"*tycache*" do hit = true
        )
        hit
    ),
    fn c_simulations =
    (
        local items = #()
        for n in objects do if isSimulation n do append items #(n.name + "  (" + className n.baseObject + ")", n)
        #(items.count, items)
    ),

    -- ------------------------------------------------------------ render
    fn c_render_elements =
    (
        local mgr = maxOps.GetCurRenderElementMgr()
        local items = #()
        for i = 0 to (mgr.NumRenderElements()) - 1 do
        (
            local e = mgr.GetRenderElement i
            if e != undefined do append items #(e.elementName + "  (" + className e + ")", undefined)
        )
        #(items.count, items)
    ),
    fn c_render_effects =
    (
        local items = for i = 1 to numEffects collect #((getEffect i).name, undefined)
        #(items.count, items)
    ),
    fn c_environment_effects =
    (
        local items = for i = 1 to numAtmospherics collect #((getAtmospheric i).name, undefined)
        #(items.count, items)
    ),

    -- ----------------------------------------------------- object states
    fn isGeoOrShape n = (isGeo n or superClassOf n == Shape),
    fn nodesWhere test =
    (
        local nodes = #()
        for n in objects do if (try (test n) catch false) do append nodes n
        #(nodes.count, nodeItems nodes)
    ),
    fn listedNodes check = (for item in check[2] where isValidNode item[2] collect item[2]),

    fn isUncollapsed n = (isGeoOrShape n and n.modifiers.count > 0),
    fn c_uncollapsed = (nodesWhere isUncollapsed),
    fn f_uncollapsed =
    (
        local nodes = listedNodes (c_uncollapsed())
        undo "Collapse Stacks" on for n in nodes do maxOps.CollapseNode n true
        nodes.count
    ),

    fn isHiddenNode n = n.isHidden,
    fn c_hidden = (nodesWhere isHiddenNode),
    fn f_hidden =
    (
        local nodes = listedNodes (c_hidden())
        undo "Unhide" on unhide nodes
        nodes.count
    ),

    fn isNotRenderable n = (isGeoOrShape n and not n.renderable),
    fn c_not_renderable = (nodesWhere isNotRenderable),
    fn f_not_renderable =
    (
        local nodes = listedNodes (c_not_renderable())
        undo "Make Renderable" on for n in nodes do n.renderable = true
        nodes.count
    ),

    fn hasShadowsOff n = (isGeoOrShape n and (not n.castShadows or not n.receiveShadows)),
    fn c_shadows_off = (nodesWhere hasShadowsOff),
    fn f_shadows_off =
    (
        local nodes = listedNodes (c_shadows_off())
        undo "Turn Shadows On" on for n in nodes do (n.castShadows = true ; n.receiveShadows = true)
        nodes.count
    ),

    fn isCameraInvisible n = (isGeo n and not n.primaryVisibility),
    fn c_camera_invisible = (nodesWhere isCameraInvisible),
    fn f_camera_invisible =
    (
        local nodes = listedNodes (c_camera_invisible())
        undo "Make Visible to Camera" on for n in nodes do n.primaryVisibility = true
        nodes.count
    ),

    -- a visibility track exists and is at 0 (or below) at the start or end of the range
    fn hasZeroVisibility n =
    (
        if n[1].controller == undefined then false else
        (
            local a = at time animationRange.start n[1].value
            local b = at time animationRange.end n[1].value
            a <= 0.0 or b <= 0.0
        )
    ),
    fn c_visibility_zero = (nodesWhere hasZeroVisibility),
    fn f_visibility_zero =
    (
        local nodes = listedNodes (c_visibility_zero())
        undo "Repair Visibility" on
            for n in nodes do
            (
                local c = bezier_float()
                c.value = 1.0
                n.visibility = c
            )
        nodes.count
    ),

    -- ------------------------------------------------------ scene totals
    fn isAnyNode n = true,
    fn isShapeNode n = (superClassOf n == Shape),
    fn isLightNode n = (superClassOf n == Light),
    fn isCameraNode n = (superClassOf n == Camera),
    fn isHelperNode n = (superClassOf n == Helper and not isGroupHead n),
    fn isWarpNode n = (superClassOf n == SpaceWarpObject),
    fn c_nodes = (nodesWhere isAnyNode),
    fn c_geometry = (nodesWhere isGeo),
    fn c_shapes = (nodesWhere isShapeNode),
    fn c_lights = (nodesWhere isLightNode),
    fn c_cameras = (nodesWhere isCameraNode),
    fn c_helpers = (nodesWhere isHelperNode),
    fn c_spacewarps = (nodesWhere isWarpNode),

    -- ---------------------------------------------------- plugin objects
    fn classMatches n patterns =
    (
        local c = toLower (className n.baseObject)
        local hit = false
        for p in patterns while not hit do if matchPattern c pattern:p do hit = true
        hit
    ),
    fn patternItems patterns =
    (
        local items = #()
        for n in objects do if classMatches n patterns do append items #(n.name + "  (" + className n.baseObject + ")", n)
        #(items.count, items)
    ),
    fn c_proxies = (patternItems #("*proxy*", "*standin*")),
    fn c_xmesh = (patternItems #("*xmesh*")),
    fn c_itoo = (patternItems #("forest_*", "railclone*")),
    fn c_scatters = (patternItems #("*scatter*")),

    -- ---------------------------------------------------- more geometry
    fn baseFaces n =
    (
        local obj = n.baseObject
        case classOf obj of
        (
            Editable_Poly: polyop.getNumFaces obj
            Editable_mesh: obj.numFaces
            default: (try (obj.mesh.numFaces) catch -1)
        )
    ),
    fn isEmptiedByModifiers n =
        (isGeo n and n.modifiers.count > 0 and not generatesMesh n and faceCount n == 0 and baseFaces n > 0),
    fn c_emptied_by_modifiers = (nodesWhere isEmptiedByModifiers),

    -- mirroring (negative scale) is fine; different absolute scale per axis is not
    fn isIrregularScale n =
    (
        if not (isGeoOrShape n or superClassOf n == Light or superClassOf n == Camera) then false else
        (
            local s = n.transform.scale
            fn r v = (floor ((abs v) * 1000.0 + 0.5)) / 1000.0
            r s.x != r s.y or r s.x != r s.z
        )
    ),
    fn c_irregular_scale = (nodesWhere isIrregularScale),

    -- ---------------------------------------------------- more animation
    fn c_motion_clips =
    (
        local n = try (theMixer.numMaxMixers()) catch 0
        local items = for i = 1 to n collect #("Mixer " + i as string, undefined)
        #(items.count, items)
    ),

    -- ------------------------------------------------------- modifiers
    fn enabledOf n cls =
    (
        local found = #()
        for m in n.modifiers do if m.enabled and classOf m == cls do append found m
        found
    ),

    fn c_double_shell =
    (
        local items = #()
        for n in objects do
        (
            local k = (enabledOf n Shell).count
            if k > 1 do append items #(n.name + "  (" + k as string + " Shells)", n)
        )
        #(items.count, items)
    ),
    fn f_double_shell =
    (
        local count = 0
        undo "Repair Stacked Shell" on
            for item in (c_double_shell())[2] do
            (
                local shells = enabledOf item[2] Shell
                -- modifiers[1] is the top of the stack: keep the last one (the lowest)
                for i = 1 to shells.count - 1 do (shells[i].enabled = false ; count += 1)
            )
        count
    ),

    fn c_double_uvw =
    (
        local items = #()
        for n in objects do
        (
            local seen = #()
            local repeated = false
            for m in (enabledOf n Uvwmap) do
            (
                -- channel 0 = map channel, 1 = vertex color channel
                local key = (m.channel as string) + ":" + (m.mapChannel as string)
                if findItem seen key > 0 then repeated = true else append seen key
            )
            if repeated do append items #(n.name, n)
        )
        #(items.count, items)
    ),

    fn noMaterial n = (isGeo n and n.material == undefined),
    fn c_no_material = (nodesWhere noMaterial),

    -- ------------------------------------------------------------ render
    -- foreign: class names (from classNames) that Python found to belong to another engine
    fn c_foreign_lights foreign =
    (
        local items = #()
        for n in objects do
            if superClassOf n == Light and findItem foreign (className n.baseObject) > 0 do
                append items #(n.name + "  (" + className n.baseObject + ")", n)
        #(items.count, items)
    ),

    fn c_foreign_objects foreign =
    (
        local items = #()
        for n in objects where superClassOf n != Light do
        (
            local what = #()
            if findItem foreign (className n.baseObject) > 0 do append what (className n.baseObject)
            for m in n.modifiers do if findItem foreign (className m) > 0 do appendIfUnique what (className m)
            if n.material != undefined do
                for x in (walkMaterial n.material #()) do if findItem foreign (className x) > 0 do appendIfUnique what (className x)
            if what.count > 0 do
            (
                local text = n.name + "  ("
                for i = 1 to what.count do text += (if i > 1 then ", " else "") + what[i]
                append items #(text + ")", n)
            )
        )
        #(items.count, items)
    ),

    -- every class name used by objects, modifiers, materials and maps (for the mismatch test)
    fn classNames =
    (
        local names = #()
        for n in objects do
        (
            appendIfUnique names (className n.baseObject)
            for m in n.modifiers do appendIfUnique names (className m)
            if n.material != undefined do for x in (walkMaterial n.material #()) do appendIfUnique names (className x)
        )
        names
    ),

    dispProps = #(#displacementTexmap, #texmapDisplace, #displacement_map, #texmap_displacement, #displacementMap),
    dispMods = #("Displace", "VRayDisplacementMod", "CoronaDisplacementMod", "Displace_Mesh", "Displace_NURBS"),

    -- a map slot counts unless its on/off switch (<slot>_on or <slot>On) is off
    fn slotIsOn m p =
    (
        local active = true
        for s in #((p as string) + "_on", (p as string) + "On") do
        (
            local v = propOf m (s as name)
            if classOf v == BooleanClass and not v do active = false
        )
        active
    ),

    fn displacementUses =
    (
        local slots = #()   -- #(material, property)
        local mods = #()    -- #(node, modifier)
        local mats = #()
        for m in sceneMaterials() do walkMaterial m mats
        for m in mats do if superClassOf m == material do
        (
            -- some materials answer to two names for one slot (Physical: displacement_map
            -- and displacementMap): count each map once
            local seen = #()
            for p in dispProps do
            (
                local v = propOf m p
                if v != undefined and findItem seen v == 0 and slotIsOn m p do (append seen v ; append slots #(m, p))
            )
        )
        for n in objects do for m in n.modifiers do
            if m.enabled and findItem dispMods (className m) > 0 do append mods #(n, m)
        #(slots, mods)
    ),
    fn c_displacement_maps =
    (
        local mats = for s in (displacementUses())[1] collect s[1]
        local items = #()
        for n in objects do if n.material != undefined do
        (
            local hit = undefined
            for x in (walkMaterial n.material #()) while hit == undefined do if findItem mats x > 0 do hit = x
            if hit != undefined do append items #(n.name + "  (" + hit.name + ")", n)
        )
        #(items.count, items)
    ),
    fn f_displacement_maps =
    (
        local slots = (displacementUses())[1]
        undo "Remove Displacement Maps" on for s in slots do setProperty s[1] s[2] undefined
        slots.count
    ),
    fn c_displace_mods =
    (
        local items = for u in (displacementUses())[2] collect #(u[1].name + "  (" + className u[2] + ")", u[1])
        #(items.count, items)
    ),
    fn f_displace_mods =
    (
        local mods = (displacementUses())[2]
        undo "Remove Displace Modifiers" on for u in mods do deleteModifier u[1] u[2]
        mods.count
    ),

    -- --------------------------------------------------------- modifiers
    -- #(#(class, modifier count, object count, enabled count), ...)
    fn modifierStats =
    (
        local names = #(), mods = #(), nodes = #(), enabled = #()
        for n in objects do
        (
            local seen = #()
            for m in n.modifiers do
            (
                local c = className m
                local i = findItem names c
                if i == 0 do (append names c ; append mods #() ; append nodes 0 ; append enabled 0 ; i = names.count)
                if findItem mods[i] m == 0 do (append mods[i] m ; if m.enabled do enabled[i] += 1)
                if findItem seen c == 0 do (append seen c ; nodes[i] += 1)
            )
        )
        for i = 1 to names.count collect #(names[i], mods[i].count, nodes[i], enabled[i])
    ),

    fn modifierAction cls action =
    (
        local count = 0
        local users = #()
        for n in objects do
        (
            local hit = false
            for m in n.modifiers do if className m == cls do hit = true
            if hit do append users n
        )
        case action of
        (
            #select: (if users.count > 0 then select users else clearSelection() ; count = users.count)
            #delete: undo "Delete Modifiers" on
                for n in users do for i = n.modifiers.count to 1 by -1 do
                    if className n.modifiers[i] == cls do (deleteModifier n i ; count += 1)
            #collapse: undo "Collapse Stacks" on
                for n in users do (maxOps.CollapseNode n true ; count += 1)
            default: undo "Toggle Modifiers" on
                for n in users do for m in n.modifiers do
                    if className m == cls do (m.enabled = (action == #enable) ; count += 1)
        )
        count
    ),

    -- the whole stack of every selected object: #enable, #disable, #delete or #collapse
    fn selectionAction action =
    (
        local count = 0
        local nodes = #()
        for n in selection do if n.modifiers.count > 0 do append nodes n
        case action of
        (
            #delete: undo "Remove All Modifiers" on
                for n in nodes do for i = n.modifiers.count to 1 by -1 do (deleteModifier n i ; count += 1)
            #collapse: undo "Collapse Stacks" on
                for n in nodes do (maxOps.CollapseNode n true ; count += 1)
            default: undo "Toggle All Modifiers" on
                for n in nodes do for m in n.modifiers do (m.enabled = (action == #enable) ; count += 1)
        )
        count
    )
)
global OTL_Inspector = OTL_InspectorStruct()
