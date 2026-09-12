from __future__ import annotations

import logging

from . import config

_LOGGER_NAME = "card_game_v2.server"


def configure_logging() -> None:
    '''Idempotent - safe to call from create_app() every time it runs, including once per test
    via TestClient(create_app()) across many existing test files. Without the handlers-already-set
    guard, repeated calls would stack duplicate handlers (and leak open file descriptors) rather
    than reusing the same configuration.'''
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(config.LOG_FILE_PATH)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
