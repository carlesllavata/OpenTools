-- Sample MAXScript tool: select all instances of the selected object.
(
    if selection.count != 1 then
        messageBox "Select exactly one object." title:"Select Instances"
    else
    (
        local instances = #()
        InstanceMgr.GetInstances selection[1] &instances
        select instances
        format "[Open3DS] Selected % instance(s).\n" instances.count
    )
)
