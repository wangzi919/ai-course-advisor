#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""執行學校行事曆爬蟲"""

import sys
import os
import logging

# 設定日誌
log_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, f"{os.path.basename(__file__).replace('.py', '.log')}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    ]
)

# 匯入爬蟲
try:
    from scrapers.school_calendar import SchoolCalendarScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from scrapers.school_calendar import SchoolCalendarScraper


def main():
    """主函式"""
    logging.info("開始更新學校行事曆資料...")
    try:
        scraper = SchoolCalendarScraper()
        scraper.check_and_scrape()  # 使用檢查機制
        logging.info("學校行事曆資料更新成功。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
