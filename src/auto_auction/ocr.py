from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def parse_number(text: str) -> float | None:
    """Extract the first numeric token from OCR text. Returns None if none found."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s = s.replace("，", ",").replace(" ", "")
    m = _NUM_RE.search(s)
    if not m:
        return None
    token = m.group(0).replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def is_below_price(price: float, threshold: float) -> bool:
    return price < threshold


def is_color_line(current: float, total: float, ratio: float) -> bool:
    """Strict greater-than: current/total > ratio. Invalid totals → False."""
    if total <= 0:
        return False
    return (current / total) > ratio


@dataclass
class OcrReadResult:
    text: str
    value: float | None
    raw: object | None = None


class RapidOcrEngine:
    """Lazy RapidOCR wrapper; safe to construct even if unused in unit tests."""

    def __init__(self) -> None:
        self._engine = None

    def _ensure(self):
        if self._engine is None:
            from rapidocr import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def read_text(self, crop_bgr: np.ndarray) -> str:
        if crop_bgr is None or crop_bgr.size == 0:
            return ""
        # Upscale small crops for stabler digits
        h, w = crop_bgr.shape[:2]
        img = crop_bgr
        if max(h, w) < 64:
            scale = max(2, int(64 / max(h, w)))
            img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        engine = self._ensure()
        result = engine(rgb)
        if result is None:
            return ""
        # rapidocr>=3: RapidOCROutput with .txts; legacy: list of [box, text, score]
        txts = getattr(result, "txts", None)
        if txts:
            return "".join(str(t) for t in txts if t)
        if isinstance(result, (list, tuple)):
            parts: list[str] = []
            for item in result:
                if isinstance(item, (list, tuple)) and len(item) >= 2 and item[1]:
                    parts.append(str(item[1]))
            return "".join(parts)
        return ""

    def read_number(self, crop_bgr: np.ndarray) -> OcrReadResult:
        text = self.read_text(crop_bgr)
        return OcrReadResult(text=text, value=parse_number(text))
