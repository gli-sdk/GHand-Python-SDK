import sys
if sys.version_info < (3, 8):
    sys.exit("xiaoyao-sdk requires Python 3.8 or higher")
import logging
import time

from .dexhand import DexHand
from .subscription import SubscriptionManager
from .version import __version__

logger_name = "xiaoyao"
logger = logging.getLogger(logger_name)
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s]: %(message)s"))
logger.addHandler(stream_handler)

logger.info("****** Welcome to the world of Xiaoyao. Just enjoy it! ******")
