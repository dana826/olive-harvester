"""HarvestController: the state machine that ties camera, maturity
detection, parameter selection, the actuator, sensors, and storage
together, and that app/api/routes.py drives.

State flow:
    IDLE -> READY (branch selected) -> ASSESSED (captured + maturity known)
         -> HARVESTING -> (auto-complete or operator stop) -> READY

A background thread ticks every TICK_INTERVAL_S to: poll simulated
sensors, accumulate harvested mass while harvesting, advance the elapsed
timer, auto-stop when the target duration is reached, and occasionally
raise a simulated fault alert — exactly the responsibilities Module 6
(Monitoring) owns, pulled forward here so the dashboard has live data.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..hardware.actuator import MockActuator
from ..hardware.camera import MockCamera
from ..hardware.sensors import MockSensorArray
from .maturity import MaturityDetector
from .parameters import ParameterSelector, check_frequency


class SystemStatus(str, Enum):
    IDLE = "idle"
    READY = "ready"
    ASSESSED = "assessed"
    HARVESTING = "harvesting"


@dataclass
class AlertRecord:
    id: int
    severity: str  # info | warning | critical
    code: str
    message: str
    raised_at: str
    resolved: bool = False
    resolved_at: Optional[str] = None


class HarvestController:
    TICK_INTERVAL_S = 0.5
    JAM_CHANCE_PER_TICK = 0.01

    def __init__(
        self,
        capture_dir: Path,
        profiles_path: Path,
        db,
        branches: List[Dict[str, str]],
    ) -> None:
        self._camera = MockCamera(capture_dir)
        self._detector = MaturityDetector()
        self._params = ParameterSelector(profiles_path)
        self._actuator = MockActuator()
        self._sensors = MockSensorArray()
        self._db = db
        self._branches = branches

        self._lock = threading.RLock()
        self._status = SystemStatus.IDLE
        self._current_branch: Optional[str] = None
        self._current_capture: Optional[Dict[str, Any]] = None
        self._recommended_params: Optional[Dict[str, Any]] = None
        self._active_params: Optional[Dict[str, Any]] = None
        self._harvest_started_at: Optional[float] = None
        self._elapsed_s: float = 0.0
        self._mass_g: float = 0.0
        self._jam_raised_this_session = False
        self._sensor_reading = {"vibration_hz": 0.0, "motor_current_a": 0.15}
        self._alerts: List[AlertRecord] = []
        self._next_alert_id = 1
        self._last_session: Optional[Dict[str, Any]] = None

        self._stop_flag = threading.Event()
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ #
    # Public API — called from app/api/routes.py
    # ------------------------------------------------------------------ #

    def list_branches(self) -> List[Dict[str, str]]:
        return self._branches

    def select_branch(self, branch_id: str) -> Dict[str, Any]:
        with self._lock:
            if branch_id not in {b["id"] for b in self._branches}:
                raise ValueError(f"Unknown branch: {branch_id!r}")
            if self._status == SystemStatus.HARVESTING:
                raise RuntimeError("Cannot change branch while harvesting is in progress.")

            self._current_branch = branch_id
            self._current_capture = None
            self._recommended_params = None
            self._active_params = None
            self._status = SystemStatus.READY

        return self.snapshot()

    def capture_and_assess(self) -> Dict[str, Any]:
        with self._lock:
            if self._current_branch is None:
                raise RuntimeError("Select a branch before capturing an image.")
            if self._status == SystemStatus.HARVESTING:
                raise RuntimeError("Cannot capture while harvesting is in progress.")

        # Deliberately done outside the lock: the (simulated) capture +
        # detection work takes real time and touches no shared state.
        capture = self._camera.capture()
        maturity = self._detector.detect(capture.image_path)
        params = self._params.select(maturity.maturity_class)

        with self._lock:
            self._current_capture = {
                "image_url": f"/api/captures/{capture.image_path.name}",
                "captured_at": capture.timestamp.isoformat(),
            }
            self._recommended_params = {
                "maturity_class": maturity.maturity_class,
                "confidence": round(maturity.confidence, 3),
                "frequency_hz": params.frequency_hz,
                "amplitude_mm": params.amplitude_mm,
                "duration_s": params.duration_s,
                "label": params.label,
                "advisory": params.advisory,
            }
            self._active_params = dict(self._recommended_params)
            self._status = SystemStatus.ASSESSED
            if params.advisory:
                self._raise_alert("warning", "LOW_MATURITY", params.advisory)

        return self.snapshot()

    def start_harvest(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            if self._status != SystemStatus.ASSESSED:
                raise RuntimeError("Capture and assess a branch before starting harvest.")

            active = dict(self._active_params)
            has_override = False
            if overrides:
                for key in ("frequency_hz", "amplitude_mm", "duration_s"):
                    value = overrides.get(key)
                    if value is not None:
                        if key == "frequency_hz":
                            check_frequency(value, "override")
                        active[key] = float(value)
                        has_override = True
            active["operator_override"] = has_override
            self._active_params = active

            self._actuator.start(active)
            self._harvest_started_at = time.monotonic()
            self._elapsed_s = 0.0
            self._mass_g = 0.0
            self._jam_raised_this_session = False
            self._status = SystemStatus.HARVESTING

        return self.snapshot()

    def stop_harvest(self) -> Dict[str, Any]:
        with self._lock:
            if self._status == SystemStatus.HARVESTING:
                self._finish_harvest("stopped")
        return self.snapshot()

    def resolve_alert(self, alert_id: int) -> Dict[str, Any]:
        with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now().isoformat()
        return self.snapshot()

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._db.fetch_sessions(limit)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": self._status.value,
                "current_branch": self._current_branch,
                "capture": self._current_capture,
                "parameters": self._active_params,
                "recommended_parameters": self._recommended_params,
                "sensors": dict(self._sensor_reading),
                "harvested_mass_g": round(self._mass_g, 1),
                "elapsed_s": round(self._elapsed_s, 1),
                "target_duration_s": (self._active_params or {}).get("duration_s"),
                "alerts": [asdict(a) for a in self._alerts],
                "last_session": self._last_session,
                "timestamp": datetime.now().isoformat(),
            }

    # ------------------------------------------------------------------ #
    # Internal — caller must hold self._lock unless noted
    # ------------------------------------------------------------------ #

    def _raise_alert(self, severity: str, code: str, message: str) -> None:
        raised_at = datetime.now().isoformat()
        alert = AlertRecord(
            id=self._next_alert_id,
            severity=severity,
            code=code,
            message=message,
            raised_at=raised_at,
        )
        self._next_alert_id += 1
        self._alerts.insert(0, alert)
        self._alerts = self._alerts[:50]
        self._db.log_alert(severity, code, message, raised_at)

    def _finish_harvest(self, reason: str) -> None:
        self._actuator.stop()
        duration_actual = round(self._elapsed_s, 1)

        session = {
            "branch_id": self._current_branch,
            "maturity_class": self._active_params.get("maturity_class"),
            "confidence": self._active_params.get("confidence"),
            "frequency_hz": self._active_params.get("frequency_hz"),
            "amplitude_mm": self._active_params.get("amplitude_mm"),
            "duration_target_s": self._active_params.get("duration_s"),
            "duration_actual_s": duration_actual,
            "harvested_mass_g": round(self._mass_g, 1),
            "status": "completed" if reason == "auto_complete" else "stopped",
            "operator_override": self._active_params.get("operator_override", False),
            "image_url": (self._current_capture or {}).get("image_url"),
            "ended_at": datetime.now().isoformat(),
        }
        session_id = self._db.insert_session(session)
        session["id"] = session_id
        self._last_session = session

        self._raise_alert(
            "info",
            "HARVEST_COMPLETE",
            f"Harvest {'completed' if reason == 'auto_complete' else 'stopped'} — "
            f"{session['harvested_mass_g']} g collected in {duration_actual}s.",
        )

        self._status = SystemStatus.READY
        self._harvest_started_at = None
        # Reset immediately (not just at the next start_harvest) so the
        # dashboard's progress bar doesn't show the previous session's
        # elapsed time next to the newly-assessed branch's target duration.
        self._elapsed_s = 0.0

    def _tick_loop(self) -> None:
        while not self._stop_flag.is_set():
            time.sleep(self.TICK_INTERVAL_S)
            with self._lock:
                harvesting = self._status == SystemStatus.HARVESTING
                if harvesting and self._harvest_started_at is not None:
                    self._elapsed_s = time.monotonic() - self._harvest_started_at

                reading = self._sensors.read(harvesting, self._active_params)
                self._sensor_reading = {
                    "vibration_hz": reading.vibration_hz,
                    "motor_current_a": reading.motor_current_a,
                }

                if harvesting:
                    self._mass_g += reading.mass_delta_g

                    if (
                        not self._jam_raised_this_session
                        and self._elapsed_s > 1.5
                        and random.random() < self.JAM_CHANCE_PER_TICK
                    ):
                        self._jam_raised_this_session = True
                        self._raise_alert(
                            "critical",
                            "POSSIBLE_JAM",
                            "Vibration feedback abnormal — possible branch jam detected.",
                        )

                    target = (self._active_params or {}).get("duration_s", 0)
                    if self._elapsed_s >= target:
                        self._finish_harvest("auto_complete")
