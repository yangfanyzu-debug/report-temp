from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.logging_config import LOG_FORMAT, resolve_log_level  # noqa: E402


class LoggingConfigTest(unittest.TestCase):
    def test_resolve_log_level_accepts_known_levels(self):
        self.assertEqual(resolve_log_level("debug"), logging.DEBUG)
        self.assertEqual(resolve_log_level("ERROR"), logging.ERROR)

    def test_resolve_log_level_falls_back_to_info(self):
        self.assertEqual(resolve_log_level("verbose"), logging.INFO)
        self.assertEqual(resolve_log_level(""), logging.INFO)

    def test_log_format_contains_time_level_logger_and_message(self):
        self.assertEqual(
            LOG_FORMAT,
            "%(asctime)s %(levelname)s %(name)s %(message)s",
        )


if __name__ == "__main__":
    unittest.main()
