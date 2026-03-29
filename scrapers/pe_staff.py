#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學體育室人員職務資料"""

import re
import json
from typing import List, Dict, Tuple
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

# 職稱後綴清單（由長到短排序，優先比對較長的職稱）
POSITION_SUFFIXES = [
    '事務助理員', '行政辦事員', '行政助理員', '行政組員', '行政助理',
    '專案副教授', '副教授', '教授', '副主任', '主任', '組長', '副組長',
    '組員', '秘書', '助理員', '辦事員', '幹事', '助理', '技士', '工友',
    '職員', '主管', '科長', '科員', '專員', '技術員',
]


def parse_name_position(name_pos: str):
    """
    從「姓名＋職稱」字串中拆分姓名與職稱。
    採用已知職稱後綴清單比對，以長度降冪優先比對。

    回傳: (name, position) tuple
    """
    for suffix in sorted(POSITION_SUFFIXES, key=len, reverse=True):
        if name_pos.endswith(suffix):
            name = name_pos[: -len(suffix)].strip()
            return name, suffix
    # 無法比對時：假設前 3 字為姓名（中文姓名通常 2-3 字）
    return name_pos[:3].strip(), name_pos[3:].strip()


class PeStaffScraper(BaseScraper):
    """體育室人員職務資料爬蟲"""

    # 位置資訊頁面
    LOCATION_PAGE_URL = "https://www.nchu.edu.tw/administrative/mid/318"

    def __init__(self):
        super().__init__(
            source_url="https://pe.nchu.edu.tw/member_ad.php",
            output_filename="pe_staff.json",
            data_dir="staff/pe"
        )

        # HTML 快取路徑（在 data/staff/cache 目錄下）
        staff_dir = self.data_dir.parent  # 從 data/staff/pe 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "pe_staff_cache.html"
        self.location_page_cache_path = cache_dir / "pe_location_cache.html"

        # 體育室位置（由 parse 時解析並儲存）
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
                logger.error("無法爬取體育室網頁")
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
        """從位置頁面中提取體育室位置"""
        if not location_html:
            return ""
        try:
            match = re.search(r'\d+號\s*([\u4e00-\u9fff]+)', location_html)
            if match:
                location = match.group(1)
                logger.debug(f"找到體育室位置: {location}")
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

    def parse(self, raw_data: Tuple[str, str]) -> List[Dict]:
        """
        解析爬取的資料。

        頁面結構：
          <h4>組別／姓名職稱</h4>
          <div class="table-responsive">
            <table>
              <tr><td>辦公室</td><td>...</td></tr>
              <tr><td>電話</td><td>...</td></tr>
              <tr><td>MAIL</td><td>...</td></tr>
              <tr><td>代理人</td><td>...</td></tr>
              <tr><td>職掌</td><td>...</td></tr>
            </table>
          </div>

        回傳: 結構化資料列表
        """
        staff_html, location_html = raw_data

        if not staff_html:
            logger.warning("沒有資料可解析")
            return []

        self._location = self._extract_location(location_html)

        soup = BeautifulSoup(staff_html, 'html.parser')
        results = []

        # 找所有 h4 標籤，每個對應一位職員
        h4_tags = soup.find_all('h4')
        logger.info(f"找到 {len(h4_tags)} 個 h4 標題（職員）")

        for h4 in h4_tags:
            try:
                heading = h4.get_text(strip=True)
                if '／' not in heading:
                    logger.debug(f"跳過非職員 h4: {heading}")
                    continue

                # 拆分組別與姓名職稱
                section_part, name_pos_part = heading.split('／', 1)
                section = section_part.strip()
                name, position = parse_name_position(name_pos_part.strip())

                # 找緊接在 h4 後面的 div.table-responsive
                wrapper = h4.find_next_sibling('div', class_='table-responsive')
                if not wrapper:
                    logger.warning(f"找不到 {name} 的資料表格")
                    continue

                table = wrapper.find('table')
                if not table:
                    logger.warning(f"找不到 {name} 的 table 元素")
                    continue

                # 解析表格每一列，key = 第一格，value = 第二格
                table_data = {}
                for row in table.find_all('tr'):
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        val = cells[1].get_text(strip=True)
                        table_data[key] = val

                phone = table_data.get('電話', '')
                email = table_data.get('MAIL', '')
                deputy = table_data.get('代理人', '')
                responsibilities = table_data.get('職掌', '')

                staff_data = {
                    'name': name,
                    'position': position,
                    'department': '體育室',
                    'section': section,
                    'phone': phone,
                    'email': email,
                    'deputy': deputy,
                    'responsibilities': responsibilities,
                }

                results.append(staff_data)
                logger.debug(f"成功解析職員: {name} ({position}) - {section}")

            except Exception as e:
                logger.error(f"解析職員資料時發生錯誤: {e}", exc_info=True)
                continue

        logger.info(f"成功解析 {len(results)} 位職員資料")
        return results


def main():
    """測試用主函式"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    scraper = PeStaffScraper()
    scraper.force_update()


if __name__ == '__main__':
    main()
