"""Development bridge: run Python files dropped into a folder inside the live 3ds Max.

Only started when Open3DS is loaded through dev/install_dev.ps1. The client is
dev/bridge.py. Protocol, all inside <repo>/.devbridge/:

    inbox/<id>.py     code to run (written as .tmp, then renamed, so it is never half-read)
    outbox/<id>.json  {"id", "ok", "stdout", "stderr", "error", "result", "seconds"}

Jobs run on the main thread (a QTimer), which is where pymxs must be used.
Assign `_result` in the code to send a JSON-serialisable value back.
"""

import io
import json
import os
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from PySide6 import QtCore

from . import __version__, log, maxhost

_log = log.get("devbridge")
_bridge = None


def _jsonable(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def _write_json_atomic(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class Bridge:
    def __init__(self, root, poll_ms=500):
        self.root = Path(root)
        self.inbox = self.root / "inbox"
        self.outbox = self.root / "outbox"
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)
        self._busy = False
        self.timer = QtCore.QTimer()
        self.timer.setInterval(max(100, int(poll_ms)))
        self.timer.timeout.connect(self._poll)

    def start(self):
        _write_json_atomic(
            self.root / "status.json",
            {
                "pid": os.getpid(),
                "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                "open3ds": __version__,
                "max_year": maxhost.max_year(),
            },
        )
        self.timer.start()
        _log.info("Dev bridge listening on %s", self.inbox)

    def stop(self):
        self.timer.stop()
        try:
            (self.root / "status.json").unlink()
        except OSError:
            pass
        _log.info("Dev bridge stopped.")

    def _poll(self):
        if self._busy:
            return
        self._busy = True
        try:
            for job in sorted(self.inbox.glob("*.py")):
                self._run(job)
        except Exception:  # noqa: BLE001
            _log.exception("Dev bridge poll failed")
        finally:
            self._busy = False

    def _run(self, job):
        job_id = job.stem
        try:
            code = job.read_text(encoding="utf-8-sig")
        except OSError:
            return
        try:
            job.unlink()  # remove first so a crashing job is never re-run
        except OSError:
            pass

        stdout, stderr = io.StringIO(), io.StringIO()
        result = {"id": job_id, "ok": True, "error": None, "result": None}
        import open3ds
        import pymxs

        namespace = {
            "__name__": "__open3ds_bridge__",
            "rt": pymxs.runtime,
            "pymxs": pymxs,
            "open3ds": open3ds,
        }
        started = time.perf_counter()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                exec(compile(code, "<bridge:%s>" % job_id, "exec"), namespace)  # noqa: S102 - dev only
                if "_result" in namespace:
                    result["result"] = _jsonable(namespace["_result"])
            except BaseException:  # noqa: BLE001 - report everything, including SystemExit
                result["ok"] = False
                result["error"] = traceback.format_exc()
        result["seconds"] = round(time.perf_counter() - started, 3)
        result["stdout"] = stdout.getvalue()
        result["stderr"] = stderr.getvalue()
        try:
            _write_json_atomic(self.outbox / (job_id + ".json"), result)
        except OSError:
            _log.exception("Could not write bridge result for %s", job_id)


def start(root, poll_ms=500):
    global _bridge
    stop()
    _bridge = Bridge(root, poll_ms)
    _bridge.start()
    return _bridge


def stop():
    global _bridge
    if _bridge is not None:
        _bridge.stop()
    _bridge = None
