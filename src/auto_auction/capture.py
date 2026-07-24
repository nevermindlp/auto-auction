from __future__ import annotations

import cv2
import mss
import numpy as np

from auto_auction.settings import AppConfig


def grab_roi_bgr(config: AppConfig) -> np.ndarray:
    """Capture the configured screen ROI as BGR uint8 (H x W x 3)."""
    roi = config.screen.roi
    if roi.width <= 0 or roi.height <= 0:
        raise ValueError("ROI width and height must be positive")

    box = {
        "left": int(roi.x),
        "top": int(roi.y),
        "width": int(roi.width),
        "height": int(roi.height),
    }
    with mss.mss() as sct:
        shot = np.array(sct.grab(box), dtype=np.uint8)
    if shot.size == 0:
        raise RuntimeError("Empty capture; check ROI and display")

    if shot.shape[2] == 4:
        return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)
    if shot.shape[2] == 3:
        return shot
    raise ValueError(f"Unexpected capture shape: {shot.shape}")
