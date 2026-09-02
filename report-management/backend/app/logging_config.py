from __future__ import annotations

import logging
import sys


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def resolve_log_level(level_name: str) -> int:
    normalized = str(level_name or "INFO").upper()
    if normalized not in VALID_LOG_LEVELS:
        normalized = "INFO"
    return getattr(logging, normalized)


def configure_logging(level_name: str) -> None:
    level = resolve_log_level(level_name)
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root.addHandler(handler)
        return
    for handler in root.handlers:
        handler.setFormatter(formatter)
