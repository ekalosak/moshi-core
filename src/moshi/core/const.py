import os

from loguru import logger

GOOGLE_PROJECT_ID = os.environ.get('GOOGLE_PROJECT_ID', 'moshi-3')
logger.debug(f"GOOGLE_PROJECT_ID: {GOOGLE_PROJECT_ID}")