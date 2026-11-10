-- OpenTools startup: puts Contents/python on sys.path and starts the hub.
-- Runs as a "post-start-up script" of the ApplicationPlugins bundle.
(
    local here = substituteString (getFilenamePath (getThisScriptFilename())) "\\" "/"
    python.Execute ( \
        "import sys, os\n" + \
        "root = os.path.normpath(os.path.join(r'" + here + "', '..', 'python'))\n" + \
        "if root not in sys.path: sys.path.insert(0, root)\n" + \
        "import opentools.bootstrap\n" + \
        "opentools.bootstrap.start()\n" )
)
