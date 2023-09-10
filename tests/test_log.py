import importlib

import loguru
import pytest

from moshi.utils import log

def test_default_logging():
    importlib.reload(log)
    importlib.reload(loguru)
    loguru.logger.debug("test")

def test_json_logging(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    importlib.reload(log)
    importlib.reload(loguru)
    log.setup_loguru()
    loguru.logger.debug("test")