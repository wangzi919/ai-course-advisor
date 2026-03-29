#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""執行總務處所有單位職員資料爬蟲"""

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
    from scrapers.oga_staff import OGAStaffScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from scrapers.oga_staff import OGAStaffScraper


# 定義所有單位的資訊
UNITS = [
    {
        "unit_name": "處本部",
        "unit_code": "home",
        "staff_url": "https://oga.nchu.edu.tw/unit-job/mid/14",
        "location_url": "https://oga.nchu.edu.tw/unit-article/mid/13"
    },
    {
        "unit_name": "事務組",
        "unit_code": "business",
        "staff_url": "https://oga.nchu.edu.tw/unit-job/mid/30",
        "location_url": "https://oga.nchu.edu.tw/unit-about/mid/28"
    },
    {
        "unit_name": "採購組",
        "unit_code": "procurement",
        "staff_url": "https://oga.nchu.edu.tw/unit-job/mid/54",
        "location_url": "https://oga.nchu.edu.tw/unit-about/mid/53"
    },
    {
        "unit_name": "出納組",
        "unit_code": "cashier",
        "staff_url": "https://oga.nchu.edu.tw/unit-job/mid/36",
        "location_url": "https://oga.nchu.edu.tw/unit-about/mid/35"
    },
    {
        "unit_name": "營繕組",
        "unit_code": "construction",
        "staff_url": "https://oga.nchu.edu.tw/unit-job/mid/42",
        "location_url": "https://oga.nchu.edu.tw/unit-about/mid/41"
    },
    {
        "unit_name": "資產經營組",
        "unit_code": "property",
        "staff_url": "https://oga.nchu.edu.tw/unit-job/mid/48",
        "location_url": "https://oga.nchu.edu.tw/unit-about/mid/47"
    },
    {
        "unit_name": "駐警隊",
        "unit_code": "security",
        "staff_url": "https://oga.nchu.edu.tw/unit-job/mid/86",
        "location_url": "https://oga.nchu.edu.tw/unit-about/mid/62"
    }
]


def main():
    """主函式"""
    logging.info("=" * 60)
    logging.info("開始更新總務處所有單位職員資料")
    logging.info("=" * 60)

    success_count = 0
    fail_count = 0
    failed_units = []

    for unit in UNITS:
        try:
            logging.info(f"\n正在爬取: {unit['unit_name']} ({unit['unit_code']})")
            logging.info(f"URL: {unit['staff_url']}")

            scraper = OGAStaffScraper(
                unit_name=unit['unit_name'],
                unit_code=unit['unit_code'],
                staff_url=unit['staff_url'],
                location_url=unit.get('location_url', '')
            )
            scraper.run()

            success_count += 1
            logging.info(f"✓ {unit['unit_name']} 完成")

        except Exception as e:
            fail_count += 1
            failed_units.append(unit['unit_name'])
            logging.error(f"✗ {unit['unit_name']} 失敗: {e}", exc_info=True)

    logging.info("\n" + "=" * 60)
    logging.info("總務處職員資料爬取完成")
    logging.info("=" * 60)
    logging.info(f"成功: {success_count} 個單位")
    logging.info(f"失敗: {fail_count} 個單位")

    if failed_units:
        logging.error(f"失敗的單位: {', '.join(failed_units)}")

    # 執行統一腳本
    if success_count > 0:
        logging.info("\n開始執行統一腳本...")
        try:
            from scripts.unify_oga_staff import main as unify_main
            unify_main()
            logging.info("✓ 統一腳本執行完成")
        except Exception as e:
            logging.error(f"✗ 統一腳本執行失敗: {e}", exc_info=True)

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == '__main__':
    main()
