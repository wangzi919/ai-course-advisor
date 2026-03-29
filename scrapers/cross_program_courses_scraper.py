#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨領域學程課程爬蟲

抓取中興大學跨領域學程課程資料，包含課程大綱。

使用方式:
    scraper = CrossProgramCoursesScraper(year='1142')
    scraper.run()  # 抓取指定學年期的所有跨領域學程課程

環境變數設定 (.env):
    USER_AGENT: 瀏覽器 User-Agent (選填)
    REQUEST_DELAY: 請求間隔秒數 (選填，預設 0.3)
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .syllabus_parser import parse_syllabus

logger = logging.getLogger(__name__)


# 學制
CAREERS = {
    'U': '大學部跨領域學程',
    'G': '研究生跨領域學程',
    'E': '教育學程',
}

# 學分學程 (大學部)
PROGRAMS_U = {
    '19': '永續環境學分學程',
    '19-1': '永續環境微學分學程',
    '2': '食品加工與管理學程',
    '21': '日本與亞太區域研究學分學程',
    '23': '創業學分學程',
    '23-1': '創業微學分學程',
    '26': '農場場長學分學程',
    '26-1': '農場場長微學分學程',
    '27': '資料科學學程',
    '28': '廢棄物利用之循環經濟學分學程',
    '28-1': '廢棄物利用之循環經濟微學分學程',
    '30': '畜牧場智慧管理學分學程',
    '30-1': '畜牧場智慧管理微學分學程',
    '31': '興創智慧學分學程',
    '31-1': '興創智慧微學分學程',
    '35': '華語教學學程',
    '36': '教育大數據學分學程',
    '36-1': '教育大數據微學分學程',
    '37': '食品安全智慧管理學分學程',
    '37-1': '食品安全智慧管理微學分學程',
    '38': '食農教育學分學程',
    '38-1': '食農教育微學分學程',
    '39': '半導體元件整合學分學程',
    '39-1': '半導體元件整合微學分學程',
    '40': '動物福祉學分學程',
    '41-1': '地方行銷暨運動觀光微學分學程',
    '42-1': '「精準醫學」跨領域科技微學分學程',
    '43-1': '生技創新創業微學分學程',
    '46': '人工智慧探索應用學分學程',
    '47': '醫學人文的跨領域實踐學分學程',
    '47-1': '醫學人文的跨領域實踐微學分學程',
    '48': 'AI治理與永續發展學分學程',
    '49': '智慧計算應用學分學程',
    '49-1': '智慧計算應用微學分學程',
    '50': 'AI導向健康醫學跨領域學分學程',
    '51-1': '動物科學產業微學分學程',
    '52': '流域整合治理與社會共融學程',
    '53': '企業實習與產業接軌微學分學程',
    '53-1': '企業實習與產業接軌微學分學程',
    '54': '人工智慧工業應用學分學程',
    '55': '人工智慧自然語言技術學分學程',
    '56': '人工智慧視覺技術學分學程',
    'B': '植物生物科技學程',
    'L': '環境生物科技學程',
    'O': '防災科技學分學程',
    'O-1': '防災科技微學分學程',
    'V': '數位人文與資訊應用學程',
    'V-1': '數位人文與資訊應用微學程',
}

# 學分學程 (研究生)
PROGRAMS_G = {
    '24': '生物科技產學合作學程',
    '25': '生技產業管理暨創業碩士學分學程',
    '29': '亞洲與中國研究碩士學分學程(全英語授課)',
    '32': '獸醫科學學分學程(全英語學程)',
    '33': '管理理論與實務碩士學分學程(全英語學程)',
    '34': '生命科學學分學程(全英語學程)',
    '44': '資料生物學碩士學分學程',
    '45': '生命工程跨領域碩士學分學程',
}

# 可用學年期
YEARS = [
    '1142', '1141', '1132', '1131', '1122', '1121', '1112', '1111',
    '1102', '1101', '1092', '1091', '1082', '1081', '1072', '1071',
    '1062', '1061', '1052', '1051', '1042', '1041', '1032', '1031',
    '1022', '1021', '1012', '1011', '1002', '1001', '0992', '0991',
    '0982', '0981', '0972', '0971', '0962', '0961', '0952', '0951',
    '0942', '0941',
]


class CrossProgramCoursesScraper:
    """跨領域學程課程爬蟲"""

    def __init__(
        self,
        year: str = '1142',
        career: str = 'U',
        program: Optional[str] = None,
        fetch_syllabus: bool = True,
        output_dir: str = 'courses/all_cross_program_courses_syllabi',
    ):
        """
        初始化爬蟲

        Args:
            year: 學年期代碼 (如: 1142)
            career: 學制 (U=大學部, G=研究生, E=教育學程)
            program: 學程代碼 (如: 19, 27)，不指定則抓取所有學程
            fetch_syllabus: 是否抓取課程大綱 (預設 True)
            output_dir: 輸出目錄名稱，相對於 data/ (預設 'cross_program_courses')
        """
        # 載入環境變數
        load_dotenv()

        self.year = year
        self.career = career
        self.program = program
        self.fetch_syllabus = fetch_syllabus

        # 設定輸出路徑 (教育學程使用獨立目錄)
        project_root = Path(__file__).parent.parent
        if career == 'E':
            self.data_dir = project_root / "data" / "courses" / "all_education_courses_syllabi"
        else:
            self.data_dir = project_root / "data" / output_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 根據參數決定輸出檔名 (教育學程不需要 career 後綴)
        if career == 'E':
            self.output_path = self.data_dir / f"cross_{year}.json"
        elif program:
            self.output_path = self.data_dir / f"cross_{year}_{career}_{program}.json"
        else:
            self.output_path = self.data_dir / f"cross_{year}_{career}.json"

        # 設定 requests session
        self.session = requests.Session()
        self.session.headers.update({
            'user-agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36')
        })

        # 跨領域學程查詢 API URL
        self.api_url = 'https://onepiece.nchu.edu.tw/cofsys/plsql/crseqry_m25'

        # 請求延遲
        self.request_delay = float(os.getenv('REQUEST_DELAY', 0.3))
        self.syllabus_delay = float(os.getenv('SYLLABUS_DELAY', 0.5))

    def run(self) -> List[Dict]:
        """執行爬蟲，抓取跨領域學程課程"""
        logger.info("=" * 50)
        logger.info(f"開始抓取學年期 {self.year} 的跨領域學程課程 (學制: {CAREERS.get(self.career, self.career)})...")
        logger.info("=" * 50)

        if self.program:
            # 只抓取單一學程
            programs = PROGRAMS_U if self.career == 'U' else PROGRAMS_G
            program_name = programs.get(self.program, self.program)
            courses = self._fetch_cross_program_courses(self.program)
            for c in courses:
                c['學程代碼'] = self.program
                c['學程名稱'] = program_name
        else:
            # 抓取所有學程
            courses = self._fetch_all_programs()

        if not courses:
            logger.warning('未抓取到任何課程')
            return []

        # 去重（根據選課號碼）
        seen = set()
        unique_courses = []
        for c in courses:
            serial = c.get('選課號碼', '')
            if serial and serial not in seen:
                seen.add(serial)
                unique_courses.append(c)
            elif not serial:
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

    def _fetch_all_programs(self) -> List[Dict]:
        """抓取指定學制的所有學程課程"""
        if self.career == 'E':
            # 教育學程不需要遍歷學程，直接抓取
            logger.info('  抓取教育學程...')
            courses = self._fetch_cross_program_courses()
            for c in courses:
                c['學程代碼'] = 'E'
                c['學程名稱'] = '教育學程'
            logger.info(f'    取得 {len(courses)} 筆課程')
            return courses

        programs = PROGRAMS_U if self.career == 'U' else PROGRAMS_G

        all_courses = []
        for program_code, program_name in programs.items():
            logger.info(f'  抓取 {program_name} ({program_code})...')
            courses = self._fetch_cross_program_courses(program_code)
            for c in courses:
                c['學程代碼'] = program_code
                c['學程名稱'] = program_name
            all_courses.extend(courses)
            logger.info(f'    取得 {len(courses)} 筆課程')
            time.sleep(self.request_delay)

        return all_courses

    def _fetch_cross_program_courses(self, program: Optional[str] = None) -> List[Dict]:
        """抓取跨領域學程課程"""
        if self.career == 'E':
            # 教育學程：v_check=1，只需要 p_year
            data = {
                'p_year': self.year,
                'v_check': '1',
            }
        else:
            # 跨領域學程：v_check=2
            data = {
                'p_year2': self.year,
                'p_career': self.career,
                'p_cp': program or self.program,
                'v_check': '2',
            }

        response = self.session.post(self.api_url, data=data)

        soup = BeautifulSoup(response.text, 'html.parser')

        tables = soup.find_all('table')
        if len(tables) < 1:
            logger.warning(f'警告: 找不到課程資料表格 (僅找到 {len(tables)} 個表格)')
            return []

        # 尋找含有課程資料的表格 (通常有選課號碼欄位)
        main_table = None
        for table in tables:
            headers = table.find_all('th')
            header_text = ' '.join([h.get_text(strip=True) for h in headers])
            if '選課號碼' in header_text or '科目名稱' in header_text:
                main_table = table
                break

        if not main_table:
            # 嘗試用索引找到表格 (可能在不同位置)
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) > 2:
                    first_row_text = rows[0].get_text()
                    if '選課號碼' in first_row_text or '科目名稱' in first_row_text:
                        main_table = table
                        break

        if not main_table:
            return []

        rows = main_table.find_all('tr')
        courses = []

        # 解析表頭以確定欄位位置
        header_row = rows[0] if rows else None
        if not header_row:
            return []

        headers = header_row.find_all(['th', 'td'])
        header_names = [h.get_text(strip=True) for h in headers]

        # 動態建立欄位索引 (清理表頭名稱中的註釋)
        field_indices = {}
        for idx, name in enumerate(header_names):
            # 移除括號中的註釋，如 "選課號碼(註4)" -> "選課號碼"
            clean_name = re.sub(r'\(註\d+\)', '', name).strip()
            field_indices[clean_name] = idx

        # 跳過 header 行
        data_rows = rows[1:] if len(rows) > 1 else []

        for row in data_rows:
            tds = row.find_all('td')

            if len(tds) < 3:
                continue

            course = {}

            # 根據表頭動態解析欄位 (排除不需要的欄位)
            exclude_fields = {'可加選餘額'}
            for field_name, idx in field_indices.items():
                if idx < len(tds) and field_name not in exclude_fields:
                    course[field_name] = tds[idx].get_text(strip=True)

            # 提取課程大綱 URL (在選課號碼欄位)
            serial_idx = field_indices.get('選課號碼', -1)
            if serial_idx >= 0 and serial_idx < len(tds):
                syllabus_link = tds[serial_idx].find('a')
                if syllabus_link and syllabus_link.get('href'):
                    href = syllabus_link['href']
                    if not href.startswith('http'):
                        href = 'https://onepiece.nchu.edu.tw/cofsys/plsql/' + href
                    course['課程大綱URL'] = href
                else:
                    course['課程大綱URL'] = ''

            # 提取上課教室 URL
            classroom_idx = field_indices.get('上課教室', -1)
            if classroom_idx >= 0 and classroom_idx < len(tds):
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
                course_name = course.get('科目名稱', course.get('課程名稱', '未知'))
                logger.warning(f'課程大綱抓取失敗 [{i+1}/{total}] {course_name}: {e}')

        logger.info(f'課程大綱抓取完成: {total} 筆')
        return courses

    def _save_data(self, data: List[Dict]):
        """儲存資料為 JSON 檔案"""
        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(data),
                "year": self.year,
                "career": self.career,
                "career_name": CAREERS.get(self.career, self.career),
                "program": self.program,
                "data_source": self.api_url,
                "include_syllabus": self.fetch_syllabus
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
    def get_available_careers() -> Dict[str, str]:
        """取得所有可用的學制"""
        return CAREERS

    @staticmethod
    def get_available_programs(career: str = 'U') -> Dict[str, str]:
        """取得指定學制的所有學程"""
        if career == 'U':
            return PROGRAMS_U
        elif career == 'G':
            return PROGRAMS_G
        else:
            return {}

    @staticmethod
    def print_available_options():
        """印出所有可用的選項"""
        print('可用的學年期:')
        for code in YEARS[:10]:
            print(f'  {code}')
        print(f'  ... (共 {len(YEARS)} 個)')

        print('\n學制:')
        for code, name in CAREERS.items():
            print(f'  {code}: {name}')

        print('\n大學部學程:')
        for code, name in PROGRAMS_U.items():
            print(f'  {code}: {name}')

        print('\n研究生學程:')
        for code, name in PROGRAMS_G.items():
            print(f'  {code}: {name}')
