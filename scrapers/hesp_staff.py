#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學高等教育深耕計畫教職員資料"""

import logging
import re
import json
from typing import List, Dict
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class HESPStaffScraper(BaseScraper):
    """高等教育深耕計畫教職員資料爬蟲"""

    def __init__(self):
        """初始化爬蟲"""
        super().__init__(
            source_url="https://hesp.nchu.edu.tw/staff/",
            output_filename="hesp_staff.json",
            data_dir="staff/rdoffice"  # 與其他研發處單位放在同一目錄
        )

        # HTML cache 路徑 (在 staff/cache 目錄下)
        staff_dir = self.data_dir.parent  # 從 data/staff/rdoffice 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "hesp_staff_cache.html"

        # 各處室位置（由 parse 時解析並儲存）
        self._location = ""

    def _extract_location(self, soup: BeautifulSoup) -> str:
        """從頁面中提取辦公室位置"""
        try:
            match = re.search(r'行政大樓\d+樓', soup.get_text())
            if match:
                location = match.group(0)
                logger.debug(f"找到辦公室位置: {location}")
                return location
        except Exception as e:
            logger.warning(f"提取位置時發生錯誤: {e}")
        return ""

    def save_data(self, data: List[Dict]):
        """覆寫 save_data，在 metadata 中加入 location 欄位"""
        try:
            result = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_count": len(data),
                    "data_source": self.source_url,
                    "location": self._location
                },
                "data": data
            }
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"資料已儲存至: {self.output_path}")
            logger.info(f"Metadata - 最後更新: {result['metadata']['last_updated']}, "
                        f"總數: {result['metadata']['total_count']}, "
                        f"位置: {result['metadata']['location']}")
            if self.enable_hot_reload:
                self._trigger_hot_reload()
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {str(e)}")

    def scrape(self) -> str:
        """爬取教職員頁面（支援 HTML cache）"""
        # 檢查是否有快取的 HTML
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            try:
                with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"讀取快取失敗: {e}，將重新爬取")

        # 沒有快取，進行爬取
        import requests
        try:
            logger.info(f"正在抓取: {self.source_url}")
            response = requests.get(
                self.source_url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            html = response.text
        except Exception as e:
            logger.error(f"抓取失敗 {self.source_url}: {str(e)}")
            return ""

        if not html:
            logger.error("無法取得教職員頁面")
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
        """解析教職員資料"""
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        self._location = self._extract_location(soup)
        staff_list = []

        # 找到所有表格
        tables = soup.find_all('table')
        logger.info(f"找到 {len(tables)} 個表格")

        for table in tables:
            # 找到表格前的標題 (h2)
            section_title = ""
            prev_element = table.find_previous('h2')
            if prev_element:
                section_title = prev_element.get_text(strip=True)
                # 移除可能的 HTML 標籤和多餘空白
                section_title = re.sub(r'<[^>]+>', '', section_title)
                section_title = re.sub(r'\s+', ' ', section_title).strip()

            logger.debug(f"處理表格: {section_title}")

            # 解析表格中的每一行資料
            rows = table.find_all('tr')

            # 跳過標題行（第一行）
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) >= 6:  # 確保有足夠的欄位
                    staff_data = self._extract_staff_from_row(cells, section_title)
                    if staff_data and staff_data['name']:
                        staff_list.append(staff_data)

        logger.info(f"共解析 {len(staff_list)} 位教職員")
        return staff_list

    def _extract_staff_from_row(self, cells, section_title: str) -> Dict:
        """從表格行提取教職員資訊"""
        staff_info = {
            'name': '',
            'unit': '',
            'position': '',
            'department': '研發處高等教育深耕計畫',
            'section': section_title,  # 所屬面向/單位
            'phone': '',
            'email': '',
            'deputy': '',
            'responsibilities': []
        }

        try:
            # 提取姓名 (第1欄)
            if len(cells) > 0:
                name_text = cells[0].get_text(strip=True)
                staff_info['name'] = name_text

            # 提取單位 (第2欄)
            if len(cells) > 1:
                unit_text = cells[1].get_text(strip=True)
                staff_info['unit'] = unit_text

            # 提取職稱 (第3欄)
            if len(cells) > 2:
                position_text = cells[2].get_text(strip=True)
                staff_info['position'] = position_text

            # 提取聯絡方式/電話 (第4欄)
            if len(cells) > 3:
                phone_text = cells[3].get_text(strip=True)
                staff_info['phone'] = phone_text

            # 提取電子信箱 (第5欄)
            if len(cells) > 4:
                email_cell = cells[4]
                # 嘗試從 a 標籤提取 email
                email_link = email_cell.find('a')
                if email_link:
                    email_text = email_link.get_text(strip=True)
                    # 如果是 mailto: 連結，提取完整 email
                    if email_link.get('href') and 'mailto:' in email_link.get('href'):
                        email_text = email_link.get('href').replace('mailto:', '')
                    staff_info['email'] = email_text
                else:
                    staff_info['email'] = email_cell.get_text(strip=True)

                # 補上 @nchu.edu.tw 後綴（如果沒有的話）
                if staff_info['email'] and '@' not in staff_info['email']:
                    staff_info['email'] = f"{staff_info['email']}@nchu.edu.tw"

            # 提取主辦業務 (第6欄)
            if len(cells) > 5:
                business_text = cells[5].get_text(strip=True)
                # 將業務內容按句號或換行分割成列表
                if business_text:
                    # 保持原始格式，不分割
                    staff_info['responsibilities'].append(business_text)

            # 提取代理人 (第7欄，如果有)
            if len(cells) > 6:
                deputy_text = cells[6].get_text(strip=True)
                staff_info['deputy'] = deputy_text

            logger.debug(f"解析職員: {staff_info['name']} - {staff_info['position']} ({staff_info['section']})")

        except Exception as e:
            logger.error(f"解析職員資料時發生錯誤: {e}")

        return staff_info
