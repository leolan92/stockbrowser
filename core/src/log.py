import logging
from pathlib import Path

# 日誌檔案路徑
LOG_FILE = Path(__file__).parent / "app.log"

def setup_logger(name: str = "stock_app", log_file: Path = LOG_FILE, level=logging.DEBUG):
    """建立一個 logger，可以同時輸出到檔案與終端機"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重複添加 handler
    if logger.hasHandlers():
        logger.handlers.clear()

    # 格式：時間 | 等級 | 訊息
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 終端機輸出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 檔案輸出
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# 建立全域 logger
logger = setup_logger()
