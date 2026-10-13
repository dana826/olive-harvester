import sys
import time
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app import create_app  # noqa: E402
from app.config import AppConfig  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    """A Flask test client backed by an isolated tmp_path data dir, so
    tests never touch the real data/db/olive_harvester.db or
    data/captures/ used by `python run.py`."""

    config = AppConfig()
    config.data_dir = tmp_path
    config.capture_dir = tmp_path / "captures"
    config.db_path = tmp_path / "db" / "olive_harvester.db"

    app = create_app(config)
    app.testing = True
    with app.test_client() as test_client:
        yield test_client


def wait_until_not_harvesting(client, timeout_s: float = 6.0):
    """Poll /api/status until harvesting finishes (auto-complete) or the
    timeout elapses; returns the final status snapshot."""

    deadline = time.monotonic() + timeout_s
    snapshot = None
    while time.monotonic() < deadline:
        snapshot = client.get("/api/status").get_json()
        if snapshot["status"] != "harvesting":
            return snapshot
        time.sleep(0.15)
    return snapshot


@pytest.fixture()
def force_class(monkeypatch):
    """Make the simulated camera render a chosen maturity class, so tests do
    not depend on the camera's random choice."""
    import random

    def _force(maturity_class: str) -> None:
        monkeypatch.setattr(random, "choice", lambda seq: maturity_class)

    return _force


def wait_for_status(client, target: str, timeout_s: float = 4.0):
    """Poll /api/status until it equals `target` (or the timeout elapses)."""
    deadline = time.monotonic() + timeout_s
    snapshot = None
    while time.monotonic() < deadline:
        snapshot = client.get("/api/status").get_json()
        if snapshot["status"] == target:
            break
        time.sleep(0.1)
    return snapshot
