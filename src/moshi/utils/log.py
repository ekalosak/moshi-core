import functools
import os
import sys
import time

# from google.cloud import logging  # NOTE building for functions so cloud logging via stdout
from loguru import logger
from loguru._defaults import LOGURU_FORMAT

LOGURU_FORMAT = LOGURU_FORMAT + " | <g><d>{extra}</d></g>"

ENV = os.getenv("ENV", "prod")
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")
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


def _to_log_dict(rec: dict) -> dict:
    """Convert a loguru record to a gcloud structured logging payload."""
    rec["severity"] = _gcp_log_severity_map(rec["level"].name)
    rec.pop("level")
    if not rec["extra"]:
        rec.pop("extra")
    rec["elapsed"] = _format_timedelta(rec["elapsed"])
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
    rec["timestamp"] = str(rec["time"])
    rec.pop("time")
    return rec


def setup_loguru():
    logger.debug("Adding stdout logger...")
    if LOG_FORMAT == "json":
        logger.debug("Using JSON formatter...")
        formatter = _to_log_dict
    else:
        logger.debug("Using LOGURU formatter...")
        formatter = LOGURU_FORMAT
    logger.remove()
    logger.level("TRANSCRIPT", no=15, color="<magenta>", icon="📜")
    logger.add(
        diagnose=ENV=="dev",
        sink=sys.stdout,
        level=LOG_LEVEL,
        format=formatter,
        colorize=ENV=="dev" or LOG_COLORIZE,
    )

logger.success("Logging configured.")