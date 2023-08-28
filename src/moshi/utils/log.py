import functools
import os
import sys
import time

# from google.cloud import logging  # NOTE building for functions so cloud logging via stdout
from loguru import logger
from loguru._defaults import LOGURU_FORMAT

LOG_FORMAT = LOGURU_FORMAT + " | <g><d>{extra}</d></g>"

ENV = os.getenv("ENV", "prod")
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
FILE_LOGS = int(os.getenv("MLOGDISK", 0))
STDOUT_LOGS = int(os.getenv("MLOGSTDOUT", 1))
CLOUD_LOGS = int(os.getenv("MLOGCLOUD", 0))
logger.info(f"ENV={ENV} LOG_LEVEL={LOG_LEVEL} FILE_LOGS={FILE_LOGS} STDOUT_LOGS={STDOUT_LOGS} CLOUD_LOGS={CLOUD_LOGS}")
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
    logger.remove()
    logger.level("TRANSCRIPT", no=15, color="<magenta>", icon="📜")
    print(f"Logging configuration: LEVEL={LOG_LEVEL} STDOUT={STDOUT_LOGS}, FILE={FILE_LOGS}, CLOUD={CLOUD_LOGS}")
    if STDOUT_LOGS:
        print("Adding stdout logger...")
        logger.add(
            diagnose=ENV=="dev",
            sink=sys.stderr,
            level=LOG_LEVEL,
            format=LOG_FORMAT,
            colorize=ENV=="dev",
        )
    if FILE_LOGS:
        print("Adding file logger...")
        logger.add(
            "logs/server.log",
            level=LOG_LEVEL,
            format=LOG_FORMAT,
            rotation="10 MB",
        )
    # # Google logging  (https://github.com/Delgan/loguru/issues/789)
    # if CLOUD_LOGS:
    #     print("Creating GCP logging client...")
    #     logging_client = logging.Client()
    #     gcp_logger = logging_client.logger("gcp-logger")

    #     async def _log_to_gcp(message):
    #         try:
    #             logdict = _to_log_dict(message.record)
    #             await gcp_logger.log_struct(logdict)
    #         except Exception as e:
    #             print(f"Error logging to GCP: {e}")

logger.success("Logging configured.")