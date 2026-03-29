#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""執行學務處所有單位職員資料爬蟲"""

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
    from scrapers.osa_staff import OSAStaffScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from scrapers.osa_staff import OSAStaffScraper


def main():
    """主函式：爬取所有學務處單位"""
    logging.info("=" * 60)
    logging.info("開始爬取所有學務處單位職員資料")
    logging.info("=" * 60)

    # 所有單位代碼
    unit_codes = list(OSAStaffScraper.UNITS.keys())
    success_count = 0
    fail_count = 0
    failed_units = []

    for unit_code in unit_codes:
        unit_name = OSAStaffScraper.UNITS[unit_code][0]
        logging.info(f"\n處理單位: {unit_name} ({unit_code})")
        logging.info("-" * 60)

        try:
            scraper = OSAStaffScraper(unit_code=unit_code)
            scraper.force_update()
            logging.info(f"✓ {unit_name} 爬取成功")
            success_count += 1

        except Exception as e:
            logging.error(f"✗ {unit_name} 爬取失敗: {e}", exc_info=True)
            fail_count += 1
            failed_units.append(unit_name)

    # 總結
    logging.info("\n" + "=" * 60)
    logging.info("爬取完成總結")
    logging.info("=" * 60)
    logging.info(f"成功: {success_count} 個單位")
    logging.info(f"失敗: {fail_count} 個單位")

    if failed_units:
        logging.warning(f"失敗單位: {', '.join(failed_units)}")

    # 如果有失敗的單位，返回錯誤碼
    if fail_count > 0:
        sys.exit(1)
    else:
        logging.info("\n所有單位爬取成功！")
        sys.exit(0)


if __name__ == '__main__':
    main()
