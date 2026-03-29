#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學國際事務處教職員資料"""

import logging
import re
from typing import List, Dict
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import html
import json

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class OIAStaffScraper(BaseScraper):
    """國際事務處教職員資料爬蟲"""

    def __init__(self):
        """初始化爬蟲"""
        super().__init__(
            source_url="https://oia.nchu.edu.tw/index.php/zh/1-1-about-tw/1-1-2-members-tw",
            output_filename="oia_staff.json",
            data_dir="staff/oia"  # 國際處單獨一個目錄
        )

        # HTML cache 路徑 (在 staff/cache 目錄下)
        staff_dir = self.data_dir.parent  # 從 data/staff/oia 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "oia_staff_cache.html"

        # 國際處位置（由 parse 時解析並儲存）
        self._location = ""

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
            html_content = response.text
        except Exception as e:
            logger.error(f"抓取失敗 {self.source_url}: {str(e)}")
            return ""

        if not html_content:
            logger.error("無法取得教職員頁面")
            return ""

        # 儲存 HTML 快取
        try:
            with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"HTML 已快取至: {self.html_cache_path}")
        except Exception as e:
            logger.warning(f"儲存 HTML 快取失敗: {e}")

        return html_content

    def _extract_location(self, soup: BeautifulSoup) -> str:
        """從頁面 footer 中提取國際處辦公室位置"""
        try:
            # 地址在 footer 的 div.g-content 中
            for div in soup.find_all('div', class_='g-content'):
                text = div.get_text()
                if '行政大樓' in text:
                    # 只取「行政大樓X樓」部分
                    match = re.search(r'行政大樓\d+樓', text)
                    if match:
                        location = match.group(0)
                        logger.debug(f"找到國際處位置: {location}")
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
                        f"地址: {result['metadata']['location']}")

            if self.enable_hot_reload:
                self._trigger_hot_reload()
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {str(e)}")

    def parse(self, raw_data: str) -> List[Dict]:
        """解析教職員資料"""
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []
        seen_names = set()  # 用於去重

        # 提取辦公室地址（存入 instance variable，供 save_data 使用）
        self._location = self._extract_location(soup)

        # 找到所有的區塊標題 (h3 和 h5)
        current_section = ""
        current_subsection = ""

        # 遍歷所有相關元素
        for element in soup.find_all(['h3', 'h5', 'p', 'div']):
            # 檢查是否為主區塊標題 (h3)
            if element.name == 'h3' and 'alert-danger' in element.get('class', []):
                section_link = element.find('a')
                if section_link:
                    current_section = section_link.get_text(strip=True)
                    current_subsection = ""
                    logger.debug(f"找到主區塊: {current_section}")

            # 檢查是否為子區塊標題 (h5)
            elif element.name == 'h5':
                current_subsection = element.get_text(strip=True)
                logger.debug(f"找到子區塊: {current_subsection}")

                # 檢查 h5 後面是否有 div.row-fluid (高層人員結構)
                next_div = element.find_next_sibling('div')
                if next_div and 'row-fluid' in next_div.get('class', []):
                    staff_data = self._extract_staff_from_table(
                        next_div,
                        current_section,
                        current_subsection
                    )
                    if staff_data and staff_data.get('name'):
                        # 去重：檢查姓名和組別的組合
                        unique_key = f"{staff_data['name']}|{staff_data['section']}"
                        if unique_key not in seen_names:
                            staff_list.append(staff_data)
                            seen_names.add(unique_key)
                            logger.debug(f"解析高層職員: {staff_data['name']}")

            # 檢查是否為 div.row-fluid（可能沒有前面的 h5 標籤）
            elif element.name == 'div' and 'row-fluid' in element.get('class', []):
                # 檢查是否包含 table（高層人員結構）
                table = element.find('table')
                if table and (table.find('strong') or table.find('b')):
                    # 確認這不是已經處理過的（通過檢查是否前面有 h5）
                    prev_h5 = element.find_previous_sibling('h5')
                    if not prev_h5 or element != prev_h5.find_next_sibling('div'):
                        # 這是一個沒有 h5 標籤的 row-fluid
                        staff_data = self._extract_staff_from_table(
                            element,
                            current_section,
                            current_subsection
                        )
                        if staff_data and staff_data.get('name'):
                            # 去重：檢查姓名和組別的組合
                            unique_key = f"{staff_data['name']}|{staff_data['section']}"
                            if unique_key not in seen_names:
                                staff_list.append(staff_data)
                                seen_names.add(unique_key)
                                logger.debug(f"解析高層職員（無h5）: {staff_data['name']}")

            # 檢查是否為人員資訊 (strong 或 b 標籤包含姓名)
            elif element.name == 'p':
                # 同時檢查 strong 和 b 標籤
                name_tag = element.find('strong') or element.find('b')
                if name_tag:
                    name_text = name_tag.get_text(strip=True)
                    # 過濾掉不是人名的標籤
                    if (name_text and
                        '負責業務' not in name_text and
                        'TOP' not in name_text and
                        ':' not in name_text and  # 過濾掉「負責業務:」等標籤
                        len(name_text) > 1):  # 至少要有2個字符
                        # 嘗試提取完整的人員資訊
                        staff_data = self._extract_staff_info_from_context(
                            element,
                            current_section,
                            current_subsection
                        )
                        if staff_data and staff_data.get('name'):
                            # 去重：檢查姓名和組別的組合
                            unique_key = f"{staff_data['name']}|{staff_data['section']}"
                            if unique_key not in seen_names:
                                staff_list.append(staff_data)
                                seen_names.add(unique_key)
                                logger.debug(f"解析職員: {staff_data['name']}")

        logger.info(f"共解析 {len(staff_list)} 位教職員（去重後）")
        return staff_list

    def _extract_staff_from_table(self, row_fluid_div, section: str, subsection: str) -> Dict:
        """從 table 結構提取高層人員資訊"""
        staff_info = {
            'name': '',
            'position': subsection if subsection else '',
            'department': '國際事務處',
            'section': section,
            'phone': '',
            'fax': '',
            'email': '',
            'website': '',
            'responsibilities': []
        }

        try:
            # 找到 table
            table = row_fluid_div.find('table')
            if not table:
                return staff_info

            # 提取姓名（在 strong 或 b 標籤中，需過濾非人名）
            # 找到所有 strong 和 b 標籤
            name_tags = table.find_all(['strong', 'b'])
            for tag in name_tags:
                name_text = tag.get_text(strip=True)
                # 過濾掉不是人名的標籤
                if (name_text and
                    '負責業務' not in name_text and
                    'TOP' not in name_text and
                    ':' not in name_text and
                    'Email' not in name_text and
                    'Tel' not in name_text and
                    'Fax' not in name_text and
                    len(name_text) > 1):
                    staff_info['name'] = name_text
                    break  # 找到第一個有效的姓名就停止

            # 提取 Email
            email_spans = table.find_all('span', id=lambda x: x and 'cloak' in x)
            if email_spans:
                for span in email_spans:
                    next_script = span.find_next_sibling('script')
                    if next_script and next_script.string:
                        email = self._extract_email_from_script(next_script.string)
                        if email:
                            staff_info['email'] = email
                            break

            # 提取電話、傳真和其他資訊
            all_text = table.get_text()

            # 提取電話
            tel_match = re.search(r'Tel:\s*([+\d\-#]+)', all_text)
            if tel_match:
                staff_info['phone'] = tel_match.group(1).strip()

            # 提取傳真
            fax_match = re.search(r'Fax:\s*([+\d\-#]+)', all_text)
            if fax_match:
                staff_info['fax'] = fax_match.group(1).strip()

            # 提取個人介紹連結
            intro_link = table.find('a', string=lambda x: x and ('點選連結' in x or '個人介紹' in x))
            if intro_link and intro_link.get('href'):
                staff_info['website'] = intro_link.get('href')

            # 提取負責業務
            # 查找包含"負責業務"的標籤
            for tag in table.find_all(['strong', 'b']):
                if '負責業務' in tag.get_text():
                    # 查找後續的 ol 列表
                    ol_tag = tag.find_next('ol')
                    if ol_tag:
                        for li in ol_tag.find_all('li'):
                            responsibility = li.get_text(strip=True)
                            if responsibility:
                                staff_info['responsibilities'].append(responsibility)
                    break

            logger.debug(f"解析高層職員: {staff_info['name']} - {staff_info['position']}")

        except Exception as e:
            logger.error(f"解析高層職員資料時發生錯誤: {e}")

        return staff_info

    def _extract_staff_info_from_context(self, start_element, section: str, subsection: str) -> Dict:
        """從上下文提取教職員資訊"""
        staff_info = {
            'name': '',
            'position': subsection if subsection else '',
            'department': '國際事務處',
            'section': section,
            'phone': '',
            'fax': '',
            'email': '',
            'website': '',
            'responsibilities': []
        }

        try:
            # 提取姓名（同時支援 strong 和 b 標籤）
            name_tag = start_element.find('strong') or start_element.find('b')
            if name_tag:
                staff_info['name'] = name_tag.get_text(strip=True)

            # 向後查找相關資訊
            current = start_element
            for _ in range(10):  # 最多查找後續10個元素
                current = current.find_next_sibling()
                if not current:
                    break

                text = current.get_text(strip=True)

                # 如果遇到下一個 strong 或 b (下一個人員)，停止
                if (current.find('strong') or current.find('b')) and '負責業務' not in text:
                    break

                # 提取 Email
                if 'Email:' in text or current.find('span', id=lambda x: x and 'cloak' in x):
                    # 嘗試從 JavaScript 中解析 Email
                    scripts = current.find_all('script')
                    for script in scripts:
                        if script.string:
                            email = self._extract_email_from_script(script.string)
                            if email:
                                staff_info['email'] = email
                                break

                # 提取電話
                if 'Tel:' in text:
                    tel_match = re.search(r'Tel:\s*([+\d\-#]+)', text)
                    if tel_match:
                        staff_info['phone'] = tel_match.group(1).strip()

                # 提取傳真
                if 'Fax:' in text:
                    fax_match = re.search(r'Fax:\s*([+\d\-#]+)', text)
                    if fax_match:
                        staff_info['fax'] = fax_match.group(1).strip()

                # 提取個人網頁
                if '個人介紹' in text or '點選連結' in text:
                    link = current.find('a')
                    if link and link.get('href'):
                        staff_info['website'] = link.get('href')

                # 提取負責業務
                if '負責業務' in text:
                    # 查找後續的 ol 或列表
                    ol_tag = current.find_next('ol')
                    if ol_tag:
                        for li in ol_tag.find_all('li'):
                            responsibility = li.get_text(strip=True)
                            if responsibility:
                                staff_info['responsibilities'].append(responsibility)

        except Exception as e:
            logger.error(f"解析職員資料時發生錯誤: {e}")

        return staff_info

    def _extract_email_from_script(self, script_text: str) -> str:
        """從 JavaScript 代碼中提取 Email"""
        try:
            # 尋找 addy 變數的定義
            # 格式: var addy... = 'username' + '&#64;';
            # addy... = addy... + 'domain' + '&#46;' + 'tw';

            parts = []

            # 提取所有的賦值語句
            lines = script_text.split(';')
            for line in lines:
                if 'addy' in line and '=' in line and 'innerHTML' not in line:
                    # 提取字符串內容
                    matches = re.findall(r"'([^']+)'", line)
                    for match in matches:
                        # 解碼 HTML 實體
                        decoded = html.unescape(match)
                        # 過濾掉變數名
                        if decoded and not decoded.startswith('addy'):
                            parts.append(decoded)

            if parts:
                email = ''.join(parts)
                # 基本驗證
                if '@' in email and '.' in email:
                    return email

        except Exception as e:
            logger.debug(f"解析 Email 時發生錯誤: {e}")

        return ""
