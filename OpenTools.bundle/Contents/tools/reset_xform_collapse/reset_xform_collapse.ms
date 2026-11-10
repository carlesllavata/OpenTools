/*
    OpenTools - Reset XForm + Collapse (MIT, OpenTools contributors).

    For every selected geometry or shape object: Reset XForm (as in Utilities), then
    collapse the stack, in one undo step.
      - Mirrored objects (negative scale) need nothing extra: in 3ds Max 2027 Reset XForm
        already keeps their faces pointing outwards (verified; flipping again would turn
        them inside out).
      - Children are unlinked while their parent is reset and linked back afterwards,
        so nothing moves.
      - Parametric objects become Editable Poly (Editable Mesh stays Editable Mesh).
*/
(
    fn canProcess n =
    (
        isValidNode n and not isGroupHead n and classOf n != TargetObject and \
        (superClassOf n == GeometryClass or superClassOf n == Shape)
    )

    local nodes = for n in selection where canProcess n collect n
    if nodes.count == 0 then
        displayTempPrompt "OpenTools: select geometry or shape objects first." 4000
    else
    (
        undo "Reset XForm + Collapse" on
        (
            with redraw off
            (
                local links = #()
                for n in nodes do for c in n.children do append links #(c, n)
                for link in links do link[1].parent = undefined

                for n in nodes do
                (
                    local geometry = superClassOf n == GeometryClass
                    local wasMesh = classOf n.baseObject == Editable_mesh
                    ResetXForm n
                    maxOps.CollapseNode n true
                    if geometry and not wasMesh and classOf n.baseObject == Editable_mesh and canConvertTo n Editable_Poly do
                        convertToPoly n
                )

                for link in links where isValidNode link[1] and isValidNode link[2] do link[1].parent = link[2]
            )
        )
        local message = "OpenTools: Reset XForm + collapse on " + (nodes.count as string) + \
            (if nodes.count == 1 then " object" else " objects")
        local skipped = selection.count - nodes.count
        if skipped > 0 do message += "; " + (skipped as string) + " skipped (not geometry or shapes)"
        displayTempPrompt (message + ".") 5000
        redrawViews()
    )
)
