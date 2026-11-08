-- Open3DS - 3-Point Scale. Based on 3PointScale by Sergo Pogosyan (SergoScripts),
-- included with the author's permission. The work is done in three_point_rotate/three_point_core.ms.
global O3DS_ThreePoint  -- declared before the block compiles (see CLAUDE.md)
(
    fileIn ((getFilenamePath (getSourceFileName())) + "../three_point_rotate/three_point_core.ms")
    O3DS_ThreePoint.runScale()
)
