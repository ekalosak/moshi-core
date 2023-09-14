__version__ = "23.9.10"

import os
GCLOUD_PROJECT = os.getenv("GCLOUD_PROJECT", "moshi-3")

from .utils import log
log.setup_loguru()
from loguru import logger
logger.trace("Moshi loading...")
logger.info(f"GCLOUD_PROJECT={GCLOUD_PROJECT} moshi-core={__version__}")

from .base import *
from .exceptions import *
from .user import *

logger.success("Moshi loaded.")
