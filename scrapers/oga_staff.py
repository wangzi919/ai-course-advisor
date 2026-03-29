#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學總務處職員資料"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict
from pathlib import Path
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class OGAStaffScraper(BaseScraper):
    """總務處職員資料爬蟲（支援多單位）"""

    def __init__(self, unit_name="處本部", unit_code="home", staff_url="https://oga.nchu.edu.tw/unit-job/mid/14", location_url=""):
        """
        初始化爬蟲

        Args:
            unit_name: 單位名稱（例如：處本部、事務組），用於 JSON 內容
            unit_code: 單位代碼（例如：home、business），用於檔案命名
            staff_url: 業務職掌頁面 URL
            location_url: 單位介紹頁面 URL，用於爬取地點資訊
        """
        self.unit_name = unit_name
        self.unit_code = unit_code
        self.location_url = location_url
        self.location = ""

        super().__init__(
            source_url=staff_url,
            output_filename=f"oga_staff_{unit_code}.json",
            data_dir="staff/oga"
        )
        self.base_url = "https://oga.nchu.edu.tw"

        # HTML cache 路徑 (在 staff/cache 目錄下)
        staff_dir = self.data_dir.parent  # 從 data/staff/oga 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / f"oga_staff_{unit_code}_cache.html"

    def _fetch_location(self) -> str:
        """從單位介紹頁面爬取地點資訊"""
        if not self.location_url:
            return ""
        html = self.fetch_page(self.location_url)
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        addr_li = soup.find('li', class_='icon-addr')
        if addr_li:
            return addr_li.get_text(strip=True)
        return ""

    def save_data(self, data: List[Dict]):
        """覆寫 save_data，在 metadata 加入 location"""
        if self.location_url and not self.location:
            self.location = self._fetch_location()
            if self.location:
                logger.info(f"地點: {self.location}")

        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(data),
                "data_source": self.source_url,
                "location": self.location
            },
            "data": data
        }

        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"資料已儲存至: {self.output_path}")
            logger.info(f"Metadata - 最後更新: {result['metadata']['last_updated']}, 總數: {result['metadata']['total_count']}")
            if self.enable_hot_reload:
                self._trigger_hot_reload()
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {str(e)}")

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

    def parse(self, raw_data: str) -> List[Dict]:
        """解析職員資料"""
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []

        # 找到所有職員資料區塊 (每個 div.item 是一個職員)
        items = soup.find_all('div', class_='item')

        logger.info(f"找到 {len(items)} 個職員區塊")

        for item in items:
            staff_data = self._extract_staff_info(item)
            if staff_data and staff_data['name']:
                staff_list.append(staff_data)

        return staff_list

    def _extract_staff_info(self, item) -> Dict:
        """從 item div 提取職員資訊"""
        staff_info = {
            'name': '',
            'department': f'總務處{self.unit_name}',
            'phone': '',
            'email': '',
            'deputy': '',
            'responsibilities': ''
        }

        try:
            # 提取姓名和職稱 (在 div.head > h2 中)
            head_div = item.find('div', class_='head')
            if head_div:
                h2_tag = head_div.find('h2')
                if h2_tag:
                    # 取得姓名
                    name = h2_tag.get_text(strip=True)
                    # 分離 <small> 標籤中的職稱
                    small_tag = h2_tag.find('small')
                    if small_tag:
                        position = small_tag.get_text(strip=True)
                        small_tag.decompose()  # 移除 small 標籤
                        base_name = h2_tag.get_text(strip=True)
                        staff_info['name'] = f"{base_name} {position}"
                    else:
                        staff_info['name'] = name

            # 提取聯絡資訊 (在 div.profile > ul > li 中)
            profile_div = item.find('div', class_='profile')
            if profile_div:
                list_items = profile_div.find_all('li')
                for li in list_items:
                    title_h3 = li.find('h3', class_='title')
                    text_div = li.find('div', class_='text')

                    if title_h3 and text_div:
                        label = title_h3.get_text(strip=True)

                        # 根據標籤名稱存入對應欄位
                        if '電話' in label:
                            staff_info['phone'] = text_div.get_text(strip=True)
                        elif 'mail' in label.lower() or 'e-mail' in label.lower():
                            # 優先取 <a> 標籤的內容
                            a_tag = text_div.find('a')
                            staff_info['email'] = a_tag.get_text(strip=True) if a_tag else text_div.get_text(strip=True)
                        elif '職務代理' in label:
                            staff_info['deputy'] = text_div.get_text(strip=True)

            # 提取業務職掌 (在 div.business > dl > dd 中)
            business_div = item.find('div', class_='business')
            if business_div:
                dd_elements = business_div.find_all('dd')
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
