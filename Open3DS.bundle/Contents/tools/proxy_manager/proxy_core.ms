/*
    Open3DS - Proxy Display Manager core (MIT, Open3DS contributors).
    Lists proxy objects quickly; Python decides labels and display values.
*/
struct O3DS_ProxyStruct
(
    fn propOf obj p = (if isProperty obj p then (try (getProperty obj p) catch undefined) else undefined),

    -- rows: #(node, class name, file, file exists, display value or -1, box mode, hidden, frozen)
    -- classes: known proxy class names; any other class with "proxy" in its name is listed too
    fn listProxies classes fileProps displayProps selectedOnly:false =
    (
        local rows = #()
        local known = Dictionary #string  -- file -> exists (one disk check per file)
        local pool = if selectedOnly then (selection as array) else (objects as array)
        for n in pool do
        (
            local obj = n.baseObject
            local c = (classOf obj) as string
            local i = findItem classes c
            if i > 0 or matchPattern c pattern:"*proxy*" do
            (
                local file = ""
                local props = if i > 0 then fileProps[i] else #(#fileName, #filename, #file, #proxy_file)
                for p in props while file == "" do
                (
                    local v = propOf obj p
                    if classOf v == String do file = v
                )
                local shown = -1
                if i > 0 and displayProps[i] != "" do
                (
                    local v = propOf obj (displayProps[i] as name)
                    if v != undefined do shown = v as integer
                )
                local exists = false
                if file != "" do
                (
                    local key = toLower file
                    if hasDictValue known key then exists = known[key]
                    else (exists = doesFileExist file ; known[key] = exists)
                )
                append rows #(n, c, file, exists, shown, n.boxMode, n.isHidden, n.isFrozen)
            )
        )
        rows
    )
)
global O3DS_Proxies = O3DS_ProxyStruct()
