#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
此腳本會爬取教務處所有單位的職員資料
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


# 教務處所有單位的業務職掌頁面
OAA_UNITS = [
    {"unit": "教務長室", "code": "dean", "url": "https://oaa.nchu.edu.tw/zh-tw/dean-staff"},
    {"unit": "註冊組", "code": "rs", "url": "https://oaa.nchu.edu.tw/zh-tw/rs-staff"},
    {"unit": "課務組", "code": "course", "url": "https://oaa.nchu.edu.tw/zh-tw/course-staff"},
    {"unit": "招生組", "code": "recruit", "url": "https://oaa.nchu.edu.tw/zh-tw/recruit-staff"},
    {"unit": "教發中心", "code": "cdtl", "url": "https://oaa.nchu.edu.tw/zh-tw/cdtl-staff"},
    {"unit": "通識中心", "code": "ge", "url": "https://oaa.nchu.edu.tw/zh-tw/ge-staff"},
    {"unit": "雙語中心", "code": "emi", "url": "https://oaa.nchu.edu.tw/zh-tw/emi-staff"}
]


def main():
    """
    主函式，爬取所有單位的職員資料
    """
    logging.info("="*70)
    logging.info("開始爬取教務處所有單位的職員資料")
    logging.info("="*70)

    results = []
    success_count = 0
    fail_count = 0

    for unit_info in OAA_UNITS:
        unit_name = unit_info['unit']
        unit_code = unit_info['code']
        unit_url = unit_info['url']

        logging.info(f"\n{'='*70}")
        logging.info(f"正在爬取: {unit_name}")
        logging.info(f"URL: {unit_url}")
        logging.info(f"{'='*70}")

        try:
            scraper = OAAStaffScraper(unit_name=unit_name, unit_code=unit_code, staff_url=unit_url)
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
