"""utils/logger.py – Dual-sink logger (console + rotating file)."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from config.settings import LOG_LEVEL, LOG_FORMAT, LOGS_DIR


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    fmt = logging.Formatter(LOG_FORMAT)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    fh = RotatingFileHandler(
        LOGS_DIR / "pipeline.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger
