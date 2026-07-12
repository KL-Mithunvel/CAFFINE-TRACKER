#!/usr/bin/env python3
"""Caffeine Tracker entry point.

Initializes the database, runs one immediate lookup sweep for any pending
drinks, starts the background retry worker, then opens the app in a native
desktop window (pywebview) backed by a local Flask server. Run with:
python main.py (console) or pythonw.exe main.py (silent, e.g. from the
desktop shortcut).
"""
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# pythonw.exe (used by the silent desktop shortcut) runs with no console, so
# sys.stdout/sys.stderr are None. Anything that tries to print() or write to
# them — including our own code and Flask/werkzeug's internals — would raise
# AttributeError and kill the app with no visible error. Redirect to devnull
# before anything else runs; our own diagnostics go to the log file instead.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "caffeine_tracker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("main")

from app import create_app, db, lookup  # noqa: E402  (after stdout/logging setup)


def _wait_for_server(host: str, port: int, timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    app = create_app()
    config = db.get_config()

    lookup.run_pending_sweep(db.get_connection())
    worker = lookup.LookupWorker()
    worker.start()

    host = config["server"]["host"]
    port = config["server"]["port"]
    url = f"http://{host}:{port}"

    server_thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    server_thread.start()

    if not _wait_for_server(host, port):
        log.error("Server did not start within timeout; aborting")
        return

    log.info("Caffeine Tracker server ready at %s, opening window", url)

    import webview

    webview.create_window("Caffeine Tracker", url, width=1100, height=800, min_size=(800, 600))
    webview.start()

    log.info("Window closed, shutting down")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Fatal error in main()")
        raise
