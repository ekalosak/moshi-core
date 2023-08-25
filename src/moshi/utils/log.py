import asyncio
import os
import sys

from google.cloud import logging
from loguru import logger
from loguru._defaults import LOGURU_FORMAT

LOG_LEVEL = os.getenv("MLOGLEVEL", "DEBUG")
FILE_LOGS = int(os.getenv("MOSHILOGDISK", 0))
STDOUT_LOGS = int(os.getenv("MOSHILOGSTDOUT", 1))
CLOUD_LOGS = int(os.getenv("MOSHILOGCLOUD", 0))

if STDOUT_LOGS:
    import pyfiglet


def _gcp_log_severity_map(level: str) -> str:
    """Convert loguru custom levels to GCP allowed severity level.
    Source:
        - https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#LogSeverity
    """
    match level:
        case "SUCCESS":
            return "INFO"
        case "INSTRUCTION":
            return "DEBUG"
        case "TRANSCRIPT":
            return "INFO"
        case "TRACE":
            return "DEBUG"
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
    log_format = LOGURU_FORMAT + " | <g><d>{extra}</d></g>"
    logger.level("TRANSCRIPT", no=15, color="<magenta>", icon="📜")
    print(f"Logging configuration: LEVEL={LOG_LEVEL} STDOUT={STDOUT_LOGS}, FILE={FILE_LOGS}, CLOUD={CLOUD_LOGS}")
    if STDOUT_LOGS:
        print("Adding stdout logger...")
        logger.add(
            diagnose=True,
            sink=sys.stderr,
            level=LOG_LEVEL,
            format=log_format,
            colorize=True,
        )
        logger.warning("Logging to stdout, including diagnostics.")
    if FILE_LOGS:
        print("Adding file logger...")
        logger.add(
            "logs/server.log",
            level=LOG_LEVEL,
            format=log_format,
            rotation="10 MB",
        )
    # Google logging  (https://github.com/Delgan/loguru/issues/789)
    if CLOUD_LOGS:
        print("Creating GCP logging client...")
        logging_client = logging.Client()
        gcp_logger = logging_client.logger("gcp-logger")

        async def _log_to_gcp(message):
            try:
                logdict = _to_log_dict(message.record)
                await asyncio.to_thread(gcp_logger.log_struct, logdict)
            except Exception as e:
                print(f"Error logging to GCP: {e}")

        def log_to_gcp(message):
            """Sends log messages to GCP logging with best effort."""
            asyncio.ensure_future(_log_to_gcp(message))

        print('Adding GCP logger...')
        logger.add(
            log_to_gcp,
            level=LOG_LEVEL,
            format="{message}",
        )
        print('GCP logger added.')


def splash(text: str):
    if STDOUT_LOGS:
        print("\n" + pyfiglet.Figlet(font="roman").renderText(text) + "\n")
