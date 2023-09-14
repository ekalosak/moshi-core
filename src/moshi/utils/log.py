import functools
import json
import os
import sys
import time

# from google.cloud import logging  # NOTE building for functions so cloud logging via stdout
import loguru
from loguru import logger
from loguru._defaults import LOGURU_FORMAT

LOGURU_FORMAT = LOGURU_FORMAT + " | <g><d>{extra}</d></g>"

ENV = os.getenv("ENV", "prod")
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
LOG_FORMAT = os.getenv("LOG_FORMAT", "rich")  # either json or anything else
LOG_COLORIZE = int(os.getenv("LOG_COLORIZE", 0))
logger.info(f"ENV={ENV} LOG_LEVEL={LOG_LEVEL} LOG_FORMAT={LOG_FORMAT} LOG_COLORIZE={LOG_COLORIZE}")
if ENV == "dev":
    logger.warning("Running in dev mode. Logs will be verbose and include sensitive diagnostic data.")

def traced(f, msg: str = None, verbose = False):
    msg = msg or f.__name__
    @functools.wraps(f)
    def wrapper(*a, **k):
        with logger.contextualize(**k if verbose else {}):
            t0 = time.monotonic()
            logger.opt(depth=1).trace(f"[START] {msg}")
            result = f(*a, **k)
            logger.opt(depth=1).trace(f"[END] {msg} ({time.monotonic() - t0:.3f}s)")
        return result
    return wrapper

def _gcp_log_severity_map(level: str) -> str:
    """Convert loguru custom levels to GCP allowed severity level.
    Source:
        - https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#LogSeverity
    """
    match level:
        case "SUCCESS":
            return "INFO"
        case "TRACE":
            if ENV == "dev":
                return "DEBUG"
            else:
                return "INFO"
        case _:
            return level


def _format_timedelta(td) -> str:
    return f"{td.days}days{td.seconds}secs{td.microseconds}usecs"

def _toRFC3339(dt):
    """Convert a datetime to RFC3339."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def _jsonify(obj):
    """Convert an object to JSON serializable."""
    if hasattr(obj, "isoformat"):
        return _toRFC3339(obj)
    logger.warning(f"Unhandled type {type(obj)}")
    return str(obj)

def _toGCPFormat(rec: loguru._handler.Message) -> str:
    """Convert a loguru record to a gcloud structured logging payload."""
    rec = rec.record
    rec["severity"] = _gcp_log_severity_map(rec["level"].name)
    rec.pop("level")
    if not rec["extra"]:
        rec.pop("extra")
    rec["elapsed"] = _format_timedelta(rec["elapsed"])
    if "exception" in rec:
        if rec["exception"] is not None:
            rec["exception"] = str(rec["exception"])
        else:
            rec.pop("exception")
    rec["file"] = rec["file"].name  # also .path
    rec["process_id"] = rec["process"].id
    rec["process_name"] = rec["process"].name
    rec.pop("process")
    rec["thread_id"] = rec["thread"].id
    rec["thread_name"] = rec["thread"].name
    rec.pop("thread")
    return json.dumps(rec, default=lambda o: _jsonify(o))

def setup_loguru(fmt=LOG_FORMAT, sink=sys.stdout.write):
    logger.debug("Adding stdout logger...")
    colorize = ENV == "dev" or LOG_COLORIZE or fmt == "rich"
    diagnose = ENV == "dev"
    if fmt == "json":
        logger.debug("Using JSON formatter...")
        def _sink(rec):
            sink(_toGCPFormat(rec) + "\n")
    else:
        logger.debug("Using LOGURU formatter...")
        _sink = sink
    try:
        logger.level("TRANSCRIPT", no=15, color="<magenta>", icon="📜")
    except TypeError:
        logger.debug("TRANSCRIPT level already defined.")
    logger.remove()
    logger.add(_sink,
        diagnose=diagnose,
        level=LOG_LEVEL,
        format=LOGURU_FORMAT,
        colorize=colorize,
    )

logger.success("Logging configured.")