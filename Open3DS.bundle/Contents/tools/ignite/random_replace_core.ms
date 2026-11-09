/*
    Open3DS - Random Replace core (MIT, Open3DS contributors).
    Each target becomes a copy or instance of a source picked by Python (by weight).
*/
struct O3DS_RandomReplaceStruct
(
    -- a source and everything parented below it
    fn withChildren n acc =
    (
        append acc n
        for c in n.children do withChildren c acc
        acc
    ),

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

    -- sources: nodes; picks: 1-based source index per target; align: #bottom (bounding
    -- box bottom centers meet) or #pivot (the source's bottom center goes to the target's
    -- pivot). The target's rotation and scale are applied, its layer is kept and it is
    -- deleted. Returns the new nodes (selected).
    fn replaceWeighted sources picks targets instance align =
    (
        local groups = for s in sources collect (withChildren s #())
        local anchors = for g in groups collect (transMatrix (bottomCenter g))
        local result = #()
        undo "Random Replace" on
        (
            for i = 1 to targets.count do
            (
                local t = targets[i]
                if isValidNode t and findItem sources t == 0 do
                (
                    local k = picks[i]
                    local nn = #()
                    maxOps.cloneNodes groups[k] cloneType:(if instance then #instance else #copy) newNodes:&nn
                    local tm = copy t.transform
                    if align == #bottom do tm.row4 = bottomCenter #(t)
                    -- clones start where their source is: carry them over to the target
                    for r in (rootsOf nn) do r.transform = (r.transform * inverse anchors[k]) * tm
                    -- (clone names are already unique and based on the source's name)
                    for n in nn do t.layer.addNode n
                    join result nn
                )
            )
            delete (for t in targets where isValidNode t and findItem sources t == 0 collect t)
        )
        if result.count > 0 then select result else clearSelection()
        result
    )
)
global O3DS_RandomReplace = O3DS_RandomReplaceStruct()
