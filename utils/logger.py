#!/usr/bin/env python3
"""
統一的 Logging 設定模組
提供整個專案統一的日誌配置
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logger(
    name: str = __name__,
    log_level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_file_name: str = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    設定並返回一個 logger 實例

    Args:
        name: Logger 名稱
        log_level: 日誌級別 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否輸出到檔案
        log_to_console: 是否輸出到 console
        log_file_name: 日誌檔案名稱，如果為 None 則使用預設名稱
        max_bytes: 單個日誌檔案最大大小
        backup_count: 保留的備份檔案數量

    Returns:
        配置好的 logger 實例
    """
    logger = logging.getLogger(name)

    # 如果 logger 已經有 handlers，直接返回（避免重複添加）
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    # 設定日誌格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File Handler (with rotation)
    if log_to_file:
        # 取得專案根目錄的 logs 資料夾
        project_root = Path(__file__).parent.parent
        logs_dir = project_root / "logs"
        logs_dir.mkdir(exist_ok=True)

        # 決定日誌檔案名稱
        if log_file_name is None:
            log_file_name = f"{name.replace('.', '_')}.log"

        log_file_path = logs_dir / log_file_name

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    """
    快速取得一個標準配置的 logger

    Args:
        name: Logger 名稱

    Returns:
        配置好的 logger 實例
    """
    return setup_logger(name)
