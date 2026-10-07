#!/usr/bin/env python3
"""Entry point: starts the Olive Harvester dashboard.

Usage:
    python run.py
    python run.py --port 8000
"""

from __future__ import annotations

import argparse

from app import create_app

app = create_app()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Olive Harvester dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    print(f"Olive Harvester dashboard running at http://{args.host}:{args.port}")
    # debug=False is intentional: the Flask reloader would spawn a second
    # process and duplicate HarvestController's background sensor thread.
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
