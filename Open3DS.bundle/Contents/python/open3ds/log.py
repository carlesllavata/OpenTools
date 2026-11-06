"""Logging to a rotating file plus the MAXScript Listener."""

import logging
import logging.handlers
import sys

from . import paths

LOGGER_NAME = "open3ds"
_FORMAT_FILE = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_FORMAT_CONSOLE = "[Open3DS] %(levelname)s: %(message)s"


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

    # Remove handlers from a previous setup (e.g. after open3ds.reload()).
    for handler in list(logger.handlers):
        if getattr(handler, "_open3ds", False):
            logger.removeHandler(handler)
            handler.close()

    try:
        paths.log_dir().mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            paths.log_file(), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(_FORMAT_FILE))
        file_handler.setLevel(logging.DEBUG)
        file_handler._open3ds = True
        logger.addHandler(file_handler)
    except OSError as exc:
        print("[Open3DS] Could not open log file: %s" % exc)

    console = _CurrentStdoutHandler()
    console.setFormatter(logging.Formatter(_FORMAT_CONSOLE))
    console.setLevel(logging.INFO if dev else logging.WARNING)
    console._open3ds = True
    logger.addHandler(console)
    return logger
