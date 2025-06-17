import sys
if sys.version_info < (3, 8, 0):
    sys.exit('Xiaoyao SDK requires Python 3.8.0 or later')

import logging
import time

# 设置日志
logger_name = 'xiaoyao'
logger = logging.getLogger(logger_name)
logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)

logger.info("***** Welcome to Xiaoyao SDK *****")

# 导入子模块
from . import hand
from . import joint
from . import tip
from . import tactile
from . import common
from . import errors
from . import status
from . import version

# 导入基础模块
from . import module
from . import message
from . import event