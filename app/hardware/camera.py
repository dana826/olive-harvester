"""Simulated Raspberry Pi Camera Module 3.

MockCamera.capture() generates a synthetic branch photo (background +
branch line + a cluster of "olives" in one randomly-chosen dominant
maturity color) and saves it as a JPEG, exactly like a real capture would.
The maturity_class_hint on the result is the simulated ground truth used
only to render the scene — app/core/maturity.py never reads it; it
re-derives the maturity class from the saved pixels, just like it will
have to on a real photo. This keeps the simulation honest: the detector
is doing real (if simple) image analysis, not being told the answer.

When the real camera is wired up, a PiCameraModule3 class implementing
the same capture() -> CaptureResult shape (via picamera2) drops in here
without any change to app/core/ or app/api/.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

# Approximate dominant RGB color used to render olives of each maturity
# class. Shared with app/core/maturity.py, which classifies a captured
# image by comparing its measured olive-pixel color against these same
# reference colors — this is the one place the "simulated scene" and the
# "detector" intentionally share knowledge (real reference colors would
# play the same role once a real camera is in use).
CLASS_COLORS = {
    "unripe": (60, 140, 50),      # green
    "turning": (150, 140, 60),    # yellow-green
    "semi_ripe": (140, 70, 55),   # reddish-purple
    "ripe": (35, 25, 25),         # near-black
}
BACKGROUND_COLOR = (235, 235, 230)
BRANCH_COLOR = (101, 67, 33)


@dataclass
class CaptureResult:
    image_path: Path
    timestamp: datetime
    width: int
    height: int
    maturity_class_hint: str  # simulation-only ground truth, for tests/debugging


class MockCamera:
    """Simulated camera backend. Same capture_dir/resolution shape a real
    picamera2-backed class will use."""

    def __init__(self, capture_dir: Path, resolution=(640, 480)) -> None:
        self._capture_dir = Path(capture_dir)
        self._capture_dir.mkdir(parents=True, exist_ok=True)
        self._resolution = resolution

    def capture(self) -> CaptureResult:
        time.sleep(0.3)  # simulate sensor + I/O latency of a real capture

        true_class = random.choice(list(CLASS_COLORS.keys()))
        image = self._render_branch(true_class)

        timestamp = datetime.now()
        filename = f"capture_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        path = self._capture_dir / filename
        image.save(path, quality=90)

        width, height = self._resolution
        return CaptureResult(
            image_path=path,
            timestamp=timestamp,
            width=width,
            height=height,
            maturity_class_hint=true_class,
        )

    def _render_branch(self, true_class: str) -> Image.Image:
        width, height = self._resolution
        image = Image.new("RGB", (width, height), color=BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)

        draw.line([(20, height // 2), (width - 20, height // 2)], fill=BRANCH_COLOR, width=6)

        base_color = CLASS_COLORS[true_class]
        radius = max(14, width // 22)
        count = random.randint(7, 10)

        for i in range(count):
            cx = int(width * (i + 1) / (count + 1)) + random.randint(-10, 10)
            cy = height // 2 + random.randint(-radius, radius)
            color = tuple(
                max(0, min(255, channel + random.randint(-18, 18))) for channel in base_color
            )
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=color,
                outline=(20, 20, 20),
            )

        return image
