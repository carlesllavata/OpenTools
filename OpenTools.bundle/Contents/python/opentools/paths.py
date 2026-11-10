# SPDX-License-Identifier: GPL-3.0-or-later
"""Filesystem locations used by OpenTools."""

import os
from pathlib import Path

# abspath (not resolve) so a mapped network drive stays "Z:\..." instead of a UNC path.
PACKAGE_DIR = Path(os.path.abspath(__file__)).parent  # .../Contents/python/opentools
CONTENTS_DIR = PACKAGE_DIR.parent.parent  # .../Contents
BUILTIN_TOOLS_DIR = CONTENTS_DIR / "tools"


def _base(env_var, fallback):
    value = os.environ.get(env_var)
    return Path(value) if value else Path.home() / fallback


def config_dir():
    """Per-user settings; roams and survives 3ds Max upgrades."""
    override = os.environ.get("OPENTOOLS_CONFIG_DIR")
    if override:
        return Path(override)
    return _base("APPDATA", "AppData/Roaming") / "OpenTools"


def data_dir():
    """Per-machine data such as logs and caches."""
    override = os.environ.get("OPENTOOLS_DATA_DIR")
    if override:
        return Path(override)
    return _base("LOCALAPPDATA", "AppData/Local") / "OpenTools"


def log_dir():
    return data_dir() / "logs"


def log_file():
    return log_dir() / "opentools.log"
