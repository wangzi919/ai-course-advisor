#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通識課程爬蟲

抓取中興大學通識課程資料，包含課程大綱。

使用方式:
    scraper = GeneCoursesScraper(year='1142')
    scraper.run()  # 抓取指定學年期的所有通識課程

環境變數設定 (.env):
    USER_AGENT: 瀏覽器 User-Agent (選填)
    REQUEST_DELAY: 請求間隔秒數 (選填，預設 0.3)
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .syllabus_parser import parse_syllabus

logger = logging.getLogger(__name__)


# 通識課程類別
GENE_SUBJECTS = {
    'all': '所有通識領域',
    'EFGKM': '人文/社會/自然/統合/核心素養',
    'E': '人文領域',
    'F': '社會領域',
    'G': '自然領域',
    'K': '統合領域',
    'M': '核心素養',
    'L': '通識資訊素養',
    '3': '敘事表達/大學國文',
    'N': '外國語文(110學年後)',
}

# subject=all 時，分別查詢以下類別再合併
ALL_SUBJECT_QUERIES = ['EFGKM', 'L', '3', 'N']

# 可用學年期
YEARS = [
    '1142', '1141', '1132', '1131', '1122', '1121', '1112', '1111',
    '1102', '1101', '1092', '1091', '1082', '1081', '1072', '1071',
    '1062', '1061', '1052', '1051', '1042', '1041', '1032', '1031',
    '1022', '1021', '1012', '1011', '1002', '1001', '0992', '0991',
    '0982', '0981', '0972', '0971', '0962', '0961', '0952', '0951',
    '0942', '0941',
]

# 要保留的欄位 (索引, 欄位名稱)
# EFGKM 格式：15 欄（含領域、學群）
FIELDS_15 = [
    (0, '領域'),
    (1, '學群'),
    (2, '選課號碼'),
    (3, '科目名稱'),
    (4, '學分'),
    (5, '上課時間'),
    (6, '上課週別'),
    (7, '上課教室'),
    (8, '授課教師'),
    (9, '開課單位'),
    (10, '開課人數'),
    (13, '授課語言'),
    (14, '備註'),
]

# L/3/N 格式：12 欄（無領域、學群、可選餘額）
FIELDS_12 = [
    (0, '選課號碼'),
    (1, '科目名稱'),
    (2, '學分'),
    (3, '上課時間'),
    (4, '上課週別'),
    (5, '上課教室'),
    (6, '授課教師'),
    (7, '開課單位'),
    (8, '開課人數'),
    (10, '授課語言'),
    (11, '備註'),
]

# L/3/N 類別對應的領域名稱
SUBJECT_DOMAIN_MAP = {
    'L': '通識資訊素養',
    '3': '敘事表達/大學國文',
    'N': '外國語文(110學年後)',
}


class GeneCoursesScraper:
    """通識課程爬蟲"""

    def __init__(
        self,
        year: str = '1142',
        subject: str = 'all',
        fetch_syllabus: bool = True,
        output_dir: str = 'courses/all_ge_courses_syllabi',
    ):
        """
        初始化爬蟲

        Args:
            year: 學年期代碼 (如: 1142)
            subject: 通識類別 (all=所有, EFGKM=人文/社會/自然/統合/核心素養, E=人文, F=社會, G=自然, K=統合, M=核心素養, L=通識資訊素養, 3=敘事表達/大學國文, N=外國語文)
            fetch_syllabus: 是否抓取課程大綱 (預設 True)
            output_dir: 輸出目錄名稱，相對於 data/ (預設 'gene_courses')
        """
        # 載入環境變數
        load_dotenv()

        self.year = year
        self.subject = subject
        self.fetch_syllabus = fetch_syllabus

        # 設定輸出路徑
        project_root = Path(__file__).parent.parent
        self.data_dir = project_root / "data" / output_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.data_dir / f"ge_courses_{year}.json"

        # 設定 requests session
        self.session = requests.Session()
        self.session.headers.update({
            'user-agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36')
        })
        self.session.cookies.set('stud_pass', '1493')

        # 通識課程查詢 API URL
        self.api_url = 'https://onepiece.nchu.edu.tw/cofsys/plsql/crseqry_gene'

        # 請求延遲
        self.request_delay = float(os.getenv('REQUEST_DELAY', 0.3))
        self.syllabus_delay = float(os.getenv('SYLLABUS_DELAY', 0.5))

    def run(self) -> List[Dict]:
        """執行爬蟲，抓取通識課程"""
        logger.info("=" * 50)
        logger.info(f"開始抓取學年期 {self.year} 的通識課程...")
        logger.info("=" * 50)

        courses = self._fetch_gene_courses()

        if not courses:
            logger.warning('未抓取到任何課程')
            return []

        # 去重（根據選課號碼）
        seen = set()
        unique_courses = []
        for c in courses:
            if c['選課號碼'] not in seen:
                seen.add(c['選課號碼'])
                unique_courses.append(c)

        logger.info(f'共抓取 {len(unique_courses)} 筆不重複課程')

        # 抓取課程大綱
        if self.fetch_syllabus:
            logger.info("開始抓取課程大綱...")
            unique_courses = self._fetch_all_syllabus(unique_courses)

        # 儲存資料
        self._save_data(unique_courses)

        logger.info("=" * 50)
        logger.info(f"爬蟲完成! 共抓取 {len(unique_courses)} 筆課程")
        logger.info("=" * 50)

        return unique_courses

    def _fetch_gene_courses(self) -> List[Dict]:
        """抓取通識課程，subject=all 時會分次查詢再合併"""
        if self.subject == 'all':
            all_courses = []
            for subj in ALL_SUBJECT_QUERIES:
                logger.info(f'查詢類別: {subj} ({GENE_SUBJECTS.get(subj, subj)})')
                courses = self._fetch_single_subject(subj)
                logger.info(f'  取得 {len(courses)} 筆')
                all_courses.extend(courses)
                time.sleep(self.request_delay)
            return all_courses
        else:
            return self._fetch_single_subject(self.subject)

    def _fetch_single_subject(self, subject: str) -> List[Dict]:
        """查詢單一類別的通識課程"""
        data = {
            'p_check': '1',
            'p_subject': subject,
            'p_year': self.year,
            'p_group': '',
            'p_lang': '',
            'p_crsName': '',
            'p_teacher': '',
            'p_week': '',
            'p_mtg': '',
            'p_emi': '',
            'p_serial_no': ''
        }

        response = self.session.post(self.api_url, data=data)

        soup = BeautifulSoup(response.text, 'html.parser')

        tables = soup.find_all('table')
        if len(tables) < 21:
            logger.warning(f'警告: 找不到課程資料表格 (僅找到 {len(tables)} 個表格)')
            return []

        # 主資料表在第 20 個 table (0-indexed)
        main_table = tables[20]
        rows = main_table.find_all('tr')

        courses = []

        # 根據第一筆資料的 td 數量判斷格式
        # EFGKM: 15 欄（含領域、學群），header 2 行
        # L/3/N: 12 欄（無領域、學群），header 1 行
        first_data_row = None
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 12:
                first_data_row = tds
                break

        if not first_data_row:
            return []

        is_short_format = len(first_data_row) < 15
        fields = FIELDS_12 if is_short_format else FIELDS_15
        skip_rows = 1 if is_short_format else 2

        for row in rows[skip_rows:]:
            tds = row.find_all('td')

            if len(tds) < len(fields):
                continue

            # 短格式先補上領域和學群，確保 key 順序一致
            course = {}
            if is_short_format:
                course['領域'] = SUBJECT_DOMAIN_MAP.get(subject, subject)
                course['學群'] = ''
            for idx, field_name in fields:
                course[field_name] = tds[idx].get_text(strip=True)

            # 提取課程大綱 URL
            # EFGKM: 選課號碼在 td[2]，L/3/N: 選課號碼在 td[0]
            serial_idx = 0 if is_short_format else 2
            syllabus_link = tds[serial_idx].find('a')
            if syllabus_link and syllabus_link.get('href'):
                course['課程大綱URL'] = 'https://onepiece.nchu.edu.tw/cofsys/plsql/' + \
                    syllabus_link['href']
            else:
                course['課程大綱URL'] = ''

            # 提取上課教室 URL
            classroom_idx = 5 if is_short_format else 7
            classroom_link = tds[classroom_idx].find('a')
            if classroom_link and classroom_link.get('href'):
                course['上課教室URL'] = classroom_link['href']
            else:
                course['上課教室URL'] = ''

            courses.append(course)

        return courses

    def _fetch_all_syllabus(self, courses: List[Dict]) -> List[Dict]:
        """為所有課程抓取課程大綱"""
        total = len(courses)

        for i, course in enumerate(courses):
            syllabus_url = course.get('課程大綱URL', '')

            if not syllabus_url:
                course['課程大綱'] = {}
                continue

            try:
                response = self.session.get(syllabus_url)
                syllabus_data = parse_syllabus(response.text)
                course['課程大綱'] = syllabus_data

                if (i + 1) % 50 == 0:
                    logger.info(f'課程大綱進度: [{i+1}/{total}]')

                time.sleep(self.syllabus_delay)

            except Exception as e:
                course['課程大綱'] = {}
                logger.warning(
                    f'課程大綱抓取失敗 [{i+1}/{total}] {course["科目名稱"]}: {e}')

        logger.info(f'課程大綱抓取完成: {total} 筆')
        return courses

    def _save_data(self, data: List[Dict]):
        """儲存資料為 JSON 檔案"""
        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(data),
                "year": self.year,
                "subject": self.subject,
                "subject_name": GENE_SUBJECTS.get(self.subject, self.subject),
                "data_source": self.api_url,
                "description": "中興大學通識課程資料，可至上方網址進行更詳細的查詢"
            },
            "data": data
        }

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f'資料已儲存至: {self.output_path}')

    @staticmethod
    def get_available_years() -> List[str]:
        """取得所有可用的學年期"""
        return YEARS

    @staticmethod
    def get_available_subjects() -> Dict[str, str]:
        """取得所有可用的通識類別"""
        return GENE_SUBJECTS

    @staticmethod
    def print_available_options():
        """印出所有可用的選項"""
        print('可用的學年期:')
        for code in YEARS[:10]:
            print(f'  {code}')
        print(f'  ... (共 {len(YEARS)} 個)')

        print('\n通識類別:')
        for code, name in GENE_SUBJECTS.items():
            print(f'  {code}: {name}')
