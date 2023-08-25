import os

from loguru import logger

GOOGLE_PROJECT_ID = os.environ.get('GOOGLE_PROJECT_ID')
if GOOGLE_PROJECT_ID:
    logger.info(f"GOOGLE_PROJECT_ID: {GOOGLE_PROJECT_ID}")
else:
    logger.warning("GOOGLE_PROJECT_ID not set.")