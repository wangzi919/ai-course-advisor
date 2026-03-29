#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""執行學務處職員資料爬蟲（單一單位）"""

import sys
import os
import logging
import argparse

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
    from scrapers.osa_staff import OSAStaffScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from scrapers.osa_staff import OSAStaffScraper


def main():
    """主函式"""
    parser = argparse.ArgumentParser(description='爬取學務處職員資料')
    parser.add_argument(
        '--unit',
        type=str,
        default='office',
        choices=['dean', 'deputy', 'office', 'arm', 'laa', 'act', 'cdc', 'dorm', 'isrc'],
        help='單位代碼（預設：office）'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='強制更新（忽略快取）'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='列出所有可用單位'
    )

    args = parser.parse_args()

    # 列出所有單位
    if args.list:
        print("\n可用單位代碼：")
        for code, (name, url, dtype) in OSAStaffScraper.UNITS.items():
            print(f"  {code:8s} - {name:12s} ({dtype})")
        return

    unit_name = OSAStaffScraper.UNITS[args.unit][0]
    logging.info(f"開始更新學務處{unit_name}職員資料...")

    try:
        scraper = OSAStaffScraper(unit_code=args.unit)

        if args.force:
            scraper.force_update()
        else:
            scraper.update()

        logging.info(f"學務處{unit_name}職員資料更新成功。")
        sys.exit(0)

    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
