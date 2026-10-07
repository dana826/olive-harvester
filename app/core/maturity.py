"""Olive maturity detection.

This is a genuine (if simple) color-based classifier, not a random
number generator standing in for one: it loads the JPEG MockCamera saved,
masks out background/branch pixels, measures the mean color of what's
left, and picks the nearest of four reference maturity colors. It never
reads MockCamera's hidden "ground truth" hint. When a real camera and/or
a trained model are available, MaturityDetector.detect() is the one
method to replace — ParameterSelector and HarvestController only depend
on the MaturityResult shape returned here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image

from ..hardware.camera import BACKGROUND_COLOR, BRANCH_COLOR, CLASS_COLORS


@dataclass
class MaturityResult:
    maturity_class: str
    confidence: float
    mean_color: Tuple[int, int, int]


class MaturityDetector:
    _BG_THRESHOLD = 35
    _BRANCH_THRESHOLD = 30
    _MIN_CONFIDENCE = 0.3
    _MAX_CONFIDENCE = 0.99

    def detect(self, image_path: Path) -> MaturityResult:
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((200, 150))
        pixels = np.asarray(image, dtype=np.int16).reshape(-1, 3)

        bg_dist = np.linalg.norm(pixels - np.array(BACKGROUND_COLOR), axis=1)
        branch_dist = np.linalg.norm(pixels - np.array(BRANCH_COLOR), axis=1)
        mask = (bg_dist > self._BG_THRESHOLD) & (branch_dist > self._BRANCH_THRESHOLD)

        olive_pixels = pixels[mask]
        if olive_pixels.size == 0:
            return MaturityResult("unknown", 0.0, (0, 0, 0))

        mean_color = olive_pixels.mean(axis=0)

        distances = {
            cls: float(np.linalg.norm(mean_color - np.array(color)))
            for cls, color in CLASS_COLORS.items()
        }
        best_class = min(distances, key=distances.get)
        sorted_distances = sorted(distances.values())
        best, second = sorted_distances[0], sorted_distances[1]
        confidence = 1.0 - (best / (best + second)) if (best + second) > 0 else 1.0
        confidence = max(self._MIN_CONFIDENCE, min(self._MAX_CONFIDENCE, confidence))

        return MaturityResult(
            maturity_class=best_class,
            confidence=confidence,
            mean_color=tuple(int(c) for c in mean_color),
        )
