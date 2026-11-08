-- Open3DS - Paste Material. Based on CPM Lite by Aleksey Sheremetov (https://kotiger.co/CPM),
-- included with the author's permission. The work is done in copy_material_mapping/cpm_core.ms.
global O3DS_CPM  -- declared before the block compiles; otherwise, on the first run in a session,
                 -- the name below becomes an empty local ("Unknown property in undefined")
(
    fileIn ((getFilenamePath (getSourceFileName())) + "../copy_material_mapping/cpm_core.ms")
    O3DS_CPM.pasteOnto false false
)
