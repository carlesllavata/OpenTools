-- SPDX-License-Identifier: GPL-3.0-or-later
-- OpenTools - Paste Material Copy. The work is done in copy_material_mapping/cpm_core.ms.
global OTL_CPM  -- declared before the block compiles; otherwise, on the first run in a session,
                 -- the name below becomes an empty local ("Unknown property in undefined")
(
    fileIn ((getFilenamePath (getSourceFileName())) + "../copy_material_mapping/cpm_core.ms")
    OTL_CPM.pasteOnto false true
)
