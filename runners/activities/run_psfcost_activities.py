#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""執行 PSFCOST 研習暨演講活動爬蟲"""

import sys
import os
import logging
from pathlib import Path

# 設定日誌
project_root = Path(__file__).resolve().parent.parent.parent
log_dir = project_root / 'logs'
log_dir.mkdir(exist_ok=True)
log_file_path = log_dir / f"{Path(__file__).stem}.log"

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
    from scrapers.activities.psfcost_activities import PsfcostActivitiesScraper
except ImportError:
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from scrapers.activities.psfcost_activities import PsfcostActivitiesScraper


def main():
    """主函式"""
    logging.info("開始更新 PSFCOST 研習暨演講活動資料...")
    try:
        scraper = PsfcostActivitiesScraper()
        scraper.force_update()  # 強制更新
        logging.info("PSFCOST 研習暨演講活動資料更新成功。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
