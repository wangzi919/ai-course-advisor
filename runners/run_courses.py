#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
執行系所課程爬蟲

此腳本會執行 CoursesScraper 來抓取系所課程資料（含課程大綱）。

使用方式:
    python runners/run_courses.py                    # 抓取預設學年期 (1142)
    python runners/run_courses.py --year 1141       # 抓取指定學年期
    python runners/run_courses.py --no-syllabus     # 不抓取課程大綱
    python runners/run_courses.py --list            # 列出所有可用學年期
"""
import sys
import os
import argparse
import logging

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
    from scrapers.courses_scraper import CoursesScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logging.info(f"將專案根目錄加入路徑: {project_root}")

    try:
        from scrapers.courses_scraper import CoursesScraper
    except ImportError as e:
        logging.error(f"無法匯入 CoursesScraper: {e}")
        sys.exit(1)


def main():
    """主函式"""
    parser = argparse.ArgumentParser(description='抓取系所課程資料')
    parser.add_argument('--year', type=str, default='1142',
                        help='指定學年期代碼 (如: 1142, 1141)')
    parser.add_argument('--no-syllabus', action='store_true',
                        help='不抓取課程大綱')
    parser.add_argument('--list', action='store_true',
                        help='列出所有可用的學年期')
    args = parser.parse_args()

    if args.list:
        scraper = CoursesScraper(year='1142', fetch_syllabus=False)
        scraper.print_available_years()
        return

    logging.info(f"開始抓取學年期 {args.year} 的系所課程...")
    logging.info(f"抓取課程大綱: {'否' if args.no_syllabus else '是'}")

    try:
        scraper = CoursesScraper(
            year=args.year,
            fetch_syllabus=not args.no_syllabus
        )
        scraper.run()

        logging.info("系所課程抓取完成。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
