/*
    OpenTools - Turn to Instance, core.
    Based on "Turn To Instance" by Miled Rizk (http://www.youtube.com/c/MiledRizk),
    included in OpenTools with the author's permission; extended by OpenTools contributors.

    OTL_TurnToInstance.convert targets source
        Turns every eligible target node into a full instance of `source`: same object,
        same modifiers, same material, and the source's name (numbered). Each target keeps
        its transform, parent, children and layer. Returns #(converted, skipped).

    Verified in 3ds Max 2027:
      - instanceReplace corrupts the parameters of targeted cameras (FOV of the standard
        Target Camera, focal length of VRayPhysicalCamera) on the source too, so it is only
        used for geometry and shapes whose source has modifiers (it shares the stack).
      - Everything else drops the target's own modifiers and takes the source's base
        object: clean for cameras, lights (V-Ray IES targets stay where they are) and
        geometry, and the nodes report as instances.
      - Turning a free camera / light into a targeted one leaves it targeted without a
        target, so cameras, lights and helpers only convert within the same class.
*/
struct OTL_TurnToInstance
(
    fn isModelling n =
    (
        local sc = superClassOf n
        sc == GeometryClass or sc == Shape
    ),

    fn canConvert n source =
    (
        if not isValidNode n or n == source or isGroupHead n then false
        else if (isModelling source) and classOf source != TargetObject then
            superClassOf n == superClassOf source and classOf n != TargetObject
        else
            classOf n == classOf source
    ),

    fn shareObject n source =
    (
        if (isModelling source) and source.modifiers.count > 0 then
            instanceReplace n source
        else
        (
            while n.modifiers.count > 0 do deleteModifier n 1
            n.baseObject = source.baseObject
        )
    ),

    fn convert targets source =
    (
        local converted = #()
        local skipped = #()
        for n in targets do
        (
            if n == source then continue
            if canConvert n source then
            (
                shareObject n source
                n.material = source.material
                n.name = uniqueName source.name
                local aim = try (n.target) catch (undefined)  -- hasProperty does not see node.target
                if isValidNode aim do aim.name = n.name + ".Target"
                append converted n
            )
            -- a camera's / light's own target, picked up with it, is not worth a "skipped"
            else if isValidNode n and not isGroupHead n and classOf n != TargetObject do append skipped n
        )
        #(converted, skipped)
    )
)
