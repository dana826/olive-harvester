"""Harvesting parameter selection: maps a maturity class to a vibration
profile (frequency, amplitude, duration), loaded from
config/vibration_profiles.yaml so it can be tuned without touching code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


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

    def select(self, maturity_class: str) -> HarvestParameters:
        profile = self._profiles.get(maturity_class)

        if profile is None:
            # Unknown / low-confidence classification: fall back to the
            # most conservative profile and flag it for the operator.
            fallback = self._profiles.get("unripe", {})
            return HarvestParameters(
                frequency_hz=fallback.get("frequency_hz", 40),
                amplitude_mm=fallback.get("amplitude_mm", 8),
                duration_s=fallback.get("duration_s", 3),
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
