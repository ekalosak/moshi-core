from datetime import datetime
import json
import sys

import loguru
import pytest

from moshi.utils import log

def test_setup():
    log.setup_loguru()

def _setup(fmt=None, sink=None):
    print("RUN SETUP")
    log.setup_loguru(fmt, sink)
    print("DONE")

@pytest.mark.parametrize("fmt", [None, "", "json", "rich"])
def test_formatting(fmt: str):
    loguru.logger.debug("before")
    _setup()
    loguru.logger.debug("after")

@pytest.mark.parametrize("sink", [sys.stdout.write, sys.stderr.write, print])
def test_sink(sink):
    loguru.logger.debug("before")
    _setup(sink=sink)
    loguru.logger.debug("after")

@pytest.mark.parametrize("serialize_me", [None, "", 1, 1.0, True, [], {}, {"foo": "bar"}, datetime.now()])
def test_json_serialization(serialize_me):
    _log = []
    def sink(x):
        _log.append(x)
    _setup(sink=sink, fmt="json")
    with loguru.logger.contextualize(payload=serialize_me):
        loguru.logger.debug("test")
    # parse json
    # retrieve foo from extra
    assert len(_log) == 1, "sent more than one log message"
    print(_log)
    rec = json.loads(_log[0])