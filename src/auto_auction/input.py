from __future__ import annotations

import logging
import time

from auto_auction.settings import AppConfig, ClickBackend

logger = logging.getLogger(__name__)


def screen_coords_for_backend(config: AppConfig, x: int, y: int) -> tuple[int, int]:
    sx = float(config.click.coordinate_scale_x)
    sy = float(config.click.coordinate_scale_y)
    return int(round(x * sx)), int(round(y * sy))


def roi_rel_to_screen(config: AppConfig, rel_x: int, rel_y: int) -> tuple[int, int]:
    """Map ROI-relative point to absolute screen (pipeline) pixels."""
    frame_scale_x = 1.0
    frame_scale_y = 1.0
    # Callers that have a live frame may pass scaled coords separately; default 1:1 with config ROI.
    abs_x = int(round(config.screen.roi.x + rel_x * frame_scale_x))
    abs_y = int(round(config.screen.roi.y + rel_y * frame_scale_y))
    return abs_x, abs_y


def roi_rel_to_screen_with_frame(
    config: AppConfig,
    rel_x: int,
    rel_y: int,
    frame_w: int,
    frame_h: int,
) -> tuple[int, int]:
    """Map ROI-relative coords (in config ROI units) using actual capture size."""
    roi = config.screen.roi
    sx = (frame_w / roi.width) if roi.width else 1.0
    sy = (frame_h / roi.height) if roi.height else 1.0
    abs_x = int(round(roi.x + rel_x * sx))
    abs_y = int(round(roi.y + rel_y * sy))
    return abs_x, abs_y


def click_screen(
    config: AppConfig,
    x: int,
    y: int,
    *,
    delay_after: float | None = None,
) -> None:
    x, y = screen_coords_for_backend(config, x, y)
    d = delay_after if delay_after is not None else config.scan.after_click_sec
    if config.scan.dry_run:
        logger.info("dry_run: click at (%s, %s)", x, y)
        time.sleep(min(d, 0.05))
        return

    backend: ClickBackend = config.effective_click_backend()
    if backend == "pydirectinput":
        import pydirectinput

        pydirectinput.moveTo(x, y)
        time.sleep(0.02)
        pydirectinput.click(x, y)
    elif backend == "pyautogui":
        import pyautogui

        pyautogui.click(x, y)
    else:
        raise ValueError(f"Unknown input backend: {backend}")

    time.sleep(d)


def click_roi_rel(
    config: AppConfig,
    rel_x: int,
    rel_y: int,
    *,
    frame_w: int | None = None,
    frame_h: int | None = None,
    delay_after: float | None = None,
) -> None:
    if frame_w is not None and frame_h is not None:
        ax, ay = roi_rel_to_screen_with_frame(config, rel_x, rel_y, frame_w, frame_h)
    else:
        ax, ay = roi_rel_to_screen(config, rel_x, rel_y)
    click_screen(config, ax, ay, delay_after=delay_after)
