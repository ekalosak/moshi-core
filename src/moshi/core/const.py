import os

from loguru import logger

GOOGLE_PROJECT = os.environ.get('GOOGLE_PROJECT', 'moshi-3')
logger.info(f"GOOGLE_PROJECT: {GOOGLE_PROJECT}")