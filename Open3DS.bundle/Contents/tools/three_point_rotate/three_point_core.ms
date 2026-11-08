/*
    Open3DS - 3-Point Rotate / 3-Point Scale, shared core.
    Based on 3PointRotation and 3PointScale 1.2 (SergoScripts) by Sergo Pogosyan
    (contact@sergepogosyan.com), included in Open3DS with the author's permission;
    adapted by Open3DS contributors.

    Three snapped clicks: base point, original point, reference point (AutoCAD's rotate /
    scale by reference). Only the top-level objects of the selection are transformed, so
    children and group members follow their parent once.

    O3DS_ThreePoint.rotateByReference nodes base orig ref axis
        Rotates about `base`, around `axis`, so the direction base->orig turns onto
        base->ref. The angle is signed (no "Flip" needed, the original's to-do). Returns it.
    O3DS_ThreePoint.scaleByReference nodes base orig ref
        Uniform scale about `base` by |ref - base| / |orig - base|. Returns the factor,
        or undefined when orig is on base.
    O3DS_ThreePoint.runRotate() / runScale()
        The interactive tools: picks, then one undo step.

    Differences from the original: the rotation angle is signed and measured in the active
    viewport's construction plane (top view: world Z, as before); no confirmation dialog
    (the result applies on the third click and Ctrl+Z undoes it); uniform scale only.
*/
global O3DS_PickedPoint

tool O3DS_PickOnePoint numPoints:1
(
    on mousePoint clickNo do if clickNo == 1 do O3DS_PickedPoint = worldPoint
)

struct O3DS_ThreePoint
(
    fn say text = displayTempPrompt ("Open3DS: " + text) 5000,

    fn topLevel nodes =
    (
        local result = #()
        for n in nodes where isValidNode n do
        (
            local p = n.parent
            local inside = false
            while p != undefined and not inside do
            (
                if (findItem nodes p) > 0 then inside = true else p = p.parent
            )
            if not inside do append result n
        )
        result
    ),

    fn signedAngle v1 v2 axis =
    (
        -- both vectors projected onto the plane normal to `axis`
        local a = v1 - axis * (dot v1 axis)
        local b = v2 - axis * (dot v2 axis)
        if (length a) < 1e-6 or (length b) < 1e-6 then 0.0
        else atan2 (dot (cross a b) axis) (dot a b)
    ),

    fn rotateByReference nodes base orig ref axis =
    (
        local axisN = normalize axis
        local ang = signedAngle (orig - base) (ref - base) axisN
        -- a positive angleaxis turns counterclockwise looking down `axis` (verified in 2027)
        if ang != 0.0 do about base rotate (topLevel nodes) (angleaxis ang axisN)
        ang
    ),

    fn scaleByReference nodes base orig ref =
    (
        local d0 = length (orig - base)
        if d0 < 1e-6 then undefined
        else
        (
            local f = (length (ref - base)) / d0
            about base scale (topLevel nodes) [f, f, f]
            f
        )
    ),

    fn pickPoint message =
    (
        O3DS_PickedPoint = undefined
        local r = startTool O3DS_PickOnePoint prompt:message snap:#3D
        if r == #escape or r == #abort then undefined else O3DS_PickedPoint
    ),

    fn pickThree verb =
    (
        local base = pickPoint (verb + ": click the base point (right-click or Esc cancels)")
        if base == undefined then undefined
        else
        (
            local orig = pickPoint (verb + ": click the original point")
            if orig == undefined then undefined
            else
            (
                local ref = pickPoint (verb + ": click the reference point")
                if ref == undefined then undefined else #(base, orig, ref)
            )
        )
    ),

    fn selectedNodes = for n in selection where isValidNode n collect n,

    fn runRotate =
    (
        local nodes = selectedNodes()
        if nodes.count == 0 then say "select the objects to rotate first."
        else
        (
            local pts = pickThree "3-Point Rotate"
            if pts == undefined then say "3-Point Rotate cancelled."
            else
            (
                local axis = (getCPTM()).row3
                local ang
                undo "3-Point Rotate" on (ang = rotateByReference nodes pts[1] pts[2] pts[3] axis)
                say ("rotated " + (formattedPrint ang format:".2f") + " degrees.")
                redrawViews()
            )
        )
        ok
    ),

    fn runScale =
    (
        local nodes = selectedNodes()
        if nodes.count == 0 then say "select the objects to scale first."
        else
        (
            local pts = pickThree "3-Point Scale"
            if pts == undefined then say "3-Point Scale cancelled."
            else
            (
                local f
                undo "3-Point Scale" on (f = scaleByReference nodes pts[1] pts[2] pts[3])
                if f == undefined then say "the original point is on the base point: nothing scaled."
                else say ("scaled by " + (formattedPrint f format:".4f") + ".")
                redrawViews()
            )
        )
        ok
    )
)
