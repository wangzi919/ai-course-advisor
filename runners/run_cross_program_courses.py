#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
執行跨領域學程課程爬蟲

此腳本會執行 CrossProgramCoursesScraper 來抓取跨領域學程課程資料（含課程大綱）。
需要先在 .env 中設定 SESSION 和 TS01489091。

使用方式:
    python runners/run_cross_program_courses.py                    # 抓取大學部所有學程
    python runners/run_cross_program_courses.py --year 1141       # 抓取指定學年期
    python runners/run_cross_program_courses.py --career G        # 抓取研究生學程
    python runners/run_cross_program_courses.py --program 27      # 只抓取特定學程
    python runners/run_cross_program_courses.py --no-syllabus     # 不抓取課程大綱
    python runners/run_cross_program_courses.py --list            # 列出所有可用選項
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
    from scrapers.cross_program_courses_scraper import CrossProgramCoursesScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logging.info(f"將專案根目錄加入路徑: {project_root}")

    try:
        from scrapers.cross_program_courses_scraper import CrossProgramCoursesScraper
    except ImportError as e:
        logging.error(f"無法匯入 CrossProgramCoursesScraper: {e}")
        sys.exit(1)


def main():
    """主函式"""
    parser = argparse.ArgumentParser(description='抓取跨領域學程課程資料')
    parser.add_argument('--year', type=str, default='1142',
                        help='指定學年期代碼 (如: 1142, 1141)')
    parser.add_argument('--career', type=str, default='U',
                        help='學制 (U=大學部, G=研究生, E=教育學程)')
    parser.add_argument('--program', type=str, default=None,
                        help='學程代碼 (如: 19, 27)，不指定則抓取所有學程')
    parser.add_argument('--no-syllabus', action='store_true',
                        help='不抓取課程大綱')
    parser.add_argument('--list', action='store_true',
                        help='列出所有可用的選項')
    args = parser.parse_args()

    if args.list:
        CrossProgramCoursesScraper.print_available_options()
        return

    logging.info(f"開始抓取學年期 {args.year} 的跨領域學程課程...")
    logging.info(f"學制: {args.career}")
    if args.program:
        logging.info(f"學程代碼: {args.program}")
    else:
        logging.info("抓取所有學程")
    logging.info(f"抓取課程大綱: {'否' if args.no_syllabus else '是'}")

    try:
        scraper = CrossProgramCoursesScraper(
            year=args.year,
            career=args.career,
            program=args.program,
            fetch_syllabus=not args.no_syllabus
        )
        scraper.run()

        logging.info("跨領域學程課程抓取完成。")
        sys.exit(0)
    except Exception as e:
        logging.error(f"爬取過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
