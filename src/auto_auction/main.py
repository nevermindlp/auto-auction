from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from auto_auction.settings import AppConfig


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto auction: fixed-ROI pet bargain scanner")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("config/default.yaml"),
        help="Path to YAML config",
    )
    p.add_argument("--dry-run", action="store_true", help="Log clicks only; no mouse")
    p.add_argument("--pick-roi", action="store_true", help="两点选 ROI 写回配置")
    p.add_argument(
        "--calibrate-point",
        action="store_true",
        help="单击标定一个点击点（配合 --key）",
    )
    p.add_argument(
        "--calibrate-rect",
        action="store_true",
        help="两点标定一个 OCR 矩形（配合 --key）",
    )
    p.add_argument(
        "--key",
        type=str,
        default=None,
        help="配置键，如 clicks.next_page 或 ocr_regions.detail.total_growth 或 clicks.slots.0",
    )
    p.add_argument(
        "--probe-ocr",
        action="store_true",
        help="对当前 ROI 跑全部 OCR 区并保存裁剪图",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    cfg_path = args.config.resolve()

    calib_flags = sum(
        bool(x) for x in (args.pick_roi, args.calibrate_point, args.calibrate_rect, args.probe_ocr)
    )
    if calib_flags > 1:
        print("标定相关参数请勿同时使用多个", file=sys.stderr)
        sys.exit(2)

    if args.calibrate_point or args.calibrate_rect:
        if not args.key:
            print("--calibrate-point / --calibrate-rect 需要 --key", file=sys.stderr)
            sys.exit(2)

    if args.pick_roi:
        if not cfg_path.is_file():
            print(f"Config not found: {cfg_path}", file=sys.stderr)
            sys.exit(1)
        from auto_auction.calibrate import run_pick_roi

        run_pick_roi(cfg_path)
        return

    if args.calibrate_point:
        from auto_auction.calibrate import run_calibrate_point

        run_calibrate_point(cfg_path, args.key)
        return

    if args.calibrate_rect:
        from auto_auction.calibrate import run_calibrate_rect

        run_calibrate_rect(cfg_path, args.key)
        return

    if not cfg_path.is_file():
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)

    config = AppConfig.load(cfg_path)
    config.resolve_paths(cfg_path)
    if args.dry_run:
        config.scan.dry_run = True

    logging.basicConfig(
        level=getattr(logging, config.logging.level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log = logging.getLogger(__name__)
    log.info(
        "platform=%s -> resolved=%s, click_backend=%s",
        config.platform,
        config.resolved_platform(),
        config.effective_click_backend(),
    )

    if args.probe_ocr:
        from auto_auction.calibrate import run_probe_ocr

        run_probe_ocr(config)
        return

    from auto_auction.state_machine import run_loop

    run_loop(config)


if __name__ == "__main__":
    main()
