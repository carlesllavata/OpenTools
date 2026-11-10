-- SPDX-License-Identifier: GPL-3.0-or-later
-- OpenTools - 3-Point Scale. The work is done in three_point_rotate/three_point_core.ms.
global OTL_ThreePoint  -- declared before the block compiles (see CLAUDE.md)
(
    fileIn ((getFilenamePath (getSourceFileName())) + "../three_point_rotate/three_point_core.ms")
    OTL_ThreePoint.runScale()
)
