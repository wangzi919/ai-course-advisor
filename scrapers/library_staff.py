#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學圖書館職員資料"""

import logging
import re
from typing import List, Dict
from pathlib import Path
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class LibraryStaffScraper(BaseScraper):
    """圖書館職員資料爬蟲（支援多單位）"""

    def __init__(self, unit_name="館長室", unit_code="dean", unit_key="44"):
        """
        初始化爬蟲

        Args:
            unit_name: 單位名稱（例如：館長室、採編組）
            unit_code: 單位代碼（例如：dean、catalog），用於檔案命名
            unit_key: 單位在網址中的 Key 值
        """
        self.unit_name = unit_name
        self.unit_code = unit_code
        self.unit_key = unit_key

        staff_url = f"https://www.lib.nchu.edu.tw/about.php?cID=6&Key={unit_key}"

        super().__init__(
            source_url=staff_url,
            output_filename=f"library_staff_{unit_code}.json",
            data_dir="staff/library"
        )
        self.base_url = "https://www.lib.nchu.edu.tw"

        # HTML cache 路徑 (在 staff/cache 目錄下)
        staff_dir = self.data_dir.parent  # 從 data/staff/library 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / f"library_staff_{unit_code}_cache.html"

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

        # 找到內容區塊
        content_div = soup.find('div', class_='n_d_content')
        if not content_div:
            logger.error("找不到內容區塊")
            return []

        # 1. 提取館長和副館長資料（在 div.col-lg-6 中）
        col_divs = content_div.find_all('div', class_='col-lg-6')
        logger.info(f"找到 {len(col_divs)} 個 col-lg-6 區塊（館長/副館長）")

        for col_div in col_divs:
            staff_data = self._extract_leader_info(col_div)
            if staff_data and staff_data.get('name'):
                staff_list.append(staff_data)

        # 2. 提取表格中的職員資料
        table = content_div.find('table', class_='rwd-table')
        if table:
            rows = table.find_all('tr')
            logger.info(f"找到表格，共 {len(rows)} 行（包含標題行）")

            # 跳過第一行（標題行）
            for row in rows[1:]:
                staff_data = self._extract_table_staff_info(row)
                if staff_data and staff_data.get('name'):
                    staff_list.append(staff_data)

        logger.info(f"{self.unit_name} 共解析出 {len(staff_list)} 筆職員資料")
        return staff_list

    def _extract_leader_info(self, col_div) -> Dict:
        """從 col-lg-6 div 提取館長/副館長資訊"""
        staff_info = {
            'name': '',
            'department': f'圖書館{self.unit_name}',
            'phone': '',
            'email': '',
            'deputy': '',
            'responsibilities': ''
        }

        try:
            # 提取姓名和職稱 (在 h3 標籤中)
            h3_element = col_div.find('h3')
            if h3_element:
                name_text = h3_element.get_text(strip=True)
                # 移除單位名稱，只保留姓名和職稱
                # 例如："國立中興大學圖書館館長 宋慧筠 教授" -> "館長 宋慧筠 教授"
                name_text = name_text.replace('國立中興大學圖書館', '')
                staff_info['name'] = name_text

            # 提取業務內容、email、分機 (在 p 標籤中)
            # 找到第一個非空的 p 標籤
            p_element = None
            for p in col_div.find_all('p'):
                if p.get_text(strip=True):
                    p_element = p
                    break

            if p_element:
                p_text = p_element.get_text()

                # 提取業務內容（使用換行符分隔，支援全形和半形冒號）
                if '業務內容：' in p_text or '業務內容:' in p_text:
                    content_match = re.search(r'業務內容[：:]\s*(.+?)(?:連絡信箱[：:]|$)', p_text, re.DOTALL)
                    if content_match:
                        content = content_match.group(1).strip()
                        # 將換行的業務內容轉換為列表格式
                        responsibilities_lines = []
                        for line in content.split('\n'):
                            line = line.strip()
                            # 過濾掉空行和純數字行
                            if line and not line.isdigit():
                                # 如果已經以數字開頭（如 "1.綜理館務"），則直接加上 "-"
                                if re.match(r'^\d+\.', line):
                                    responsibilities_lines.append(f"- {line}")
                                elif line:  # 其他非空行
                                    responsibilities_lines.append(f"- {line}")
                        if responsibilities_lines:
                            staff_info['responsibilities'] = '\n'.join(responsibilities_lines)

                # 提取 email
                email_link = p_element.find('a', href=lambda x: x and 'mailto:' in x)
                if email_link:
                    # 從 href 屬性獲取 email（更可靠）
                    email = email_link.get('href', '').replace('mailto:', '')
                    if email:
                        staff_info['email'] = email
                    else:
                        staff_info['email'] = email_link.get_text(strip=True)

                # 提取分機
                if '分機號碼：' in p_text or '分機號碼:' in p_text:
                    phone_match = re.search(r'分機號碼[：:]\s*(\d+)', p_text)
                    if phone_match:
                        staff_info['phone'] = phone_match.group(1)

        except Exception as e:
            logger.error(f"解析館長/副館長資訊時發生錯誤: {e}")

        return staff_info if staff_info['name'] else None

    def _extract_table_staff_info(self, row) -> Dict:
        """從表格行提取職員資訊"""
        staff_info = {
            'name': '',
            'department': f'圖書館{self.unit_name}',
            'phone': '',
            'email': '',
            'deputy': '',
            'responsibilities': ''
        }

        try:
            cells = row.find_all('td')
            if len(cells) < 5:
                return None

            # 職稱
            position = cells[0].get_text(strip=True)

            # 承辦人（姓名和 email）
            name_cell = cells[1]
            email_link = name_cell.find('a', href=lambda x: x and 'mailto:' in x)
            if email_link:
                name = email_link.get_text(strip=True)
                staff_info['email'] = email_link.get('href', '').replace('mailto:', '')
            else:
                name = name_cell.get_text(strip=True)

            # 組合職稱和姓名
            staff_info['name'] = f"{name} {position}" if position else name

            # 業務內容
            content_cell = cells[2]
            # 檢查是否有 <ol> 或 <ul> 列表
            ol_element = content_cell.find('ol')
            ul_element = content_cell.find('ul')

            if ol_element or ul_element:
                list_element = ol_element or ul_element
                list_items = list_element.find_all('li')
                responsibilities = [f"- {li.get_text(strip=True)}" for li in list_items if li.get_text(strip=True)]
                staff_info['responsibilities'] = '\n'.join(responsibilities)
            else:
                # 如果沒有列表，直接取文字
                content = content_cell.get_text(strip=True)
                if content:
                    staff_info['responsibilities'] = content

            # 分機
            phone = cells[3].get_text(strip=True)
            staff_info['phone'] = phone

            # 職務代理人
            deputy_cell = cells[4]
            deputy = deputy_cell.get_text(strip=True)
            # 處理換行符號，將 <br> 轉換為文字分隔
            deputy = deputy.replace('\n', ' ').strip()
            staff_info['deputy'] = deputy

        except Exception as e:
            logger.error(f"解析表格職員資訊時發生錯誤: {e}")
            return None

        return staff_info if staff_info['name'] else None
