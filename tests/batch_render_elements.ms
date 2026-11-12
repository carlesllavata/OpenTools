-- SPDX-License-Identifier: GPL-3.0-or-later
-- Starts tests/batch_render_elements.py. Run it with 3dsmaxbatch only: the test resets the scene.
--     "C:\Program Files\Autodesk\3ds Max 2027\3dsmaxbatch.exe" tests\batch_render_elements.ms
(
	local here = getFilenamePath (getThisScriptFilename())
	python.ExecuteFile (here + "batch_render_elements.py")
)
