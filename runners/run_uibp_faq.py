#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""執行興大校務規劃處 FAQ 爬蟲"""

import logging
import os
import sys

# 設定專案根目錄
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 設定日誌
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'run_uibp_faq.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    ]
)

from scrapers.uibp_faq import UIBPFAQScraper


def main():
    """主函式"""
    logging.info("開始更新興大校務規劃處 FAQ 資料...")
    try:
        scraper = UIBPFAQScraper()
        result = scraper.force_update()
        if result:
            logging.info("FAQ 資料更新成功。")
            sys.exit(0)
        else:
            logging.error("FAQ 資料更新失敗。")
            sys.exit(1)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
