-- SPDX-License-Identifier: GPL-3.0-or-later
/*
    OpenTools - Random Wire Color.

    Gives every selected object a different wire color (the object color in the Modify panel),
    in one undo step, so wire-color masks (Corona CMasking_WireColor, V-Ray VRayWireColor...)
    separate each object. Clicking again gives a new combination.
      - Colors are spread rather than purely random: hues step by the golden ratio from a
        random start, across a few saturation / brightness levels, then shuffled. Two objects
        never get near-identical colors, and no color is near black, white or grey.
      - Group heads are skipped (the members carry the color).
*/
(
    fn spreadColors count =
    (
        local golden = 0.618033988749895
        local sats = #(0.9, 0.6, 1.0)
        local vals = #(1.0, 0.75, 0.9, 0.6)
        local start = random 0.0 1.0
        local colors = for i = 0 to count - 1 collect
        (
            local hueStep = mod (start + i * golden) 1.0
            local c = color 255 0 0
            c.hue = hueStep * 255.0
            c.saturation = sats[1 + (mod i sats.count) as integer] * 255.0
            c.value = vals[1 + (mod (i / sats.count) vals.count) as integer] * 255.0
            c
        )
        -- shuffle so a new click gives a new combination, not just a rotated one
        for i = colors.count to 2 by -1 do
        (
            local j = random 1 i
            swap colors[i] colors[j]
        )
        colors
    )

    local nodes = for n in selection where isValidNode n and not isGroupHead n collect n
    if nodes.count == 0 then
        displayTempPrompt "OpenTools: select objects first." 4000
    else
    (
        local colors = spreadColors nodes.count
        undo "Random Wire Color" on
        (
            for i = 1 to nodes.count do nodes[i].wirecolor = colors[i]
        )
        displayTempPrompt ("OpenTools: new wire colors on " + (nodes.count as string) + \
            (if nodes.count == 1 then " object." else " objects.")) 4000
        redrawViews()
    )
)
