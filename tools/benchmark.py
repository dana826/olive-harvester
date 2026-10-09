#!/usr/bin/env python3
"""Measure software processing times on the machine it is run on.

Run it on the Raspberry Pi 4 (and on any PC for comparison):

    python tools/benchmark.py            # default: 200 images, 1000 DB rows

It reports median / 95th percentile / max timings for:
  1. maturity classification of one saved 640x480 JPEG (load + analyse)
  2. one control-loop iteration (sensor read + status snapshot)
  3. database insert of one session record
  4. database query: latest 20 sessions, and sessions of one branch

Images are the simulator's synthetic photos; replace them with real
Camera Module 3 photos for real-image timing (--images-dir).
"""

from __future__ import annotations

import argparse
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig  # noqa: E402
from app.core.harvest_controller import HarvestController  # noqa: E402
from app.core.maturity import MaturityDetector  # noqa: E402
from app.hardware.camera import MockCamera  # noqa: E402
from app.hardware.sensors import MockSensorArray  # noqa: E402
from app.storage.db import Database  # noqa: E402


def summarize(name: str, samples_s: list) -> dict:
    ms = sorted(s * 1000 for s in samples_s)
    p95 = ms[min(len(ms) - 1, int(round(0.95 * (len(ms) - 1))))]
    row = {
        "name": name,
        "n": len(ms),
        "median_ms": statistics.median(ms),
        "p95_ms": p95,
        "max_ms": ms[-1],
    }
    print(f"{name:<46} n={row['n']:<5} median={row['median_ms']:8.3f} ms  "
          f"p95={row['p95_ms']:8.3f} ms  max={row['max_ms']:8.3f} ms")
    return row


def timed(fn, repeats: int) -> list:
    out = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=int, default=200)
    ap.add_argument("--rows", type=int, default=1000)
    ap.add_argument("--images-dir", type=Path, default=None,
                    help="folder of real JPEG/PNG photos to time instead of synthetic ones")
    args = ap.parse_args()

    print(f"Python {platform.python_version()} on {platform.platform()}")
    print(f"Machine: {platform.machine()}, processor: {platform.processor() or 'n/a'}\n")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg = AppConfig()

        # --- image set --------------------------------------------------
        if args.images_dir:
            paths = sorted(p for p in args.images_dir.iterdir()
                           if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
            if not paths:
                print("No images found in --images-dir")
                return 1
        else:
            cam = MockCamera(tmp / "captures")
            cam_time = cam.capture  # includes simulated 0.3 s latency; not timed
            paths = [cam_time().image_path for _ in range(args.images)]
        detector = MaturityDetector()
        detector.detect(paths[0])  # warm-up (imports, caches)

        results = []
        it = iter(range(10**9))
        results.append(summarize(
            "maturity classification (per image)",
            timed(lambda: detector.detect(paths[next(it) % len(paths)]), len(paths)),
        ))

        # --- control loop iteration ------------------------------------
        db = Database(tmp / "db" / "bench.db", cfg.schema_path)
        controller = HarvestController(
            capture_dir=tmp / "captures2",
            profiles_path=cfg.vibration_profiles_path,
            db=db,
            branches=cfg.branches,
        )
        sensors = MockSensorArray()
        params = {"frequency_hz": 18.0, "amplitude_mm": 14.0, "duration_s": 6.0}
        results.append(summarize(
            "control-loop iteration (sensor read + snapshot)",
            timed(lambda: (sensors.read(True, params), controller.snapshot()), 2000),
        ))

        # --- database ---------------------------------------------------
        def session(i):
            return {
                "branch_id": f"T{i % 3 + 1}-B{i % 4 + 1}", "maturity_class": "ripe",
                "confidence": 0.72, "frequency_hz": 18.0, "amplitude_mm": 14.0,
                "duration_target_s": 6.0, "duration_actual_s": 6.1,
                "harvested_mass_g": 72.3, "status": "completed",
                "operator_override": False, "image_url": "/api/captures/x.jpg",
                "ended_at": datetime.now().isoformat(),
            }

        counter = iter(range(10**9))
        results.append(summarize(
            "database insert (1 session record)",
            timed(lambda: db.insert_session(session(next(counter))), args.rows),
        ))
        results.append(summarize(
            f"database query: latest 20 of {args.rows} sessions",
            timed(lambda: db.fetch_sessions(20), 500),
        ))
        conn = sqlite3.connect(tmp / "db" / "bench.db")
        results.append(summarize(
            f"database query: all sessions of one branch",
            timed(lambda: conn.execute(
                "SELECT * FROM harvest_sessions WHERE branch_id = ?", ("T1-B1",)
            ).fetchall(), 500),
        ))
        conn.close()

    print("\nLaTeX table rows (median / p95, ms):")
    for r in results:
        print(f"{r['name']} & {r['median_ms']:.2f} & {r['p95_ms']:.2f} \\\\")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
