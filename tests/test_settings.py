from __future__ import annotations

import unittest
from pathlib import Path

from auto_auction.settings import AppConfig


class TestSettings(unittest.TestCase):
    def test_load_default_yaml(self) -> None:
        root = Path(__file__).resolve().parents[1]
        cfg = AppConfig.load(root / "config" / "default.yaml")
        self.assertEqual(cfg.scan.slot_count, 8)
        self.assertEqual(len(cfg.clicks.slots), 8)
        self.assertEqual(len(cfg.ocr_regions.slots), 8)
        self.assertGreater(cfg.scan.color_line_ratio, 0)


if __name__ == "__main__":
    unittest.main()
