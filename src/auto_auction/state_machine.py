from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

import cv2

from auto_auction.capture import grab_roi_bgr
from auto_auction.input import click_roi_rel
from auto_auction.ocr import RapidOcrEngine, is_below_price, is_color_line
from auto_auction.regions import (
    crop_bgr,
    detail_current_rect,
    detail_total_rect,
    slot_price_rect,
)
from auto_auction.settings import AppConfig

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE = auto()
    READ_PAGE = auto()
    OPEN_DETAIL = auto()
    CHECK_GROWTH = auto()
    FAVORITE = auto()
    CLOSE_DETAIL = auto()
    NEXT_PAGE = auto()
    DONE = auto()


def should_open_detail(price: float | None, threshold: float) -> bool:
    if price is None:
        return False
    return is_below_price(price, threshold)


def pages_exhausted(page_index: int, max_pages: int) -> bool:
    """page_index is 0-based count of pages already fully processed."""
    return page_index >= max_pages


def run_loop(config: AppConfig) -> None:
    Path(config.paths.debug_dir).mkdir(parents=True, exist_ok=True)
    Path(config.paths.hits_dir).mkdir(parents=True, exist_ok=True)

    automation_running = threading.Event()
    stop_program = threading.Event()
    state_holder: list[State] = [State.IDLE]
    ctx: dict[str, Any] = {
        "page_index": 0,
        "slot_index": 0,
        "engine": RapidOcrEngine(),
        "pending_close": False,
    }

    def worker() -> None:
        state = state_holder[0]
        while not stop_program.is_set():
            if not automation_running.is_set():
                time.sleep(config.scan.loop_idle_sec)
                continue
            prev = state
            state = _step(state, config, ctx, stop_program, automation_running)
            if state != prev:
                logger.info("状态切换: %s -> %s", prev.name, state.name)
            state_holder[0] = state
            if state == State.DONE:
                automation_running.clear()
                logger.info("扫描完成 (DONE)。可 quit 退出，或修改配置后重新 start。")
                state = State.IDLE
                state_holder[0] = state
                ctx["page_index"] = 0
                ctx["slot_index"] = 0
            time.sleep(config.scan.loop_idle_sec)

    t = threading.Thread(target=worker, name="auto-auction-loop", daemon=True)
    t.start()
    _run_cli(automation_running, stop_program, state_holder, ctx)
    logger.info("Exiting.")


def _interruptible_sleep(
    seconds: float,
    stop_program: threading.Event,
    automation_running: threading.Event,
) -> None:
    end = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < end:
        if stop_program.is_set() or not automation_running.is_set():
            return
        time.sleep(min(0.05, end - time.monotonic()))


def _save_debug(config: AppConfig, crop, tag: str) -> None:
    if not config.scan.save_debug:
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = Path(config.paths.debug_dir) / f"{tag}_{stamp}.png"
    cv2.imwrite(str(path), crop)
    logger.info("debug saved: %s", path)


def _step(
    state: State,
    config: AppConfig,
    ctx: dict[str, Any],
    stop_program: threading.Event,
    automation_running: threading.Event,
) -> State:
    if stop_program.is_set() or not automation_running.is_set():
        if ctx.get("pending_close"):
            try:
                _close_detail(config, ctx)
            except Exception:
                logger.exception("stop: close detail failed")
            ctx["pending_close"] = False
        return state if state != State.IDLE else State.IDLE

    if state == State.IDLE:
        ctx["page_index"] = 0
        ctx["slot_index"] = 0
        return State.READ_PAGE

    if state == State.READ_PAGE:
        return _read_page(config, ctx, stop_program, automation_running)

    if state == State.OPEN_DETAIL:
        return _open_detail(config, ctx, stop_program, automation_running)

    if state == State.CHECK_GROWTH:
        return _check_growth(config, ctx)

    if state == State.FAVORITE:
        return _favorite(config, ctx, stop_program, automation_running)

    if state == State.CLOSE_DETAIL:
        return _close_and_advance(config, ctx, stop_program, automation_running)

    if state == State.NEXT_PAGE:
        return _next_page(config, ctx, stop_program, automation_running)

    return state


def _read_page(
    config: AppConfig,
    ctx: dict[str, Any],
    stop_program: threading.Event,
    automation_running: threading.Event,
) -> State:
    slot = int(ctx["slot_index"])
    n = config.scan.slot_count
    if slot >= n:
        return State.NEXT_PAGE

    frame = grab_roi_bgr(config)
    fh, fw = frame.shape[:2]
    engine: RapidOcrEngine = ctx["engine"]
    rect = slot_price_rect(config, slot, fw, fh)
    crop = crop_bgr(frame, rect)
    read = engine.read_number(crop)
    page = int(ctx["page_index"])
    logger.info(
        "[READ_PAGE] page=%s slot=%s price_text=%r value=%s",
        page,
        slot,
        read.text,
        read.value,
    )

    if read.value is None:
        _save_debug(config, crop, f"price_fail_p{page}_s{slot}")
        ctx["slot_index"] = slot + 1
        return State.READ_PAGE

    if not should_open_detail(read.value, config.scan.price_threshold):
        logger.info(
            "[READ_PAGE] skip slot=%s price=%s >= threshold=%s",
            slot,
            read.value,
            config.scan.price_threshold,
        )
        ctx["slot_index"] = slot + 1
        return State.READ_PAGE

    ctx["last_price"] = read.value
    ctx["frame_wh"] = (fw, fh)
    return State.OPEN_DETAIL


def _open_detail(
    config: AppConfig,
    ctx: dict[str, Any],
    stop_program: threading.Event,
    automation_running: threading.Event,
) -> State:
    slot = int(ctx["slot_index"])
    pt = config.clicks.slots[slot]
    fw, fh = ctx.get("frame_wh", (config.screen.roi.width, config.screen.roi.height))
    click_roi_rel(config, pt.x, pt.y, frame_w=fw, frame_h=fh, delay_after=0)
    ctx["pending_close"] = True
    _interruptible_sleep(config.scan.after_click_sec, stop_program, automation_running)
    return State.CHECK_GROWTH


def _check_growth(config: AppConfig, ctx: dict[str, Any]) -> State:
    frame = grab_roi_bgr(config)
    fh, fw = frame.shape[:2]
    engine: RapidOcrEngine = ctx["engine"]
    total_crop = crop_bgr(frame, detail_total_rect(config, fw, fh))
    cur_crop = crop_bgr(frame, detail_current_rect(config, fw, fh))
    total = engine.read_number(total_crop)
    current = engine.read_number(cur_crop)
    logger.info(
        "[CHECK_GROWTH] total=%r/%s current=%r/%s",
        total.text,
        total.value,
        current.text,
        current.value,
    )
    if total.value is None or current.value is None:
        _save_debug(config, total_crop, "growth_total_fail")
        _save_debug(config, cur_crop, "growth_current_fail")
        return State.CLOSE_DETAIL

    ctx["last_total"] = total.value
    ctx["last_current"] = current.value
    if is_color_line(current.value, total.value, config.scan.color_line_ratio):
        ctx["last_frame"] = frame
        return State.FAVORITE
    return State.CLOSE_DETAIL


def _favorite(
    config: AppConfig,
    ctx: dict[str, Any],
    stop_program: threading.Event,
    automation_running: threading.Event,
) -> State:
    pt = config.clicks.favorite
    fw, fh = ctx.get("frame_wh", (config.screen.roi.width, config.screen.roi.height))
    click_roi_rel(config, pt.x, pt.y, frame_w=fw, frame_h=fh, delay_after=0)
    _interruptible_sleep(config.scan.after_click_sec, stop_program, automation_running)

    total = float(ctx.get("last_total", 0))
    current = float(ctx.get("last_current", 0))
    ratio = (current / total) if total else 0.0
    page = int(ctx["page_index"])
    slot = int(ctx["slot_index"])
    price = ctx.get("last_price")
    logger.info(
        "HIT color-line page=%s slot=%s price=%s total=%s current=%s ratio=%.4f",
        page,
        slot,
        price,
        total,
        current,
        ratio,
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    frame = ctx.get("last_frame")
    if frame is not None:
        path = Path(config.paths.hits_dir) / f"hit_p{page}_s{slot}_{stamp}.png"
        cv2.imwrite(str(path), frame)
        logger.info("hit screenshot: %s", path)
    return State.CLOSE_DETAIL


def _close_detail(config: AppConfig, ctx: dict[str, Any]) -> None:
    pt = config.clicks.close_detail
    fw, fh = ctx.get("frame_wh", (config.screen.roi.width, config.screen.roi.height))
    click_roi_rel(config, pt.x, pt.y, frame_w=fw, frame_h=fh, delay_after=0)


def _close_and_advance(
    config: AppConfig,
    ctx: dict[str, Any],
    stop_program: threading.Event,
    automation_running: threading.Event,
) -> State:
    _close_detail(config, ctx)
    ctx["pending_close"] = False
    _interruptible_sleep(config.scan.after_click_sec, stop_program, automation_running)
    ctx["slot_index"] = int(ctx["slot_index"]) + 1
    return State.READ_PAGE


def _next_page(
    config: AppConfig,
    ctx: dict[str, Any],
    stop_program: threading.Event,
    automation_running: threading.Event,
) -> State:
    page = int(ctx["page_index"]) + 1
    ctx["page_index"] = page
    if pages_exhausted(page, config.scan.max_pages):
        logger.info("[NEXT_PAGE] reached max_pages=%s -> DONE", config.scan.max_pages)
        return State.DONE
    pt = config.clicks.next_page
    fw, fh = ctx.get("frame_wh", (config.screen.roi.width, config.screen.roi.height))
    click_roi_rel(config, pt.x, pt.y, frame_w=fw, frame_h=fh, delay_after=0)
    logger.info("[NEXT_PAGE] clicked next, now page_index=%s", page)
    _interruptible_sleep(config.scan.after_page_sec, stop_program, automation_running)
    ctx["slot_index"] = 0
    return State.READ_PAGE


def _run_cli(
    automation_running: threading.Event,
    stop_program: threading.Event,
    state_holder: list[State],
    ctx: dict[str, Any],
) -> None:
    start_cmds = frozenset({"start", "s", "begin", "开始"})
    stop_cmds = frozenset({"stop", "pause", "p", "暂停"})
    status_cmds = frozenset({"status", "状态"})
    help_cmds = frozenset({"help", "h", "?", "帮助"})
    quit_cmds = frozenset({"quit", "exit", "q", "退出"})
    help_text = (
        "  start / 开始  — 启动或继续扫描\n"
        "  stop / 暂停   — 暂停（尽量先关详情）\n"
        "  status / 状态 — 当前状态与页/槽\n"
        "  help / 帮助\n"
        "  quit / 退出"
    )
    print("auto-auction 已启动。输入 help 查看命令。")
    print(help_text)
    while not stop_program.is_set():
        try:
            raw = input("auto-auction> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            stop_program.set()
            break
        if not raw:
            continue
        cmd = raw.lower()
        if cmd in start_cmds:
            automation_running.set()
            print(f"已启动。当前状态: {state_holder[0].name}")
        elif cmd in stop_cmds:
            automation_running.clear()
            print(f"已暂停。当前状态: {state_holder[0].name}")
        elif cmd in status_cmds:
            print(
                f"running={automation_running.is_set()} state={state_holder[0].name} "
                f"page={ctx.get('page_index')} slot={ctx.get('slot_index')}"
            )
        elif cmd in help_cmds:
            print(help_text)
        elif cmd in quit_cmds:
            stop_program.set()
            break
        else:
            print("未知命令。输入 help 查看。")
