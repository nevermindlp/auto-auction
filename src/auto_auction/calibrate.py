from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
from ruamel.yaml import YAML

from auto_auction.capture import grab_roi_bgr
from auto_auction.ocr import RapidOcrEngine
from auto_auction.regions import crop_bgr, scale_rect_to_frame
from auto_auction.settings import AppConfig

logger = logging.getLogger(__name__)


def corners_to_roi(
    top_left: tuple[int, int],
    bottom_right: tuple[int, int],
) -> tuple[int, int, int, int]:
    x1, y1 = top_left
    x2, y2 = bottom_right
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    w = right - left
    h = bottom - top
    if w < 2 or h < 2:
        raise ValueError("选区宽或高过小（<2px）")
    return int(left), int(top), int(w), int(h)


def wait_n_left_clicks(n: int) -> list[tuple[int, int]]:
    from pynput import mouse

    points: list[tuple[int, int]] = []

    def on_click(x: float, y: float, button: mouse.Button, pressed: bool) -> bool:
        if not pressed or button != mouse.Button.left:
            return True
        points.append((int(round(x)), int(round(y))))
        print(f"  已记录点 {len(points)}: ({points[-1][0]}, {points[-1][1]})")
        return len(points) < n

    print(f"请用鼠标左键依次点击 {n} 个点（完成后自动结束；Ctrl+C 取消）")
    sys.stdout.flush()
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
    if len(points) < n:
        raise RuntimeError(f"未收集到 {n} 个点击点")
    return points


def _load_ruamel(path: Path) -> tuple[YAML, Any]:
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml, yaml.load(path.read_text(encoding="utf-8")) or {}


def _dump_ruamel(yaml: YAML, path: Path, doc: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(doc, f)


def _set_nested(doc: Any, dotted_key: str, value: Any) -> None:
    """Set nested key like ``clicks.slots.0`` or ``ocr_regions.detail.total_growth``."""
    parts = dotted_key.split(".")
    cur: Any = doc
    for i, p in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if p.isdigit():
            idx = int(p)
            while len(cur) <= idx:
                cur.append({} if not nxt.isdigit() else [])
            cur = cur[idx]
            continue
        if p not in cur or cur[p] is None:
            cur[p] = [] if nxt.isdigit() else {}
        cur = cur[p]
    last = parts[-1]
    if last.isdigit():
        idx = int(last)
        while len(cur) <= idx:
            cur.append(None)
        cur[idx] = value
    else:
        cur[last] = value


def update_nested_mapping(config_path: Path, dotted_key: str, mapping: dict[str, int]) -> None:
    yaml, doc = _load_ruamel(config_path)
    _set_nested(doc, dotted_key, dict(mapping))
    _dump_ruamel(yaml, config_path, doc)
    print(f"已更新 {config_path} -> {dotted_key} = {mapping}")


def run_pick_roi(config_path: Path) -> None:
    p1, p2 = wait_n_left_clicks(2)
    x, y, w, h = corners_to_roi(p1, p2)
    update_nested_mapping(config_path, "screen.roi", {"x": x, "y": y, "width": w, "height": h})


def run_calibrate_point(config_path: Path, key: str) -> None:
    config = AppConfig.load(config_path)
    sx, sy = wait_n_left_clicks(1)[0]
    rel_x = int(sx - config.screen.roi.x)
    rel_y = int(sy - config.screen.roi.y)
    update_nested_mapping(config_path, key, {"x": rel_x, "y": rel_y})


def run_calibrate_rect(config_path: Path, key: str) -> None:
    config = AppConfig.load(config_path)
    p1, p2 = wait_n_left_clicks(2)
    x, y, w, h = corners_to_roi(p1, p2)
    rel = {
        "x": int(x - config.screen.roi.x),
        "y": int(y - config.screen.roi.y),
        "w": int(w),
        "h": int(h),
    }
    update_nested_mapping(config_path, key, rel)


def run_probe_ocr(config: AppConfig, output_dir: Path | None = None) -> None:
    out = Path(output_dir or config.paths.debug_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    frame = grab_roi_bgr(config)
    fh, fw = frame.shape[:2]
    engine = RapidOcrEngine()

    for i, slot in enumerate(config.ocr_regions.slots):
        rect = scale_rect_to_frame(slot.price, config, fw, fh)
        crop = crop_bgr(frame, rect)
        path = out / f"probe_{stamp}_slot{i}_price.png"
        cv2.imwrite(str(path), crop)
        read = engine.read_number(crop)
        line = f"slot[{i}].price text={read.text!r} value={read.value} -> {path.name}"
        print(line)
        logger.info(line)

    for name, rect_cfg in (
        ("total_growth", config.ocr_regions.detail.total_growth),
        ("current_growth", config.ocr_regions.detail.current_growth),
    ):
        rect = scale_rect_to_frame(rect_cfg, config, fw, fh)
        crop = crop_bgr(frame, rect)
        path = out / f"probe_{stamp}_detail_{name}.png"
        cv2.imwrite(str(path), crop)
        read = engine.read_number(crop)
        line = f"detail.{name} text={read.text!r} value={read.value} -> {path.name}"
        print(line)
        logger.info(line)

    print(f"probe-ocr 完成，输出目录: {out}")
