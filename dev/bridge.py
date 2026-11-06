"""Client for the Open3DS dev bridge: runs Python inside the live 3ds Max.

Run with the Python bundled with 3ds Max (any Python 3.8+ works):

    python -I dev/bridge.py ping
    python -I dev/bridge.py reload
    python -I dev/bridge.py -c "print(rt.objects.count)"
    python -I dev/bridge.py path/to/script.py

Inside the code: `rt` (pymxs.runtime), `pymxs` and `open3ds` are predefined;
assign `_result = ...` to get a value back. Exit code: 0 ok, 1 error in Max,
2 no answer (3ds Max closed, or Open3DS not loaded through dev/install_dev.ps1).
"""

import argparse
import json
import os
import sys
import time
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, ".devbridge")

PING = """
import sys
_result = {
    "open3ds": open3ds.__version__,
    "max_year": open3ds.maxhost.max_year(),
    "python": sys.version.split()[0],
    "tools": sorted(open3ds.app.current().registry.tools) if open3ds.app.current() else None,
    "errors": [[str(p), m] for p, m in open3ds.app.current().registry.errors] if open3ds.app.current() else None,
}
"""

RELOAD = """
app = open3ds.reload()
_result = {"tools": len(app.registry.tools), "errors": [[str(p), m] for p, m in app.registry.errors]}
"""


def send(code, timeout):
    inbox = os.path.join(ROOT, "inbox")
    outbox = os.path.join(ROOT, "outbox")
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(outbox, exist_ok=True)

    job_id = "%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:6])
    job = os.path.join(inbox, job_id + ".py")
    tmp = os.path.join(inbox, job_id + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(code)
    os.replace(tmp, job)

    answer = os.path.join(outbox, job_id + ".json")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(answer):
            for _attempt in range(10):
                try:
                    with open(answer, encoding="utf-8") as handle:
                        data = json.load(handle)
                    break
                except (OSError, ValueError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Could not read %s" % answer)
            try:
                os.remove(answer)
            except OSError:
                pass
            return data
        time.sleep(0.15)

    # Nobody picked it up: withdraw the job so it does not run later by surprise.
    picked_up = not os.path.exists(job)
    try:
        os.remove(job)
    except OSError:
        pass
    return {"timeout": True, "picked_up": picked_up}


def main(argv=None):
    # Windows consoles default to cp1252; never crash on characters such as "▾" or "…".
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser =argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", help="'ping', 'reload' or a .py file to run")
    parser.add_argument("-c", dest="code", help="code to run")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds to wait (default 60)")
    args = parser.parse_args(argv)

    if args.code is not None:
        code = args.code
    elif args.target == "ping":
        code = PING
        args.timeout = min(args.timeout, 10.0)
    elif args.target == "reload":
        code = RELOAD
    elif args.target:
        with open(args.target, encoding="utf-8-sig") as handle:
            code = handle.read()
    else:
        parser.error("give 'ping', 'reload', a file, or -c CODE")

    data = send(code, args.timeout)
    if data.get("timeout"):
        if data.get("picked_up"):
            print("3ds Max took the job but did not answer within %.0fs (still running?)." % args.timeout, file=sys.stderr)
        else:
            print(
                "No answer from 3ds Max. Is it open, with Open3DS loaded via dev/install_dev.ps1?",
                file=sys.stderr,
            )
        return 2

    if data.get("stdout"):
        sys.stdout.write(data["stdout"])
        if not data["stdout"].endswith("\n"):
            sys.stdout.write("\n")
    if data.get("stderr"):
        sys.stderr.write(data["stderr"])
    if data.get("result") is not None:
        print(json.dumps(data["result"], indent=2, ensure_ascii=False))
    if not data.get("ok"):
        sys.stderr.write(data.get("error") or "unknown error\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
