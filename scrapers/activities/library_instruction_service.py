#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學圖書館利用指導課程"""

import logging
import re
from typing import List, Dict

from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper

# 使用標準 logging,讓 run_*.py 的設定統一管理
logger = logging.getLogger(__name__)


class LibraryInstructionScraper(BaseScraper):
    """圖書館利用指導課程爬蟲"""

    def __init__(self):
        super().__init__(
            source_url="https://cal.lib.nchu.edu.tw/",
            output_filename="library_instruction_service.json",
            data_dir="activities",
            enable_hot_reload=False  # 不在此處觸發熱重載，統一由 unify_activities.py 處理
        )

    def scrape(self) -> List[str]:
        """爬取圖書館利用指導課程所有分頁"""
        all_pages_html = []

        # 先抓取第一頁
        logger.info("正在抓取第 1 頁...")
        first_page_html = self.fetch_page(self.source_url)
        if not first_page_html:
            logger.error("無法取得第一頁")
            return []

        all_pages_html.append(first_page_html)

        # 解析分頁數量
        soup = BeautifulSoup(first_page_html, "html.parser")
        page_list = soup.find("div", id="pageList")

        if page_list:
            # 找到所有分頁按鈕
            page_buttons = page_list.find_all("input", class_="pageBtn")
            total_pages = len(page_buttons)
            logger.info(f"找到 {total_pages} 個分頁")

            # 抓取第 2 頁及之後的頁面
            for page_num in range(2, total_pages + 1):
                page_url = f"{self.source_url}?act=&page={page_num}"
                logger.info(f"正在抓取第 {page_num} 頁: {page_url}")
                page_html = self.fetch_page(page_url)
                if page_html:
                    all_pages_html.append(page_html)
                else:
                    logger.warning(f"無法取得第 {page_num} 頁")
        else:
            logger.info("沒有找到分頁元素，只有單一頁面")

        logger.info(f"總共抓取了 {len(all_pages_html)} 個頁面")
        return all_pages_html

    def parse(self, html_list: List[str]) -> List[Dict]:
        """解析圖書館利用指導課程資料（支援多頁）"""
        if not html_list:
            return []

        all_activities = []

        for page_idx, html in enumerate(html_list, 1):
            if not html:
                continue

            logger.info(f"正在解析第 {page_idx} 頁...")
            soup = BeautifulSoup(html, "html.parser")

            table = soup.find("table")
            if not table:
                logger.warning(f"第 {page_idx} 頁找不到活動表格")
                continue

            rows = table.find_all("tr")[1:]  # 跳過標題列
            logger.info(f"第 {page_idx} 頁找到 {len(rows)} 個課程項目")

            page_activities = []
            for row_idx, row in enumerate(rows, 1):
                cells = row.find_all("td")
                if len(cells) >= 6:
                    try:
                        activity_data = self._parse_activity_row(row, cells)
                        if activity_data:
                            page_activities.append(activity_data)
                    except Exception as e:
                        logger.warning(f"第 {page_idx} 頁第 {row_idx} 個課程解析錯誤: {e}")
                        continue

            logger.info(f"第 {page_idx} 頁成功解析 {len(page_activities)} 個課程")
            all_activities.extend(page_activities)

        logger.info(f"總共成功解析 {len(all_activities)} 個課程（來自 {len(html_list)} 個頁面）")
        return all_activities

    def _parse_activity_row(self, row, cells: List) -> Dict:
        """解析單個課程行"""
        title = ""
        content = ""
        activity_cell = cells[3]

        a_tag = activity_cell.find("a")
        if a_tag:
            title = a_tag.get_text(strip=True)
            full_text = activity_cell.get_text(strip=True)
            content = full_text.replace(title, "", 1).strip()
        else:
            title = activity_cell.get_text(strip=True)

        registration_info = ""
        if len(cells) > 6:
            reg_cell = cells[6]
            reg_a_tag = reg_cell.find("a")
            if reg_a_tag:
                registration_info = reg_a_tag.get_text(strip=True)
            else:
                registration_info = reg_cell.get_text(strip=True)

        activity_data = {
            "coid": row.get("coid"),
            "date": cells[0].get_text(strip=True),
            "time": cells[1].get_text(strip=True),
            "target_audience": cells[2].get_text(strip=True),
            "title": title,
            "content": content,
            "instructor": cells[4].get_text(strip=True),
            "location": cells[5].get_text(strip=True),
            "registration_info": registration_info,
        }

        return self._clean_activity_data(activity_data)

    @staticmethod
    def _clean_activity_data(activity_data: Dict) -> Dict:
        """清理和標準化活動資料"""
        for key in ["title", "content", "instructor", "location"]:
            if key in activity_data:
                activity_data[key] = re.sub(r"\s+", " ", activity_data[key]).strip()
        return activity_data