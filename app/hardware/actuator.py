"""Simulated vibration/harvesting actuator driver.

Timing (how long harvesting runs) is owned by HarvestController, not this
class — this mirrors how the real driver will work too: it just turns the
motor on with a set of parameters and off again, on command. A real
gpiozero-backed driver will implement the same start(params)/stop()/
is_running shape.
"""

from __future__ import annotations

from typing import Any, Dict


class MockActuator:
    def __init__(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, params: Dict[str, Any]) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
