#!/usr/bin/env python3
"""Caffeine Tracker entry point.

Initializes the database, runs one immediate lookup sweep for any pending
drinks, starts the background retry worker, opens the browser, and serves
the app locally. Run with: python main.py
"""
import logging
import threading
import webbrowser

from app import create_app, db, lookup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    app = create_app()
    config = db.get_config()

    lookup.run_pending_sweep(db.get_connection())
    worker = lookup.LookupWorker()
    worker.start()

    host = config["server"]["host"]
    port = config["server"]["port"]
    url = f"http://{host}:{port}"

    if config["server"].get("open_browser", True):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"Caffeine Tracker running at {url} (Ctrl+C to stop)")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
