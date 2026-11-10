/*
    OpenTools - XRef Display Manager core (MIT, OpenTools contributors).
    XRef scenes (xrefs.*) and XRef object records (objXRefMgr) by index.
*/
struct OTL_XRefStruct
(
    fn flag obj p = (try (getProperty obj p) catch false),

    -- #(index, file, exists, disabled, hidden, box, auto update, top-level objects)
    fn scenes =
    (
        local rows = #()
        for i = 1 to xrefs.getXRefFileCount() do
        (
            local x = xrefs.getXRefFile i
            local count = try (x.tree.children.count) catch 0
            append rows #(i, x.filename, doesFileExist x.filename, flag x #disabled, flag x #hidden,
                          flag x #boxDisp, flag x #autoUpdate, count)
        )
        rows
    ),

    -- indexes: highest first, so that removing or merging does not shift the others
    fn sceneAction indexes action =
    (
        local done = 0
        for i in indexes do
        (
            local x = xrefs.getXRefFile i
            if x != undefined do
            (
                case action of
                (
                    #enable: x.disabled = false
                    #disable: x.disabled = true
                    #show: x.hidden = false
                    #hide: x.hidden = true
                    #box: x.boxDisp = true
                    #full: x.boxDisp = false
                    #autoOn: x.autoUpdate = true
                    #autoOff: x.autoUpdate = false
                    #update: updateXRef x
                    #merge: merge x
                    #remove: delete x
                )
                done += 1
            )
        )
        done
    ),

    fn recordNodes rec =
    (
        local types = #(#XRefObjectType)
        local items = #()
        rec.GetItems &types &items
        local nodes = #()
        for it in items do for n in (refs.dependentNodes it) do appendIfUnique nodes n
        nodes
    ),

    -- #(index, file, exists, enabled, auto update, unresolved, nested, objects, nodes)
    fn records =
    (
        local rows = #()
        for i = 1 to objXRefMgr.recordCount do
        (
            local rec = objXRefMgr.GetRecord i
            local nodes = recordNodes rec
            append rows #(i, rec.srcFileName, doesFileExist rec.srcFileName, rec.enabled, rec.autoUpdate,
                          rec.unresolved, rec.nested, rec.ItemCount #(#XRefObjectType), nodes)
        )
        rows
    ),

    fn recordAction indexes action =
    (
        local done = 0
        for i in indexes do
        (
            local rec = objXRefMgr.GetRecord i
            if rec != undefined do
            (
                case action of
                (
                    #enable: rec.enabled = true
                    #disable: rec.enabled = false
                    #autoOn: rec.autoUpdate = true
                    #autoOff: rec.autoUpdate = false
                    #update: rec.Update()
                    #merge: objXRefMgr.MergeRecordIntoScene rec
                    #remove: objXRefMgr.RemoveRecordFromScene rec
                )
                done += 1
            )
        )
        done
    )
)
global OTL_XRefs = OTL_XRefStruct()
