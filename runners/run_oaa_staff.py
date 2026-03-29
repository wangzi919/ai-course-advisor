#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
此腳本會執行 OAAStaffScraper 來更新教務處職員資料。
設計為可被 cron 等排程工具定期執行。
"""
import sys
import os
import logging

# --- Logging 設定 ---
# 建立 logs 資料夾
log_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'logs')
os.makedirs(log_dir, exist_ok=True)
# 設定日誌檔案路徑
log_file_path = os.path.join(log_dir, f"{os.path.basename(__file__).replace('.py', '.log')}")
# 設定 logging，同時輸出到 console 和檔案
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    ]
)

# --- 路徑設定 ---
try:
    from scrapers.oaa_staff import OAAStaffScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logging.info(f"將專案根目錄加入路徑: {project_root}")

    try:
        from scrapers.oaa_staff import OAAStaffScraper
    except ImportError as e:
        logging.error(f"無法匯入 OAAStaffScraper: {e}")
        sys.exit(1)


def main():
    """
    主函式，用於初始化並執行爬蟲。
    """
    logging.info("開始更新教務處職員資料...")
    try:
        scraper = OAAStaffScraper()
        scraper.force_update()
        logging.info("教務處職員資料更新成功。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
