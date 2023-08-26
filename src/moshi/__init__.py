from . import version
__version__ = version.__version__
from .core.base import *
from .core.const import *
from .utils import log

log.setup_loguru()