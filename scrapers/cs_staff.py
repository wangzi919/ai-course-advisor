#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學資訊工程學系行政人員資料"""

import logging
import re
from typing import List, Dict
from pathlib import Path
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class CSStaffScraper(BaseScraper):
    """資訊工程學系行政人員資料爬蟲"""

    def __init__(self):
        """初始化爬蟲"""
        super().__init__(
            source_url="https://www.cs.nchu.edu.tw/v4/#administration",
            output_filename="cs_staff.json",
            data_dir="staff/cs"
        )

        # HTML cache 路徑 (在 staff/cache 目錄下)
        staff_dir = self.data_dir.parent  # 從 data/staff/cs 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "cs_staff_cache.html"

    def scrape(self) -> str:
        """爬取行政人員頁面（支援 HTML cache）"""
        # 檢查是否有快取的 HTML
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            try:
                with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"讀取快取失敗: {e}，將重新爬取")

        # 沒有快取，進行爬取
        html = self.fetch_page(self.source_url)
        if not html:
            logger.error("無法取得行政人員頁面")
            return ""

        # 儲存 HTML 快取
        try:
            with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML 已快取至: {self.html_cache_path}")
        except Exception as e:
            logger.warning(f"儲存 HTML 快取失敗: {e}")

        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """解析行政人員資料"""
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []

        # 找到所有人員資料區塊 (每個 col-xs-12 col-md-6 是一個職員)
        staff_divs = soup.find_all('div', class_='col-xs-12 col-md-6')

        logger.info(f"找到 {len(staff_divs)} 個行政人員區塊")

        for staff_div in staff_divs:
            # 檢查是否是註解掉的人員（HTML 註解）
            if staff_div.parent.name == 'comment':
                logger.debug("跳過註解掉的人員資料")
                continue

            staff_data = self._extract_staff_info(staff_div)
            if staff_data and staff_data['name']:
                staff_list.append(staff_data)

        return staff_list

    def _extract_staff_info(self, staff_div) -> Dict:
        """從 staff div 提取行政人員資訊"""
        staff_info = {
            'name': '',
            'position': '',
            'department': '資訊工程學系',
            'phone': '',
            'email': '',
            'responsibilities': ''
        }

        try:
            table = staff_div.find('table')
            if not table:
                logger.warning("未找到 table 元素")
                return staff_info

            rows = table.find_all('tr')

            # 第一列：姓名和職稱
            if len(rows) > 0:
                first_row = rows[0]
                h4 = first_row.find('h4')
                h5 = first_row.find('h5')

                if h4:
                    # 提取姓名 (移除 <b> 標籤)
                    name_tag = h4.find('b')
                    if name_tag:
                        staff_info['name'] = name_tag.get_text(strip=True)

                if h5:
                    # 提取職稱 (移除前面的 " / " 和 <b> 標籤)
                    position_tag = h5.find('b')
                    if position_tag:
                        position_text = position_tag.get_text(strip=True)
                        # 移除前面的 " / "
                        staff_info['position'] = position_text.replace('/', '').strip()

            # 其他列：電話、信箱、業務職掌
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value_cell = cells[1]

                    if '連絡電話' in label:
                        staff_info['phone'] = value_cell.get_text(strip=True)
                    elif '電子信箱' in label:
                        email_link = value_cell.find('a')
                        if email_link:
                            email = email_link.get_text(strip=True)
                            staff_info['email'] = email
                    elif '業務職掌' in label:
                        staff_info['responsibilities'] = value_cell.get_text(strip=True)

            logger.debug(f"解析職員: {staff_info['name']} - {staff_info['position']}")

        except Exception as e:
            logger.error(f"解析職員資料時發生錯誤: {e}")

        return staff_info
