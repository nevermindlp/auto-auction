from __future__ import annotations

import numpy as np

from auto_auction.settings import AppConfig, Rect


def scale_rect_to_frame(rect: Rect, config: AppConfig, frame_w: int, frame_h: int) -> Rect:
    """Scale a config-ROI-relative rect onto the actual capture pixel grid."""
    roi = config.screen.roi
    sx = (frame_w / roi.width) if roi.width else 1.0
    sy = (frame_h / roi.height) if roi.height else 1.0
    return Rect(
        x=int(round(rect.x * sx)),
        y=int(round(rect.y * sy)),
        w=max(1, int(round(rect.w * sx))),
        h=max(1, int(round(rect.h * sy))),
    )


def crop_bgr(frame: np.ndarray, rect: Rect) -> np.ndarray:
    h, w = frame.shape[:2]
    x1 = max(0, min(w, rect.x))
    y1 = max(0, min(h, rect.y))
    x2 = max(0, min(w, rect.x + rect.w))
    y2 = max(0, min(h, rect.y + rect.h))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid crop rect {rect} for frame {w}x{h}")
    return frame[y1:y2, x1:x2].copy()


def slot_price_rect(config: AppConfig, slot_index: int, frame_w: int, frame_h: int) -> Rect:
    return scale_rect_to_frame(config.ocr_regions.slots[slot_index].price, config, frame_w, frame_h)


def detail_total_rect(config: AppConfig, frame_w: int, frame_h: int) -> Rect:
    return scale_rect_to_frame(config.ocr_regions.detail.total_growth, config, frame_w, frame_h)


def detail_current_rect(config: AppConfig, frame_w: int, frame_h: int) -> Rect:
    return scale_rect_to_frame(config.ocr_regions.detail.current_growth, config, frame_w, frame_h)
