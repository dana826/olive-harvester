"""Application configuration: paths and the mock branch/tree map.

Everything hardware-related (real vs. simulated camera, sensors, actuator)
is decided in app/hardware/ — this file only defines *where things live*
and *what branches exist* for the operator to pick from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AppConfig:
    def __init__(self) -> None:
        self.data_dir = PROJECT_ROOT / "data"
        self.capture_dir = self.data_dir / "captures"
        self.db_path = self.data_dir / "db" / "olive_harvester.db"
        self.schema_path = PROJECT_ROOT / "app" / "storage" / "schema.sql"
        self.vibration_profiles_path = PROJECT_ROOT / "config" / "vibration_profiles.yaml"
        self.branches: List[Dict[str, str]] = _default_branches()


def _default_branches() -> List[Dict[str, str]]:
    """Mock tree/branch map the operator selects from.

    Stands in for a real orchard map (or a GPS/position picker) until this
    is wired to something real. Kept simple and static for the MVP.
    """

    branches = []
    for tree in range(1, 4):
        for branch in range(1, 5):
            branches.append(
                {
                    "id": f"T{tree}-B{branch}",
                    "label": f"Tree {tree} / Branch {branch}",
                }
            )
    return branches
