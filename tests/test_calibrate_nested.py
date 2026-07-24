from __future__ import annotations

import unittest

from auto_auction.calibrate import _set_nested


class TestYamlNested(unittest.TestCase):
    def test_set_point(self) -> None:
        doc: dict = {"clicks": {"next_page": {"x": 0, "y": 0}}}
        _set_nested(doc, "clicks.next_page", {"x": 10, "y": 20})
        self.assertEqual(doc["clicks"]["next_page"], {"x": 10, "y": 20})

    def test_set_slot_index(self) -> None:
        doc: dict = {"clicks": {"slots": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}}
        _set_nested(doc, "clicks.slots.0", {"x": 9, "y": 8})
        self.assertEqual(doc["clicks"]["slots"][0], {"x": 9, "y": 8})

    def test_set_ocr_rect(self) -> None:
        doc: dict = {"ocr_regions": {"detail": {"total_growth": {"x": 0, "y": 0, "w": 1, "h": 1}}}}
        _set_nested(doc, "ocr_regions.detail.total_growth", {"x": 1, "y": 2, "w": 3, "h": 4})
        self.assertEqual(doc["ocr_regions"]["detail"]["total_growth"]["w"], 3)


if __name__ == "__main__":
    unittest.main()
