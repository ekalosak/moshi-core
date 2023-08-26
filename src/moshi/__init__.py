from .version import __version__
from .utils import log
log.setup_loguru()
from loguru import logger
logger.trace("Moshi loading...")

import os
GOOGLE_PROJECT = os.environ.get('GOOGLE_PROJECT', 'dne')
logger.info(f"GOOGLE_PROJECT: {GOOGLE_PROJECT}")

from .base import *
from .exceptions import *
from .user import *

logger.success("Moshi loaded.")