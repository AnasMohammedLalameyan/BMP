#!/usr/bin/env python3
"""
scripts/run_server.py - start the BMP Compliance Platform web application.

    python scripts/run_server.py                       # http://127.0.0.1:8000 (this computer only)
    python scripts/run_server.py --host 0.0.0.0        # reachable from other computers on the network
    python scripts/run_server.py --reload              # development: restart when code changes
    python scripts/run_server.py --workers 2           # production: several worker processes

Settings come from .env (see .env.example). In production put a reverse proxy that provides HTTPS in front of it.
"""
import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import uvicorn  # noqa: E402

from app.config import Settings  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Run the BMP Compliance Platform")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    settings = Settings.load()            # fails fast, with a clear message, if the configuration is unsafe or incomplete
    print(f"BMP Compliance Platform ({settings.env}) - http://{args.host}:{args.port}")
    if settings.is_production and args.host not in ("127.0.0.1", "localhost"):
        print("  Reminder: serve this behind an HTTPS reverse proxy; do not expose it directly.")
    uvicorn.run("app.main:app", host=args.host, port=args.port, workers=args.workers if not args.reload else 1,
                reload=args.reload, proxy_headers=True, forwarded_allow_ips="127.0.0.1")


if __name__ == "__main__":
    main()
