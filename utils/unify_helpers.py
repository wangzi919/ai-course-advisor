#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""統一資料腳本的輔助工具"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def save_unified_data_with_hot_reload(
    output_path: Path,
    unified_data: Dict[str, Any],
    pm2_services: list = None
) -> Path:
    """
    儲存統一資料並觸發熱重載

    此函數整合了兩個功能:
    1. 儲存 JSON 資料到檔案
    2. 觸發熱重載機制 (檔案時間戳 + PM2 reload)

    Args:
        output_path: 輸出檔案路徑
        unified_data: 要儲存的資料 (包含 metadata 和 data)
        pm2_services: PM2 服務名稱列表 (預設 ['claude-mcp-server'])

    Returns:
        Path: 輸出檔案路徑

    Raises:
        Exception: 儲存失敗時拋出例外
    """
    if pm2_services is None:
        pm2_services = ['claude-mcp-server']

    # 儲存資料
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(unified_data, f, ensure_ascii=False, indent=2)
        logger.info(f"資料已成功儲存至: {output_path}")
    except Exception as e:
        logger.error(f"儲存資料失敗: {e}")
        raise

    # 觸發熱重載（完整日誌輸出）
    try:
        from utils.hot_reload import hot_reload_after_scraping

        # hot_reload_after_scraping 會輸出完整的熱重載日誌
        hot_reload_after_scraping(
            data_file_path=str(output_path),
            pm2_services=pm2_services,
            use_pm2_reload=True
        )
    except ImportError:
        logger.warning("⚠ 無法載入 hot_reload 模組，跳過熱重載")
    except Exception as e:
        logger.warning(f"⚠ 熱重載失敗: {e}")

    return output_path
