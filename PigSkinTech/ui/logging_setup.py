"""Small local diagnostic log; never log passwords or case contents."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from services.paths import DATA_ROOT


def configure_logging():
    log_dir = DATA_ROOT / 'logs'
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger('pigskin')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(log_dir / 'pigskin.log', maxBytes=1_000_000,
                                      backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s'))
        logger.addHandler(handler)
    return logger
