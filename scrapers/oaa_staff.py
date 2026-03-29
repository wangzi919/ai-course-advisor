#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學教務處職員資料"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict
from pathlib import Path
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class OAAStaffScraper(BaseScraper):
    """教務處職員資料爬蟲（支援多單位）"""

    def __init__(self, unit_name="註冊組", unit_code="rs", staff_url="https://oaa.nchu.edu.tw/zh-tw/rs-staff"):
        """
        初始化爬蟲

        Args:
            unit_name: 單位名稱（例如：註冊組、課務組），用於 JSON 內容
            unit_code: 單位代碼（例如：rs、course），用於檔案命名
            staff_url: 業務職掌頁面 URL
        """
        self.unit_name = unit_name
        self.unit_code = unit_code

        super().__init__(
            source_url=staff_url,
            output_filename=f"oaa_staff_{unit_code}.json",
            data_dir="staff/oaa",
            enable_hot_reload=False  # 停用個別單位的熱重載，統一在 unify_oaa_staff.py 執行
        )
        self.base_url = "https://oaa.nchu.edu.tw"
        self._location = ""

        # HTML cache 路徑 (在 staff/cache 目錄下)
        staff_dir = self.data_dir.parent  # 從 data/staff/oaa 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / f"oaa_staff_{unit_code}_cache.html"

    def force_update(self):
        """強制更新資料（清除 HTML 快取後重新爬取）"""
        logger.info("強制更新模式")

        # 清除 HTML 快取
        if self.html_cache_path.exists():
            try:
                self.html_cache_path.unlink()
                logger.info(f"已清除 HTML 快取: {self.html_cache_path}")
            except Exception as e:
                logger.warning(f"清除 HTML 快取失敗: {e}")

        return self.run()

    def scrape(self) -> str:
        """爬取職員頁面（支援 HTML cache）"""
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
            logger.error("無法取得職員頁面")
            return ""

        # 儲存 HTML 快取
        try:
            with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML 已快取至: {self.html_cache_path}")
        except Exception as e:
            logger.warning(f"儲存 HTML 快取失敗: {e}")

        return html

    def _extract_location(self, html: str) -> str:
        """從頁面 footer-group 提取當前單位的位置"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            footer = soup.find('div', class_='footer-group')
            if not footer:
                return ''
            for item in footer.find_all('div', class_='group-item'):
                dt = item.find('dt')
                if dt and dt.get_text(strip=True) == self.unit_name:
                    dd = item.find('dd')
                    if dd:
                        a = dd.find('a')
                        text = a.get_text(strip=True) if a else dd.get_text(strip=True)
                        m = re.search(r'（([^）]+)）', text)
                        return m.group(1) if m else ''
        except Exception as e:
            logger.warning(f'提取位置失敗: {e}')
        return ''

    def parse(self, raw_data: str) -> List[Dict]:
        """解析職員資料"""
        if not raw_data:
            return []

        self._location = self._extract_location(raw_data)
        logger.info(f'{self.unit_name} 位置: {self._location}')

        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []

        # 找到所有職員資料區塊 (每個 group-item 是一個職員)
        group_items = soup.find_all('div', class_='group-item')

        logger.info(f"找到 {len(group_items)} 個職員區塊")

        for item in group_items:
            staff_data = self._extract_staff_info(item)
            if staff_data and staff_data['name']:
                staff_list.append(staff_data)

        return staff_list

    def _parse_staff_sections(self, content_area) -> List[Dict]:
        """解析職員資料區塊（已棄用，改用 parse 中的邏輯）"""
        # 此方法已不再使用
        pass

    def _extract_staff_info(self, group_item) -> Dict:
        """從 group-item div 提取職員資訊"""
        staff_info = {
            'name': '',
            'department': f'教務處{self.unit_name}',
            'phone': '',
            'email': '',
            'deputy': '',
            'responsibilities': ''
        }

        try:
            # 提取姓名和職稱 (在 h2.title.t02 中，合併顯示)
            h2_element = group_item.find('h2', class_='title')
            if h2_element:
                # 取得完整的姓名+職稱
                name_text = h2_element.get_text(strip=True)
                small_element = h2_element.find('small')
                if small_element:
                    position = small_element.get_text(strip=True)
                    # 組合成 "姓名 職稱" 格式
                    small_element.decompose()
                    base_name = h2_element.get_text(strip=True)
                    staff_info['name'] = f"{base_name} {position}"
                else:
                    staff_info['name'] = name_text

            # 提取聯絡資訊 (在 item-inner inner01 的 ul > li 中)
            inner01 = group_item.find('div', class_='inner01')
            if inner01:
                list_items = inner01.find_all('li')
                for li in list_items:
                    label_elem = li.find('h3', class_='label')
                    text_elem = li.find('div', class_='text')

                    if label_elem and text_elem:
                        label = label_elem.get_text(strip=True)
                        # 對於 email，優先取 <a> 標籤的內容，否則取 div 的文字
                        if 'mail' in label.lower():
                            a_elem = text_elem.find('a')
                            value = a_elem.get_text(strip=True) if a_elem else text_elem.get_text(strip=True)
                        else:
                            value = text_elem.get_text(strip=True)

                        # 根據標籤名稱存入對應欄位
                        if '電話' in label:
                            staff_info['phone'] = value
                        elif 'mail' in label.lower():
                            staff_info['email'] = value
                        elif '職務代理' in label:
                            staff_info['deputy'] = value

            # 提取業務職掌 (在 item-inner inner02 的 dl > dd 中)
            inner02 = group_item.find('div', class_='inner02')
            if inner02:
                dd_elements = inner02.find_all('dd')
                responsibilities_list = []
                for dd in dd_elements:
                    responsibility = dd.get_text(strip=True)
                    if responsibility:
                        responsibilities_list.append(f"- {responsibility}")

                # 將列表轉換成字串，用換行符號區隔
                if responsibilities_list:
                    staff_info['responsibilities'] = '\n'.join(responsibilities_list)

        except Exception as e:
            logger.error(f"解析職員資訊時發生錯誤: {e}")

        return staff_info if staff_info['name'] else None

    def save_data(self, data: List[Dict]) -> None:
        """儲存資料並加入 location 到 metadata"""
        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(data),
                "data_source": self.source_url,
                "unit_name": self.unit_name,
                "unit_code": self.unit_code,
                "location": self._location,
            },
            "data": data,
        }

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"資料已儲存至: {self.output_path} (location: {self._location})")
