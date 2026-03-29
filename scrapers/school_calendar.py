#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學行事曆資料"""

import re
import logging
from typing import List, Dict
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SchoolCalendarScraper(BaseScraper):
    """
    中興大學行事曆爬蟲

    從中興大學官網抓取學年度行事曆資料，包含：
    - 學年度和學期資訊
    - 事件開始和結束日期
    - 事件描述（中英文）
    - 自動分類事件類型
    """

    def __init__(self):
        super().__init__(
            source_url="https://www.nchu.edu.tw/calendar/",
            output_filename="school_calendar.json",
            data_dir="calendar",
            enable_hot_reload=True,
            pm2_services=['claude-mcp-server']
        )
        # HTML 快取路徑（用於開發除錯）
        self.html_cache_path = self.data_dir / "school_calendar_cache.html"

    def scrape(self) -> str:
        """
        爬取行事曆網頁內容

        Returns:
            HTML 字串
        """
        # 檢查是否有快取的 HTML
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                return f.read()

        # 爬取新資料
        html = self.fetch_page(self.source_url)

        # 儲存 HTML 快取
        if html:
            with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML 已快取至: {self.html_cache_path}")

        return html if html else ""

    def parse(self, raw_data: str) -> List[Dict]:
        """
        解析行事曆資料

        Args:
            raw_data: scrape() 回傳的 HTML 內容

        Returns:
            解析後的行事曆事件列表
        """
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        events = []

        # 尋找學年度資訊
        academic_year = None
        current_semester = None

        # 從標題中提取學年度：國立中興大學114學年度行事曆
        title = soup.find('h2', class_='title')
        if title:
            title_text = title.get_text()
            year_match = re.search(r'(\d{3})學年度', title_text)
            if year_match:
                academic_year = int(year_match.group(1))
                logger.info(f"找到學年度: {academic_year}")

        # 尋找所有包含行事曆資料的表格
        tables = soup.find_all('table', class_='MsoNormalTable')

        for table in tables:
            # 查找這個表格前面的學期標題
            # 尋找前一個 h2 標籤來判斷是第幾學期
            prev_h2 = table.find_previous('h2', class_='MsoNormal')
            if prev_h2:
                h2_text = prev_h2.get_text()
                semester_match = re.search(r'第(\d)學期', h2_text)
                if semester_match:
                    current_semester = int(semester_match.group(1))
                    logger.info(f"找到第 {current_semester} 學期")

                # 如果在這個 h2 中也有學年度資訊，更新它
                year_match = re.search(r'(\d{3})學年度', h2_text)
                if year_match:
                    academic_year = int(year_match.group(1))

            rows = table.find_all('tr')
            current_year = None
            current_month = None

            for row in rows:
                cells = row.find_all('td')

                # 檢查第一個 cell 是否包含月份資訊（月次欄位）
                if cells and len(cells) > 0:
                    first_cell_text = cells[0].get_text(strip=True)

                    # 匹配民國年月格式：114年8月
                    year_month_match = re.search(r'(\d{3})年\s*(\d{1,2})月', first_cell_text)
                    if year_month_match:
                        roc_year = int(year_month_match.group(1))
                        current_year = roc_year + 1911  # 轉換為西元年
                        current_month = int(year_month_match.group(2))
                        logger.debug(f"找到月份: {current_year}年{current_month}月")

                # 尋找重要記事欄位（通常是最後一個較寬的欄位）
                for cell in cells:
                    # 檢查是否包含事件內容（通常 width 很大或包含<br>標籤）
                    if cell.find('br') or (cell.get('width') and int(cell.get('width', 0)) > 500):
                        # 獲取該 cell 的完整 HTML
                        cell_html = str(cell)
                        # 用 <br /> 或 <br> 分割事件
                        event_lines = re.split(r'<br\s*/?>|\n', cell_html)

                        for line in event_lines:
                            # 移除 HTML 標籤
                            clean_text = BeautifulSoup(line, 'html.parser').get_text(strip=True)

                            if not clean_text:
                                continue

                            # 匹配日期格式：8/1：事件內容 或 8/1-8/4：事件內容
                            date_match = re.match(r'(\d{1,2})/(\d{1,2})(?:-(\d{1,2})/(\d{1,2}))?[：:]\s*(.+)', clean_text)

                            if date_match and current_year and current_month:
                                # 提取日期資訊
                                start_month = int(date_match.group(1))
                                start_day = int(date_match.group(2))
                                end_month = int(date_match.group(3)) if date_match.group(3) else None
                                end_day = int(date_match.group(4)) if date_match.group(4) else None
                                event_text = date_match.group(5).strip()

                                # 計算正確的年份（處理跨學年情況）
                                start_year = self._calculate_event_year(
                                    current_year, current_month, start_month
                                )

                                try:
                                    # 建立開始和結束日期
                                    start_date_str = f"{start_year}-{start_month:02d}-{start_day:02d}"

                                    # 驗證開始日期
                                    datetime.strptime(start_date_str, "%Y-%m-%d")

                                    # 處理結束日期
                                    end_date_str = None
                                    if end_month and end_day:
                                        # 處理結束日期的年份
                                        end_year = start_year
                                        if end_month < start_month:
                                            # 如果結束月份小於開始月份，表示跨年
                                            end_year = start_year + 1

                                        end_date_str = f"{end_year}-{end_month:02d}-{end_day:02d}"

                                        # 驗證結束日期
                                        datetime.strptime(end_date_str, "%Y-%m-%d")

                                    # 建立學年度-學期格式（例如：114-1）
                                    semester_code = f"{academic_year}-{current_semester}" if academic_year and current_semester else None

                                    event = {
                                        "semester": semester_code,
                                        "start_date": start_date_str,
                                        "end_date": end_date_str,
                                        "event": event_text,
                                        "category": self._categorize_event(event_text)
                                    }
                                    events.append(event)

                                    date_display = f"{start_date_str} 到 {end_date_str}" if end_date_str else start_date_str
                                    logger.debug(f"解析事件: {semester_code} {date_display} - {event_text[:50]}")
                                except ValueError as e:
                                    logger.warning(f"日期解析失敗: {start_date_str}, 錯誤: {e}")

        # 按開始日期排序
        events.sort(key=lambda x: x['start_date'])

        logger.info(f"共解析 {len(events)} 個行事曆事件")
        return events

    def _calculate_event_year(
        self,
        current_year: int,
        current_month: int,
        event_month: int
    ) -> int:
        """
        計算事件的正確年份（處理跨學年情況）

        Args:
            current_year: 當前表格所屬年份
            current_month: 當前表格所屬月份
            event_month: 事件發生的月份

        Returns:
            事件的實際年份

        範例:
            - 在 8 月表格中看到 7 月事件 → 同一年（暑假期間）
            - 在 8 月表格中看到 1-6 月事件 → 下一年（下學期結束）
            - 在 2 月表格中看到 8-12 月事件 → 上一年（上學期開始）
        """
        month_diff = event_month - current_month

        if current_month >= 8:  # 下學期表格（8-12月）
            # 在下學期表格中看到上學期月份
            if event_month <= 7 and month_diff < -1:
                # 月份差距超過1，表示是下一年的事件
                # 例如：在8月看到6月以前的事件
                return current_year + 1
            # 如果是7月（緊鄰8月），是同一年的暑假
            return current_year
        else:  # 上學期表格（1-7月）
            # 在上學期表格中看到下學期月份
            if event_month >= 8:
                # 表示是上一年的事件
                # 例如：在2月看到8-12月的事件
                return current_year - 1
            return current_year

    def _categorize_event(self, event_text: str) -> str:
        """
        根據事件內容自動分類

        Args:
            event_text: 事件描述文字

        Returns:
            事件類別（開學、放假、考試、選課、註冊、畢業、新生、活動、行政、其他）
        """
        if not event_text:
            return "其他"

        # 定義分類關鍵字（按優先順序排列，越具體的分類越前面）
        categories = {
            "開學": ["開學", "學期開始", "開始上課"],
            "放假": ["放假", "假期", "連假", "補假", "調整放假"],
            "考試": ["期中考", "期末考"],
            "選課": ["選課", "加退選", "初選", "網路初選", "網路加退選", "course selection", "add/drop"],
            "註冊": ["註冊", "繳費", "學雜費", "就學貸款", "減免", "payment"],
            "畢業": ["畢業", "學位考試", "論文口試", "離校", "提前畢業", "graduation", "thesis", "dissertation"],
            "新生": ["新生", "freshmen", "New student"],
            "活動": ["運動會", "路跑", "舞蹈", "校慶", "典禮", "慶祝", "演練", "避難"],
            "行政": ["截止", "申請", "繳交", "受理", "轉系", "輔系", "雙主修", "跨域", "學程", "抵免", "停修", "休學"],
        }

        # 依序檢查關鍵字
        for category, keywords in categories.items():
            if any(keyword in event_text for keyword in keywords):
                return category

        return "其他"


if __name__ == "__main__":
    # 測試用
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    scraper = SchoolCalendarScraper()
    scraper.run()
