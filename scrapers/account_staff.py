#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學主計室職員資料"""

import re
import json
from typing import List, Dict, Tuple
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class AccountStaffScraper(BaseScraper):
    """主計室職員資料爬蟲"""

    # 位置資訊頁面
    LOCATION_PAGE_URL = "https://www.nchu.edu.tw/administrative/mid/311"

    # 組別對應表
    SECTION_MAP = {
        '室本部': '室本部',
        '一組': '一組（預算決算組）',
        '二組': '二組（校務基金組）',
        '三組': '三組（國科會計畫組）',
        '四組': '四組（其他計畫組）'
    }

    def __init__(self):
        super().__init__(
            source_url="https://account.nchu.edu.tw/zh-tw/about",
            output_filename="account_staff.json",
            data_dir="staff/account"  # 輸出到 data/staff/account/
        )

        # HTML 快取路徑（在 data/staff/cache 目錄下）
        staff_dir = self.data_dir.parent  # 從 data/staff/account 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "account_staff_cache.html"
        self.location_page_cache_path = cache_dir / "account_location_cache.html"

        # 主計室位置（由 parse 時解析並儲存）
        self._location = ""

    def scrape(self) -> Tuple[str, str]:
        """
        爬取網頁內容
        回傳: (職員資料 HTML, 位置頁面 HTML)
        """
        # 爬取職員資料頁
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                staff_html = f.read()
        else:
            staff_html = self.fetch_page(self.source_url)
            if not staff_html:
                logger.error("無法爬取主計室網頁")
                return "", ""
            try:
                with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                    f.write(staff_html)
                logger.info(f"HTML 已快取至: {self.html_cache_path}")
            except Exception as e:
                logger.warning(f"無法儲存 HTML 快取: {e}")

        # 爬取位置資訊頁
        if self.location_page_cache_path.exists():
            logger.info(f"使用快取的位置頁面: {self.location_page_cache_path}")
            with open(self.location_page_cache_path, 'r', encoding='utf-8') as f:
                location_html = f.read()
        else:
            location_html = self.fetch_page(self.LOCATION_PAGE_URL)
            if not location_html:
                logger.warning("無法爬取位置頁面")
                location_html = ""
            else:
                try:
                    with open(self.location_page_cache_path, 'w', encoding='utf-8') as f:
                        f.write(location_html)
                    logger.info(f"位置頁面已快取至: {self.location_page_cache_path}")
                except Exception as e:
                    logger.warning(f"無法儲存位置頁面快取: {e}")

        return staff_html, location_html

    def _extract_location(self, location_html: str) -> str:
        """從位置頁面中提取主計室位置"""
        if not location_html:
            return ""
        try:
            match = re.search(r'\d+號\s*(行政大樓\d+樓)', location_html)
            if match:
                location = match.group(1)
                logger.debug(f"找到主計室位置: {location}")
                return location
        except Exception as e:
            logger.warning(f"提取位置時發生錯誤: {e}")
        return ""

    def parse(self, raw_data: Tuple[str, str]) -> List[Dict]:
        """
        解析爬取的資料
        參數: raw_data - scrape() 回傳的 (職員資料 HTML, 位置頁面 HTML)
        回傳: 結構化資料列表
        """
        staff_html, location_html = raw_data

        if not staff_html:
            logger.warning("沒有資料可解析")
            return []

        self._location = self._extract_location(location_html)

        soup = BeautifulSoup(staff_html, 'html.parser')
        results = []

        # 主計室使用 table 標籤組織資料
        # 找到所有的表格
        tables = soup.find_all('table')

        if not tables:
            logger.warning("找不到任何表格")
            return []

        logger.info(f"找到 {len(tables)} 個表格")

        # 找到所有標題，用於判斷當前處理的是哪個組別
        # 主計室的組別標題通常在 h3 或 h4 標籤中
        current_section = "室本部"  # 預設值

        # 遍歷頁面內容，尋找組別標題和對應的表格
        content_area = soup.find('div', class_='view-content')
        if not content_area:
            # 如果沒有 view-content，嘗試其他可能的容器
            content_area = soup.find('div', class_='region-content')

        if not content_area:
            # 如果還是沒有，直接處理整個 body
            content_area = soup.find('body')

        if not content_area:
            logger.warning("找不到內容區域")
            return []

        # 遍歷內容區域的所有元素
        for element in content_area.find_all(['h2', 'h3', 'h4', 'table']):
            if element.name in ['h2', 'h3', 'h4']:
                # 檢查是否為組別標題
                heading_text = element.get_text(strip=True)
                for key, value in self.SECTION_MAP.items():
                    if key in heading_text:
                        current_section = value
                        logger.info(f"找到組別: {current_section}")
                        break

            elif element.name == 'table':
                # 解析表格資料
                rows = element.find_all('tr')
                if len(rows) < 2:
                    continue  # 跳過沒有資料的表格

                # 解析標題列，判斷欄位順序
                thead = element.find('thead')
                if not thead:
                    continue

                header_row = thead.find('tr')
                if not header_row:
                    continue

                headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
                if '姓名' not in headers:
                    continue  # 跳過非人員資料表格

                logger.info(f"解析 [{current_section}] 的人員資料，欄位: {headers}")

                # 建立欄位索引映射
                col_map = {}
                for idx, header in enumerate(headers):
                    if '姓名' in header:
                        col_map['name'] = idx
                    elif '職稱' in header:
                        col_map['position'] = idx
                    elif '電話' in header:
                        col_map['phone'] = idx
                    elif 'Email' in header or 'email' in header:
                        col_map['email'] = idx
                    elif '經辦業務' in header or '業務' in header:
                        col_map['responsibilities'] = idx
                    elif '職務代理' in header or '代理' in header:
                        col_map['deputy'] = idx

                # 處理資料列（從 tbody 取得）
                tbody = element.find('tbody')
                if not tbody:
                    continue

                for row in tbody.find_all('tr'):
                    try:
                        cols = row.find_all('td')
                        if len(cols) < 3:
                            continue  # 至少需要姓名、電話、Email

                        # 解析姓名
                        name = ""
                        if 'name' in col_map:
                            name = cols[col_map['name']].get_text(strip=True)
                        if not name:
                            continue

                        # 解析職稱
                        position = ""
                        if 'position' in col_map:
                            position = cols[col_map['position']].get_text(strip=True)

                        # 解析電話
                        phone = ""
                        if 'phone' in col_map:
                            phone = cols[col_map['phone']].get_text(strip=True)

                        # 解析 Email
                        email = ""
                        if 'email' in col_map:
                            email_col = cols[col_map['email']]
                            email_link = email_col.find('a', href=re.compile(r'^mailto:'))
                            if email_link:
                                email = email_link.get('href', '').replace('mailto:', '').strip()
                            else:
                                email = email_col.get_text(strip=True)

                        # 解析業務職掌
                        responsibilities_list = []
                        if 'responsibilities' in col_map:
                            duties_col = cols[col_map['responsibilities']]
                            # 使用 <br> 分隔，保留換行結構
                            duties_text = duties_col.get_text('\n', strip=True)
                            if duties_text:
                                lines = duties_text.split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if line:
                                        responsibilities_list.append(line)

                        responsibilities = '\n'.join(f"- {r}" for r in responsibilities_list) if responsibilities_list else ""

                        # 解析職務代理人
                        deputy = ""
                        if 'deputy' in col_map:
                            deputy = cols[col_map['deputy']].get_text(strip=True)

                        # 建立資料字典
                        staff_data = {
                            'name': name,
                            'position': position,
                            'department': '主計室',
                            'section': current_section,
                            'phone': phone,
                            'email': email,
                            'deputy': deputy,
                            'responsibilities': responsibilities
                        }

                        results.append(staff_data)
                        logger.debug(f"成功解析職員: {name} ({position}) - {current_section}")

                    except Exception as e:
                        logger.error(f"解析職員資料時發生錯誤: {e}", exc_info=True)
                        continue

        logger.info(f"成功解析 {len(results)} 位職員資料")
        return results


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


def main():
    """測試用主函式"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    scraper = AccountStaffScraper()
    scraper.force_update()


if __name__ == '__main__':
    main()
