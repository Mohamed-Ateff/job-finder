"""python -m webapp  ->  http://localhost:8501  (add --no-browser to skip opening it)"""

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from webapp.server import HOST, PORT, app

ROOT = Path(__file__).resolve().parents[1]
KEEPER = ROOT / "tools" / "keep_online.py"
KEEPER_LOCK = 20240                     # the keeper holds this port while it runs


def watch_keeper() -> None:
    """The keeper restarts this app if it stops; this app restarts the keeper if it stops.
    Either one alone brings the other back, so the public link never stays down."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    while True:
        time.sleep(60)
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", KEEPER_LOCK))       # free: no keeper is running
        except OSError:
            continue
        finally:
            probe.close()
        try:
            subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable), str(KEEPER)], cwd=ROOT,
                             creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


if __name__ == "__main__":
    url = f"http://{'localhost' if HOST in ('127.0.0.1', '::1') else HOST}:{PORT}"
    print(f"Job Automation is running at {url}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    if KEEPER.exists() and os.name == "nt" and "--no-keeper" not in sys.argv:
        threading.Thread(target=watch_keeper, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
