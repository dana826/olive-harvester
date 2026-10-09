"""Simulated sensor array: vibration feedback, motor current draw, and
mass gained per tick (standing in for an HX711 load cell).

read() is called once per controller tick (see
app/core/harvest_controller.py) and returns plausible idle or
active-harvesting readings. A real backend (accelerometer + current-sense
+ HX711 over GPIO) will implement the same read(harvesting, active_params)
-> SensorReading shape.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SensorReading:
    vibration_hz: float
    motor_current_a: float
    mass_delta_g: float


class MockSensorArray:
    def read(
        self, harvesting: bool, active_params: Optional[Dict[str, Any]]
    ) -> SensorReading:
        if not harvesting or not active_params:
            # Idle: small sensor noise, no motor current, nothing falling.
            vibration = round(random.uniform(0.0, 0.4), 2)
            current = round(random.uniform(0.12, 0.20), 2)
            return SensorReading(vibration_hz=vibration, motor_current_a=current, mass_delta_g=0.0)

        target_hz = float(active_params.get("frequency_hz", 15))
        vibration = round(target_hz + random.uniform(-1.5, 1.5), 2)
        current = round(1.1 + random.uniform(-0.15, 0.2), 2)
        # ~75% of ticks register olives falling into the collection tray.
        mass_delta = round(random.uniform(1.5, 9.0), 2) if random.random() < 0.75 else 0.0

        return SensorReading(vibration_hz=vibration, motor_current_a=current, mass_delta_g=mass_delta)
