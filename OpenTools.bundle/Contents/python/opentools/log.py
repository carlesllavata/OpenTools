# SPDX-License-Identifier: GPL-3.0-or-later
"""Logging to a rotating file plus the MAXScript Listener."""

import logging
import logging.handlers
import sys

from . import paths

LOGGER_NAME = "opentools"
_FORMAT_FILE = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_FORMAT_CONSOLE = "[OpenTools] %(levelname)s: %(message)s"


class _CurrentStdoutHandler(logging.StreamHandler):
    """Writes to whatever sys.stdout is at emit time (the Listener, or a redirect)."""

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _value):
        pass


def get(name=None):
    return logging.getLogger(LOGGER_NAME + ("." + name if name else ""))


def setup(dev=False):
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if dev else logging.INFO)
    logger.propagate = False

    # Remove handlers from a previous setup (e.g. after opentools.reload()).
    for handler in list(logger.handlers):
        if getattr(handler, "_opentools", False):
            logger.removeHandler(handler)
            handler.close()

    try:
        paths.log_dir().mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            paths.log_file(), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(_FORMAT_FILE))
        file_handler.setLevel(logging.DEBUG)
        file_handler._opentools = True
        logger.addHandler(file_handler)
    except OSError as exc:
        print("[OpenTools] Could not open log file: %s" % exc)

    console = _CurrentStdoutHandler()
    console.setFormatter(logging.Formatter(_FORMAT_CONSOLE))
    console.setLevel(logging.INFO if dev else logging.WARNING)
    console._opentools = True
    logger.addHandler(console)
    return logger
