from __future__ import annotations

import unittest

from auto_auction.ocr import is_below_price, is_color_line, parse_number


class TestParseNumber(unittest.TestCase):
    def test_plain(self) -> None:
        self.assertEqual(parse_number("12345"), 12345.0)

    def test_comma(self) -> None:
        self.assertEqual(parse_number("12,345"), 12345.0)

    def test_currency_prefix(self) -> None:
        self.assertEqual(parse_number("￥9800"), 9800.0)

    def test_decimal(self) -> None:
        self.assertEqual(parse_number("12.5"), 12.5)

    def test_empty(self) -> None:
        self.assertIsNone(parse_number(""))
        self.assertIsNone(parse_number("abc"))


class TestRules(unittest.TestCase):
    def test_below_price(self) -> None:
        self.assertTrue(is_below_price(100, 500))
        self.assertFalse(is_below_price(500, 500))
        self.assertFalse(is_below_price(501, 500))

    def test_color_line_strict_gt(self) -> None:
        self.assertTrue(is_color_line(99, 100, 0.98))
        self.assertFalse(is_color_line(98, 100, 0.98))
        self.assertFalse(is_color_line(0, 0, 0.98))
        self.assertFalse(is_color_line(10, 0, 0.98))


if __name__ == "__main__":
    unittest.main()
