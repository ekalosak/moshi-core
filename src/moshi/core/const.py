import os

from loguru import logger

GOOGLE_PROJECT = os.environ.get('GOOGLE_PROJECT')
if GOOGLE_PROJECT:
    logger.info(f"GOOGLE_PROJECT: {GOOGLE_PROJECT}")
else:
    logger.warning("GOOGLE_PROJECT not set.")