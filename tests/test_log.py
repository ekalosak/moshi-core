import importlib

import loguru
import pytest

from moshi.utils import log

@pytest.mark.parametrize("fmt", [None, "", "json", "rich"])
def test_logging(fmt: str):
    loguru.logger.debug("before")
    print("RUN SETUP")
    log.setup_loguru(fmt=fmt)
    print("DONE")
    loguru.logger.debug("after")