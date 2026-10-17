import logging
from datetime import datetime
log_format = "%(bt_time)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s"

# 配置日志
logging.basicConfig(level=logging.INFO, format=log_format)

# 创建一个 Logger
init_logger = logging.getLogger("my_logger")

# 创建一个 LoggerAdapter，用于添加额外的上下文信息
log = logging.LoggerAdapter(init_logger, {"bt_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
log.info("bit-trader loaded，application start✈️")