#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學人事室職員資料"""

import re
import json
from typing import List, Dict
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class PersonStaffScraper(BaseScraper):
    """人事室職員資料爬蟲"""

    # 組別對應表
    SECTION_MAP = {
        'home0': '主管',
        'home1': '綜合企劃組',
        'home2': '考試任免組',
        'home3': '考核培訓組',
        'home4': '待遇退撫組'
    }

    # 人事室主要電話
    MAIN_PHONE = '(04)22840673'

    def __init__(self):
        super().__init__(
            source_url="https://person.nchu.edu.tw/personal.php",
            output_filename="person_staff.json",
            data_dir="staff/person"  # 輸出到 data/staff/person/
        )

        # HTML 快取路徑（在 data/staff/cache 目錄下）
        staff_dir = self.data_dir.parent  # 從 data/staff/person 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "person_staff_cache.html"

        # 人事室位置（由 parse 時解析並儲存）
        self._location = ""

    def _extract_location(self, soup: BeautifulSoup) -> str:
        """從頁面 address 標籤中提取人事室位置"""
        try:
            addr_tag = soup.find('address')
            if addr_tag:
                text = addr_tag.get_text(strip=True)
                # 擷取門牌號碼後、Tel 前的建築物+樓層（含括號）
                match = re.search(r'\d+號\s+([\u4e00-\u9fff\d（）()]+)', text)
                if match:
                    location = match.group(1).strip()
                    logger.debug(f"找到人事室位置: {location}")
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
        """
        爬取網頁內容
        回傳: HTML 字串
        """
        # 檢查快取（開發時使用）
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                return f.read()

        # 爬取新資料
        html = self.fetch_page(self.source_url)
        if not html:
            logger.error("無法爬取人事室網頁")
            return ""

        # 儲存快取
        try:
            with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML 已快取至: {self.html_cache_path}")
        except Exception as e:
            logger.warning(f"無法儲存 HTML 快取: {e}")

        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """
        解析爬取的資料
        參數: raw_data - scrape() 回傳的內容
        回傳: 結構化資料列表
        """
        if not raw_data:
            logger.warning("沒有資料可解析")
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        self._location = self._extract_location(soup)
        results = []

        # 遍歷每個 tab-pane (組別)
        for section_id, section_name in self.SECTION_MAP.items():
            tab_pane = soup.find('div', id=section_id, class_='tab-pane')
            if not tab_pane:
                logger.warning(f"找不到組別: {section_name} (id={section_id})")
                continue

            # 在該組別下找所有 h4 標籤
            staff_headers = tab_pane.find_all('h4')
            logger.info(f"在 [{section_name}] 找到 {len(staff_headers)} 位職員")

            for h4 in staff_headers:
                try:
                    # 解析姓名和職稱（格式：姓名(職稱)）
                    full_name = h4.get_text(strip=True)
                    if not full_name:
                        continue

                    # 提取姓名和職稱
                    name_match = re.match(r'(.+?)\((.+?)\)', full_name)
                    if name_match:
                        name = name_match.group(1).strip()
                        position = name_match.group(2).strip()
                    else:
                        # 如果沒有括號，整個作為姓名
                        name = full_name
                        position = ""

                    # 找到 h4 的父級 div (col-md-5)
                    col_md_5 = h4.find_parent('div', class_='col-md-5')
                    if not col_md_5:
                        logger.warning(f"找不到 {name} 的父級 div (col-md-5)")
                        continue

                    # 找到包含 col-md-5 的 row
                    row = col_md_5.find_parent('div', class_='row')
                    if not row:
                        logger.warning(f"找不到 {name} 的 row")
                        continue

                    # 在 col-md-5 中找 ul 元素（包含 email 和分機）
                    ul = col_md_5.find('ul')
                    email = ""
                    extension = ""

                    if ul:
                        li_items = ul.find_all('li')
                        for li in li_items:
                            # 檢查是否為 email
                            email_link = li.find('a', href=re.compile(r'^mailto:'))
                            if email_link:
                                email = email_link.get_text(strip=True)
                            else:
                                # 假設是分機（移除圖標）
                                text = li.get_text(strip=True)
                                if text and '@' not in text:
                                    extension = text

                    # 組合完整電話號碼
                    phone = f"{self.MAIN_PHONE} 轉 {extension}" if extension else ""

                    # 在同一個 row 中找 col-md-7 (職責內容)
                    col_md_7 = row.find('div', class_='col-md-7')
                    responsibilities = []

                    if col_md_7:
                        # 複製 col_md_7 避免修改原始樹
                        import copy
                        col_md_7_copy = copy.copy(col_md_7)

                        # 將 <br> 標籤替換為特殊分隔符
                        for br in col_md_7_copy.find_all('br'):
                            br.replace_with('|||NEWLINE|||')

                        # 取得職責內容
                        resp_text = col_md_7_copy.get_text()
                        if resp_text:
                            # 用分隔符分割並清理每行
                            lines = resp_text.split('|||NEWLINE|||')
                            responsibilities = [line.strip() for line in lines if line.strip()]

                    # 找到職務代理人（在下一個 row 的 col-md-7 中）
                    deputy = ""
                    next_row = row.find_next_sibling('div', class_='row')

                    if next_row:
                        deputy_div = next_row.find('div', class_='col-md-7')
                        if deputy_div:
                            text = deputy_div.get_text(strip=True)
                            if '職務代理' in text:
                                deputy = text.replace('職務代理：', '').replace('職務代理', '').strip()

                    # 建立資料字典
                    staff_data = {
                        'name': name,
                        'position': position,
                        'department': '人事室',
                        'section': section_name,  # 加入組別資訊
                        'phone': phone,
                        'email': email,
                        'deputy': deputy,
                        'responsibilities': '\n'.join(f"- {r}" for r in responsibilities) if responsibilities else ""
                    }

                    results.append(staff_data)
                    logger.debug(f"成功解析職員: {name} ({position}) - {section_name}")

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

    scraper = PersonStaffScraper()
    scraper.update()


if __name__ == '__main__':
    main()
