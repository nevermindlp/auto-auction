from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

PlatformSetting = Literal["auto", "windows", "macos", "linux"]
ResolvedPlatform = Literal["windows", "macos", "linux"]
ClickBackend = Literal["pydirectinput", "pyautogui"]


def resolve_platform(platform: PlatformSetting) -> ResolvedPlatform:
    if platform == "auto":
        if sys.platform == "win32":
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        return "linux"
    return platform


def click_backend_for_platform(resolved: ResolvedPlatform) -> ClickBackend:
    return "pydirectinput" if resolved == "windows" else "pyautogui"


class Roi(BaseModel):
    x: int = 0
    y: int = 0
    width: int = 800
    height: int = 600


class Point(BaseModel):
    x: int
    y: int


class Rect(BaseModel):
    x: int
    y: int
    w: int
    h: int


class ScreenConfig(BaseModel):
    roi: Roi = Field(default_factory=Roi)


class ScanConfig(BaseModel):
    max_pages: int = Field(default=20, ge=1)
    price_threshold: float = Field(default=50000, ge=0)
    color_line_ratio: float = Field(default=0.98, gt=0, le=1.0)
    slot_count: int = Field(default=8, ge=1, le=32)
    after_click_sec: float = Field(default=0.6, ge=0)
    after_page_sec: float = Field(default=1.0, ge=0)
    loop_idle_sec: float = Field(default=0.05, ge=0)
    dry_run: bool = False
    save_debug: bool = True


class ClicksConfig(BaseModel):
    next_page: Point
    favorite: Point
    close_detail: Point
    slots: list[Point]


class SlotOcrRegions(BaseModel):
    price: Rect


class DetailOcrRegions(BaseModel):
    total_growth: Rect
    current_growth: Rect


class OcrRegionsConfig(BaseModel):
    slots: list[SlotOcrRegions]
    detail: DetailOcrRegions


class ClickScaleConfig(BaseModel):
    coordinate_scale_x: float = Field(default=1.0, gt=0)
    coordinate_scale_y: float = Field(default=1.0, gt=0)


class PathsConfig(BaseModel):
    debug_dir: str = "artifacts/debug"
    hits_dir: str = "artifacts/hits"


class LoggingConfig(BaseModel):
    level: str = "INFO"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    screen: ScreenConfig = Field(default_factory=ScreenConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    clicks: ClicksConfig
    ocr_regions: OcrRegionsConfig
    click: ClickScaleConfig = Field(default_factory=ClickScaleConfig)
    platform: PlatformSetting = "auto"
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @model_validator(mode="after")
    def _align_slot_counts(self) -> AppConfig:
        n = self.scan.slot_count
        if len(self.clicks.slots) != n:
            raise ValueError(f"clicks.slots length {len(self.clicks.slots)} != scan.slot_count {n}")
        if len(self.ocr_regions.slots) != n:
            raise ValueError(
                f"ocr_regions.slots length {len(self.ocr_regions.slots)} != scan.slot_count {n}"
            )
        return self

    @classmethod
    def load(cls, path: str | Path) -> AppConfig:
        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(raw)

    def resolve_paths(self, config_file: Path) -> None:
        base = config_file.parent.parent
        self.paths.debug_dir = str((base / self.paths.debug_dir).resolve())
        self.paths.hits_dir = str((base / self.paths.hits_dir).resolve())

    def resolved_platform(self) -> ResolvedPlatform:
        return resolve_platform(self.platform)

    def effective_click_backend(self) -> ClickBackend:
        return click_backend_for_platform(self.resolved_platform())
