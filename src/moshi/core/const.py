import os

from loguru import logger

GOOGLE_PROJECT = os.environ.get('GOOGLE_PROJECT', 'dne')
logger.info(f"GOOGLE_PROJECT: {GOOGLE_PROJECT}")