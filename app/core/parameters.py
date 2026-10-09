"""Harvesting parameter selection: maps a maturity class to a vibration
profile (frequency, amplitude, duration), loaded from
config/vibration_profiles.yaml so it can be tuned without touching code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

# Motor design range: 10-20 Hz (600-1200 rpm). Reference pulse: 15 Hz, 6 s.
MIN_FREQUENCY_HZ = 10.0
MAX_FREQUENCY_HZ = 20.0


def check_frequency(value: float, source: str = "frequency_hz") -> float:
    """Return value as float, or raise ValueError if outside the motor range."""
    value = float(value)
    if not MIN_FREQUENCY_HZ <= value <= MAX_FREQUENCY_HZ:
        raise ValueError(
            f"{source}={value:g} Hz is outside the motor range "
            f"{MIN_FREQUENCY_HZ:g}-{MAX_FREQUENCY_HZ:g} Hz."
        )
    return value


@dataclass
class HarvestParameters:
    frequency_hz: float
    amplitude_mm: float
    duration_s: float
    label: str
    advisory: Optional[str] = None


class ParameterSelector:
    def __init__(self, profiles_path: Path) -> None:
        with open(profiles_path, "r") as f:
            data = yaml.safe_load(f) or {}
        self._profiles = data.get("profiles", {})
        for name, profile in self._profiles.items():
            check_frequency(profile["frequency_hz"], f"profile '{name}'")

    def select(self, maturity_class: str) -> HarvestParameters:
        profile = self._profiles.get(maturity_class)

        if profile is None:
            # Unknown / low-confidence classification: fall back to the
            # most conservative profile and flag it for the operator.
            fallback = self._profiles.get("unripe", {})
            return HarvestParameters(
                frequency_hz=fallback.get("frequency_hz", MIN_FREQUENCY_HZ),
                amplitude_mm=fallback.get("amplitude_mm", 8),
                duration_s=fallback.get("duration_s", 6),
                label="Unknown",
                advisory="Maturity could not be confidently classified — using conservative parameters.",
            )

        return HarvestParameters(
            frequency_hz=profile["frequency_hz"],
            amplitude_mm=profile["amplitude_mm"],
            duration_s=profile["duration_s"],
            label=profile.get("label", maturity_class),
            advisory=profile.get("advisory"),
        )
