from datetime import datetime
import json
import sys

import loguru
import pytest

from moshi.utils import log

def test_setup():
    log.setup_loguru()

def _setup(fmt="", sink=print):
    print("RUN SETUP")
    log.setup_loguru(fmt, sink)
    print("DONE")

@pytest.mark.parametrize("fmt", ["", "json", "rich"])
def test_formatting(fmt: str):
    loguru.logger.debug("before")
    _setup(fmt=fmt)
    loguru.logger.debug("after")

@pytest.mark.parametrize("sink", [sys.stdout.write, sys.stderr.write, print])
def test_sink(sink):
    loguru.logger.debug("before")
    _setup(sink=sink)
    loguru.logger.debug("after")

@pytest.mark.parametrize("serialize_me", [None, "", 1, 1.0, True, [], {}, {"foo": "bar"}, datetime.now()])
def test_json_serialization(serialize_me):
    """Defines the supported loggable objects that we can log to GCP logging."""
    _log = []
    def sink(x):
        _log.append(x)
    _setup(sink=sink, fmt="json")
    with loguru.logger.contextualize(payload=serialize_me):
        loguru.logger.debug("test")
    assert len(_log) == 1, "sent more than one log message"
    rec = json.loads(_log[0])
    extra = rec["extra"]
    if isinstance(serialize_me, datetime):
        payload = datetime.fromisoformat(extra['payload']).isoformat()
        assert payload == serialize_me.isoformat() + "+00:00", "failed to serialize payload"
    else:
        payload = extra['payload']
        assert payload == serialize_me, "failed to serialize payload"