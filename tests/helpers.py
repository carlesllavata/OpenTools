# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared test helpers."""

import json
import logging
from pathlib import Path

# Keep the opentools logger quiet during tests.
_logger = logging.getLogger("opentools")
_logger.addHandler(logging.NullHandler())
_logger.propagate = False


def make_tool(root, folder_name, manifest, files=None):
    """Create <root>/<folder_name>/tool.json plus any extra files; returns the folder."""
    folder = Path(root) / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        text = manifest if isinstance(manifest, str) else json.dumps(manifest)
        (folder / "tool.json").write_text(text, encoding="utf-8")
    for name, content in (files or {}).items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return folder
