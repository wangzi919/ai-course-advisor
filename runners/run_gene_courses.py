#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
執行通識課程爬蟲

此腳本會執行 GeneCoursesScraper 來抓取通識課程資料（含課程大綱）。

使用方式:
    python runners/run_gene_courses.py                    # 抓取預設學年期 (1142)
    python runners/run_gene_courses.py --year 1141       # 抓取指定學年期
    python runners/run_gene_courses.py --all             # 抓取所有學年期
    python runners/run_gene_courses.py --subject E       # 只抓取人文領域
    python runners/run_gene_courses.py --no-syllabus     # 不抓取課程大綱
    python runners/run_gene_courses.py --list            # 列出所有可用選項
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
    from scrapers.gene_courses_scraper import GeneCoursesScraper
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logging.info(f"將專案根目錄加入路徑: {project_root}")

    try:
        from scrapers.gene_courses_scraper import GeneCoursesScraper
    except ImportError as e:
        logging.error(f"無法匯入 GeneCoursesScraper: {e}")
        sys.exit(1)


def main():
    """主函式"""
    parser = argparse.ArgumentParser(description='抓取通識課程資料')
    parser.add_argument('--year', type=str, default='1142',
                        help='指定學年期代碼 (如: 1142, 1141)')
    parser.add_argument('--subject', type=str, default='all',
                        help='通識類別 (all=所有, EFGKM=人文/社會/自然/統合/核心素養, E=人文, F=社會, G=自然, K=統合, M=核心素養, L=通識資訊素養, 3=敘事表達/大學國文, N=外國語文)')
    parser.add_argument('--all', action='store_true',
                        help='抓取所有學年期')
    parser.add_argument('--no-syllabus', action='store_true',
                        help='不抓取課程大綱')
    parser.add_argument('--list', action='store_true',
                        help='列出所有可用的選項')
    args = parser.parse_args()

    if args.list:
        GeneCoursesScraper.print_available_options()
        return

    years = GeneCoursesScraper.get_available_years() if args.all else [args.year]

    logging.info(f"準備抓取 {len(years)} 個學年期")
    logging.info(f"通識類別: {args.subject}")
    logging.info(f"抓取課程大綱: {'否' if args.no_syllabus else '是'}")

    failed = []
    for i, year in enumerate(years, 1):
        logging.info(f"[{i}/{len(years)}] 開始抓取學年期 {year}...")
        try:
            scraper = GeneCoursesScraper(
                year=year,
                subject=args.subject,
                fetch_syllabus=not args.no_syllabus
            )
            scraper.run()
        except Exception as e:
            logging.error(f"學年期 {year} 抓取失敗: {e}", exc_info=True)
            failed.append(year)

    if failed:
        logging.warning(f"以下學年期抓取失敗: {', '.join(failed)}")
        sys.exit(1)
    else:
        logging.info(f"全部 {len(years)} 個學年期抓取完成。")
        sys.exit(0)


if __name__ == '__main__':
    main()
