#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
執行教學計畫申請爬蟲。
資料來源：https://cdtl.nchu.edu.tw/2019application/index.php
輸出：data/cdtl/cdtl_applications.json
"""

import sys
import os
import logging

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

try:
    from scrapers.cdtl_applications_scraper import CdtlApplicationsScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from scrapers.cdtl_applications_scraper import CdtlApplicationsScraper


def main():
    logging.info("開始更新教學計畫申請資料...")
    try:
        scraper = CdtlApplicationsScraper()
        scraper.force_update()
        logging.info("教學計畫申請資料更新成功。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
