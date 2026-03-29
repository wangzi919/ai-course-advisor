#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
執行領域模組實施要點及課程資訊爬蟲。
資料來源：
  - 實施要點: https://oaa.nchu.edu.tw/zh-tw/rule/download-list.0.0.L3%EF%BC%8D28
  - 課程資訊: https://oaa.nchu.edu.tw/zh-tw/unit-page-p.342/page-list.2923
輸出: data/modules/domain_modules.json
"""

import sys
import os
import logging

# --- Logging 設定 ---
log_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, f"{os.path.basename(__file__).replace('.py', '.log')}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file_path, mode="a", encoding="utf-8"),
    ],
)

# --- 路徑設定 ---
try:
    from scrapers.domain_modules_scraper import DomainModulesScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        from scrapers.domain_modules_scraper import DomainModulesScraper
    except ImportError as e:
        logging.error(f"無法匯入 DomainModulesScraper: {e}")
        sys.exit(1)


def main():
    logging.info("開始更新領域模組資料...")
    try:
        scraper = DomainModulesScraper()
        # force_update() 會清除快取後重新爬取；若要保留快取請改用 check_and_scrape()
        scraper.force_update()
        logging.info("領域模組資料更新成功。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
