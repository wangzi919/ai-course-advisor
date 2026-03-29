#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""熱重載工具 - 用於在爬蟲更新資料後觸發服務重載"""

import logging
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


def trigger_pm2_reload(service_names: Optional[List[str]] = None):
    """
    觸發 PM2 服務重載

    這是一個可選的備援方案。由於 library API 已實作檔案時間快取機制，
    大多數情況下資料會自動重載，無需重啟服務。

    此函數會執行 PM2 reload，這是一個零停機的平滑重啟操作。

    Args:
        service_names: PM2 服務名稱列表。如果為 None，使用預設服務列表
    """
    if service_names is None:
        # 預設的 MCP 服務名稱
        service_names = ['claude-mcp-server']

    try:
        # 檢查 PM2 是否存在
        result = subprocess.run(
            ['which', 'pm2'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.info("PM2 未安裝，跳過 PM2 reload（使用檔案時間快取機制即可）")
            return

        logger.info("=" * 60)
        logger.info("開始 PM2 熱重載流程")
        logger.info("=" * 60)

        success_count = 0
        fail_count = 0

        for service_name in service_names:
            try:
                logger.info(f"🔄 重載服務: {service_name}")

                result = subprocess.run(
                    ['pm2', 'reload', service_name],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    logger.info(f"✓ 成功重載: {service_name}")
                    success_count += 1
                else:
                    logger.warning(f"✗ 重載失敗: {service_name}")
                    logger.warning(f"  錯誤訊息: {result.stderr.strip()}")
                    fail_count += 1

            except subprocess.TimeoutExpired:
                logger.warning(f"✗ 重載逾時: {service_name}")
                fail_count += 1
            except Exception as e:
                logger.warning(f"✗ 重載錯誤: {service_name} - {e}")
                fail_count += 1

        logger.info("=" * 60)
        logger.info(f"PM2 重載完成: 成功 {success_count} / 失敗 {fail_count}")
        logger.info("=" * 60)

    except Exception as e:
        logger.warning(f"PM2 reload 過程發生錯誤: {e}")


def touch_data_file(file_path: str):
    """
    更新檔案的修改時間戳記

    這會觸發檔案時間快取機制重新載入資料。

    Args:
        file_path: 資料檔案的路徑
    """
    try:
        from pathlib import Path

        path = Path(file_path)
        if path.exists():
            # 更新檔案的存取和修改時間為當前時間
            path.touch()
            logger.info(f"✓ 已更新檔案時間戳記: {file_path}")
        else:
            logger.warning(f"✗ 檔案不存在: {file_path}")

    except Exception as e:
        logger.warning(f"更新檔案時間戳記時發生錯誤: {e}")


def hot_reload_after_scraping(
    data_file_path: Optional[str] = None,
    pm2_services: Optional[List[str]] = None,
    use_pm2_reload: bool = True
):
    """
    爬蟲完成後的完整熱重載流程

    此函數整合了兩種熱重載機制：
    1. 檔案時間戳更新（主要機制，快速且無需重啟）
    2. PM2 服務重載（備援機制，確保完全重載）

    Args:
        data_file_path: 資料檔案路徑（選填）
        pm2_services: PM2 服務名稱列表（選填）
        use_pm2_reload: 是否使用 PM2 reload（預設為 True）
    """
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 18 + "熱重載流程開始" + " " * 18 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")

    # 步驟 1: 更新檔案時間戳（如果提供了檔案路徑）
    if data_file_path:
        logger.info("📝 步驟 1/2: 更新資料檔案時間戳")
        touch_data_file(data_file_path)
        logger.info("")

    # 步驟 2: PM2 重載（如果啟用）
    if use_pm2_reload:
        logger.info("🔄 步驟 2/2: 觸發 PM2 服務重載")
        trigger_pm2_reload(pm2_services)
    else:
        logger.info("⏭️  步驟 2/2: 跳過 PM2 重載（僅使用檔案時間快取機制）")

    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 18 + "熱重載流程完成" + " " * 18 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
