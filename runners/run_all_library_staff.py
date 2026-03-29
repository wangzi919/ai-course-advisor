#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
此腳本會爬取圖書館所有單位的職員資料
"""
import sys
import os
import logging
import json
import time

# --- Logging 設定 ---
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

# --- 路徑設定 ---
try:
    from scrapers.library_staff import LibraryStaffScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logging.info(f"將專案根目錄加入路徑: {project_root}")

    try:
        from scrapers.library_staff import LibraryStaffScraper
    except ImportError as e:
        logging.error(f"無法匯入 LibraryStaffScraper: {e}")
        sys.exit(1)


# 圖書館所有單位的業務職掌頁面
LIBRARY_UNITS = [
    {"unit": "館長室", "code": "dean", "key": "44"},
    {"unit": "行政庶務室", "code": "admin", "key": "43"},
    {"unit": "採編組", "code": "catalog", "key": "42"},
    {"unit": "典閱組", "code": "circulation", "key": "41"},
    {"unit": "參考組", "code": "reference", "key": "40"},
    {"unit": "數位資源組", "code": "digital", "key": "39"},
    {"unit": "資訊組", "code": "it", "key": "38"},
    {"unit": "校史館組", "code": "history", "key": "37"},
    {"unit": "出版中心", "code": "press", "key": "36"}
]


def main():
    """
    主函式，爬取所有單位的職員資料
    """
    logging.info("="*70)
    logging.info("開始爬取圖書館所有單位的職員資料")
    logging.info("="*70)

    results = []
    success_count = 0
    fail_count = 0

    for unit_info in LIBRARY_UNITS:
        unit_name = unit_info['unit']
        unit_code = unit_info['code']
        unit_key = unit_info['key']

        logging.info(f"\n{'='*70}")
        logging.info(f"正在爬取: {unit_name}")
        logging.info(f"Key: {unit_key}")
        logging.info(f"{'='*70}")

        try:
            scraper = LibraryStaffScraper(
                unit_name=unit_name,
                unit_code=unit_code,
                unit_key=unit_key
            )
            scraper.force_update()

            success_count += 1
            results.append({
                'unit': unit_name,
                'status': 'success',
                'message': '成功'
            })

            logging.info(f"✅ {unit_name} 爬取成功")

            # 避免請求過快
            time.sleep(1)

        except Exception as e:
            fail_count += 1
            results.append({
                'unit': unit_name,
                'status': 'failed',
                'message': str(e)
            })
            logging.error(f"❌ {unit_name} 爬取失敗: {e}", exc_info=True)

    # 輸出總結
    logging.info("\n" + "="*70)
    logging.info("爬取完成！")
    logging.info("="*70)
    logging.info(f"成功: {success_count} 個單位")
    logging.info(f"失敗: {fail_count} 個單位")

    for result in results:
        status_icon = "✅" if result['status'] == 'success' else "❌"
        logging.info(f"  {status_icon} {result['unit']}: {result['message']}")

    if fail_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
