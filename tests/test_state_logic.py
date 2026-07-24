from __future__ import annotations

import unittest

from auto_auction.state_machine import pages_exhausted, should_open_detail


class TestStateLogic(unittest.TestCase):
    def test_should_open_detail(self) -> None:
        self.assertTrue(should_open_detail(100.0, 500.0))
        self.assertFalse(should_open_detail(500.0, 500.0))
        self.assertFalse(should_open_detail(None, 500.0))

    def test_pages_exhausted(self) -> None:
        self.assertFalse(pages_exhausted(0, 20))
        self.assertFalse(pages_exhausted(19, 20))
        self.assertTrue(pages_exhausted(20, 20))


if __name__ == "__main__":
    unittest.main()
