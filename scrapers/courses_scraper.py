#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系所課程爬蟲

抓取中興大學各系所的課程資料，包含課程大綱。

使用方式:
    scraper = CoursesScraper(year='1142')
    scraper.run()  # 抓取指定學年期的所有課程

環境變數設定 (.env):
    USER_AGENT: 瀏覽器 User-Agent (選填)
    REQUEST_DELAY: 請求間隔秒數 (選填，預設 0.3)
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import urllib3
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 忽略 SSL 憑證驗證警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .nchu_departments import DEPARTMENTS, get_career
from .syllabus_parser import parse_syllabus

logger = logging.getLogger(__name__)




def _fetch_available_years(session: requests.Session) -> Dict[str, str]:
    """從課程查詢頁面動態取得所有可用的學年期及其對應值"""
    url = 'https://onepiece.nchu.edu.tw/cofsys/plsql/crseqry_home'
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    years = {}
    select = soup.find('select', {'name': 'v_year'})
    if select:
        for option in select.find_all('option'):
            value = option.get('value', '')
            text = option.get_text(strip=True)
            if value and text:
                years[text] = value

    return years

# 課程欄位定義
FIELDS = [
    '必選別', '選課號碼', '科目名稱', '先修科目', '全半年',
    '學分數', '上課時數', '實習時數', '上課時間', '實習時間',
    '上課教室', '實習教室', '上課教師', '實習教師', '開課單位',
    '開課人數', '外系人數', '可加選餘額', '授課語言', '備註'
]


class CoursesScraper:
    """系所課程爬蟲"""

    def __init__(
        self,
        year: str = '1142',
        fetch_syllabus: bool = True,
        output_dir: str = 'courses/all_courses_syllabi',
    ):
        """
        初始化爬蟲

        Args:
            year: 學年期代碼 (如: 1142)
            fetch_syllabus: 是否抓取課程大綱 (預設 True)
            output_dir: 輸出目錄名稱，相對於 data/ (預設 'courses')
        """
        # 載入環境變數
        load_dotenv()

        self.year_code = year
        self.fetch_syllabus = fetch_syllabus

        # 設定輸出路徑
        project_root = Path(__file__).parent.parent
        self.data_dir = project_root / "data" / output_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.data_dir / f"courses_{year}.json"

        # 設定 requests session
        self.session = requests.Session()
        self.session.verify = False  # 繞過 SSL 憑證驗證
        self.session.headers.update({
            'user-agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36')
        })

        # 課程查詢 API URL (crseqry_home 支援所有學年期，crseqry_home_now 僅限當學期)
        self.api_url = 'https://onepiece.nchu.edu.tw/cofsys/plsql/crseqry_home'

        # 動態取得學年期對應值
        self._years_cache = None
        self.year_value = self._get_year_value(year)

        # 請求延遲
        self.request_delay = float(os.getenv('REQUEST_DELAY', 0.3))
        self.syllabus_delay = float(os.getenv('SYLLABUS_DELAY', 0.5))

    def _get_years(self) -> Dict[str, str]:
        """取得學年期對照表（帶快取）"""
        if self._years_cache is None:
            logger.info("從課程查詢頁面取得可用學年期...")
            self._years_cache = _fetch_available_years(self.session)
            logger.info(f"取得 {len(self._years_cache)} 個學年期")
        return self._years_cache

    def _get_year_value(self, year_code: str) -> str:
        """取得學年期代碼對應的查詢值"""
        years = self._get_years()
        if year_code not in years:
            available = sorted(years.keys(), reverse=True)[:5]
            raise ValueError(f"學年期 {year_code} 不存在，可用的學年期: {', '.join(available)}...")
        return years[year_code]

    def run(self) -> List[Dict]:
        """執行爬蟲，抓取所有系所課程"""
        logger.info("=" * 50)
        logger.info(f"開始抓取學年期 {self.year_code} 的課程...")
        logger.info("=" * 50)

        all_courses = []
        total = len(DEPARTMENTS)

        for idx, (dept_code, dept_name) in enumerate(DEPARTMENTS):
            try:
                courses = self._fetch_department_courses(dept_code, dept_name)
                all_courses.extend(courses)
                logger.info(f'[{idx+1}/{total}] {dept_code} {dept_name}: {len(courses)} 筆課程')
                time.sleep(self.request_delay)
            except Exception as e:
                logger.error(f'[{idx+1}/{total}] {dept_code} {dept_name}: 錯誤 - {e}')

        # 去重（根據選課號碼）
        seen = set()
        unique_courses = []
        for c in all_courses:
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

    def _fetch_department_courses(self, dept_code: str, dept_name: str) -> List[Dict]:
        """抓取單一系所的課程"""
        career = get_career(dept_code)

        data = {
            'v_year': self.year_value,
            'v_career': career,
            'v_excel': '0',
            'v_dept': dept_code,
            'v_level': '',
            'v_lang': '',
            'v_text': '',
            'v_teach': '',
            'v_week': '',
            'v_mtg': '',
            'v_emi': ''
        }

        response = self.session.post(self.api_url, data=data)

        soup = BeautifulSoup(response.text, 'html.parser')

        courses = []

        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')

            if len(tds) >= 20:
                for i in range(0, len(tds) - 19, 20):
                    cells = tds[i:i+20]

                    first_cell = cells[0].get_text(strip=True)
                    if first_cell not in ['必修', '選修']:
                        continue

                    course = {}
                    for j, field in enumerate(FIELDS):
                        course[field] = cells[j].get_text(strip=True)

                    # 加入系所資訊
                    course['系所代碼'] = dept_code
                    course['系所名稱'] = dept_name

                    # 提取課程大綱 URL (選課號碼欄位，索引 1)
                    syllabus_link = cells[1].find('a')
                    if syllabus_link and syllabus_link.get('href'):
                        course['課程大綱URL'] = syllabus_link['href']
                    else:
                        course['課程大綱URL'] = ''

                    # 提取上課教室 URL (上課教室欄位，索引 10)
                    classroom_link = cells[10].find('a')
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

                if (i + 1) % 100 == 0:
                    logger.info(f'課程大綱進度: [{i+1}/{total}]')

                time.sleep(self.syllabus_delay)

            except Exception as e:
                course['課程大綱'] = {}
                logger.warning(f'課程大綱抓取失敗 [{i+1}/{total}] {course["科目名稱"]}: {e}')

        logger.info(f'課程大綱抓取完成: {total} 筆')
        return courses

    def _save_data(self, data: List[Dict]):
        """儲存資料為 JSON 檔案"""
        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(data),
                "year_code": self.year_code,
                "data_source": self.api_url,
                "include_syllabus": self.fetch_syllabus
            },
            "data": data
        }

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f'資料已儲存至: {self.output_path}')

    def get_available_years(self) -> List[str]:
        """取得所有可用的學年期"""
        return sorted(self._get_years().keys(), reverse=True)

    def print_available_years(self):
        """印出所有可用的學年期"""
        print('可用的學年期:')
        for code in self.get_available_years():
            print(f'  {code}')
