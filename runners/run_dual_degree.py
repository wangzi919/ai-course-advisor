#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
執行雙聯學位計畫爬蟲。
資料來源：
  - 締約說明: https://www.oia.nchu.edu.tw/.../7-3-1-agreement-signing-tw
  - 締約學校: https://www.oia.nchu.edu.tw/.../7-3-2-list-of-partner-universities-of-dual-degree-program-tw
輸出: data/oia/dual_degree.json
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
    from scrapers.dual_degree_scraper import DualDegreeScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from scrapers.dual_degree_scraper import DualDegreeScraper


def main():
    logging.info("開始更新雙聯學位資料...")
    try:
        scraper = DualDegreeScraper()
        scraper.force_update()
        logging.info("雙聯學位資料更新成功。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
