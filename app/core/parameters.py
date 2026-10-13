"""Harvesting parameter selection: maps a maturity class to a vibration
profile (frequency, amplitude, duration), loaded from
config/vibration_profiles.yaml so it can be tuned without touching code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

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
    # frequency/amplitude/duration are None for a class that is not
    # harvested automatically (unripe): no pulse is planned until the
    # operator confirms the override, whose values are in `override`.
    frequency_hz: Optional[float]
    amplitude_mm: Optional[float]
    duration_s: Optional[float]
    label: str
    advisory: Optional[str] = None
    harvestable: bool = True
    override: Optional[Dict[str, float]] = None


# Conservative pulse used when the maturity class cannot be determined.
FALLBACK_FREQUENCY_HZ = MIN_FREQUENCY_HZ
FALLBACK_AMPLITUDE_MM = 8.0
FALLBACK_DURATION_S = 6.0


class ParameterSelector:
    def __init__(self, profiles_path: Path) -> None:
        with open(profiles_path, "r") as f:
            data = yaml.safe_load(f) or {}
        self._profiles = data.get("profiles", {})
        for name, profile in self._profiles.items():
            if profile.get("harvestable", True):
                check_frequency(profile["frequency_hz"], f"profile '{name}'")
            else:
                check_frequency(profile["override"]["frequency_hz"], f"override of '{name}'")

    def select(self, maturity_class: str) -> HarvestParameters:
        profile = self._profiles.get(maturity_class)

        if profile is None:
            # Unknown / low-confidence classification: use a conservative
            # pulse and flag it for the operator.
            return HarvestParameters(
                frequency_hz=FALLBACK_FREQUENCY_HZ,
                amplitude_mm=FALLBACK_AMPLITUDE_MM,
                duration_s=FALLBACK_DURATION_S,
                label="Unknown",
                advisory="Maturity could not be confidently classified — using conservative parameters.",
            )

        if not profile.get("harvestable", True):
            return HarvestParameters(
                frequency_hz=None,
                amplitude_mm=None,
                duration_s=None,
                label=profile.get("label", maturity_class),
                advisory=profile.get("advisory"),
                harvestable=False,
                override=dict(profile["override"]),
            )

        return HarvestParameters(
            frequency_hz=profile["frequency_hz"],
            amplitude_mm=profile["amplitude_mm"],
            duration_s=profile["duration_s"],
            label=profile.get("label", maturity_class),
            advisory=profile.get("advisory"),
        )
