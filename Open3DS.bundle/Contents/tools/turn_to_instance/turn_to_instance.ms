/*
    Open3DS - Turn to Instance.
    Based on "Turn To Instance" by Miled Rizk (http://www.youtube.com/c/MiledRizk),
    included in Open3DS with the author's permission; extended by Open3DS contributors.

    Select the objects to convert, run the tool, then pick the source object in a viewport.
    Every selected object of a compatible type becomes a full instance of the source (object,
    modifiers, material and name), keeping its own position, rotation and scale. One undo step.
*/
-- Declared before the block compiles; otherwise, on the first run in a session, the struct
-- name below becomes an empty local ("Unknown property in undefined").
global O3DS_TurnToInstance
(
    fileIn ((getFilenamePath (getSourceFileName())) + "turn_to_instance_core.ms")

    local targets = for n in selection where isValidNode n and not isGroupHead n collect n
    if targets.count == 0 then
        displayTempPrompt "Open3DS: select the objects to turn into instances, then run Turn to Instance." 5000
    else
    (
        fn pickable obj = (findItem targets obj) == 0 and not isGroupHead obj
        local source = pickObject message:"Turn to Instance: pick the source object (Esc cancels)" \
            prompt:"Pick the source object" filter:pickable
        if isValidNode source then
        (
            local result
            undo "Turn to Instance" on
            (
                with redraw off result = O3DS_TurnToInstance.convert targets source
            )
            local converted = result[1].count
            local skipped = result[2].count
            local message = "Open3DS: " + (converted as string) + \
                (if converted == 1 then " object" else " objects") + " turned into instances of " + source.name
            if skipped > 0 do message += "; " + (skipped as string) + " skipped (different type)"
            displayTempPrompt (message + ".") 5000
            redrawViews()
        )
        else
            displayTempPrompt "Open3DS: Turn to Instance cancelled." 3000
    )
)
