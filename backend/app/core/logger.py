import sys
import os
from loguru import logger

def setup_app_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        enqueue=True,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logger.add(
        f"{log_dir}/app_metrics.log",
        enqueue=True,
        serialize=True,
        rotation="100 MB",
        retention="30 days",
        level="INFO",
    )

    print("Logging configured successfully.")