"""Logging configuration."""

import logging
import sys


def setup_logging(
    level: str = "INFO",
    format: str | None = None,
) -> logging.Logger:
    """Configure logging.

    Args:
        level: Log level
        format: Log format

    Returns:
        Root logger
    """
    if format is None:
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Set third-party library log levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    return logging.getLogger("mobility_bench")
