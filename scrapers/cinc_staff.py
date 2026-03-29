#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學計算機及資訊網路中心人員職務資料"""

import json
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

# 各組別對應的 AJAX Nbr 參數
SECTION_NBR_MAP = {
    '主任室': 7,
    '服務諮詢組': 8,
    '校務系統組': 10,
    '資訊網路組': 11,
    '研究發展組': 12,
    '資源管理組': 334,
    '資安驗證中心': 13,
}

AJAX_URL = 'https://cc.nchu.edu.tw/app/index.php?Action=mobileloadmod&Type=mobile_um_mstr&Nbr={nbr}'
SOURCE_URL = 'https://cc.nchu.edu.tw/p/426-1000-6.php?Lang=zh-tw'


def parse_name_position(raw: str):
    """
    從「職稱 姓名」或「職稱姓名」或「姓名」字串中拆分職稱與姓名。

    格式說明：
    - "主任 詹永寬"        → position="主任",        name="詹永寬"
    - "副主任兼任組長吳賢明" → position="副主任兼任組長", name="吳賢明"
    - "陳品澄"             → position="",            name="陳品澄"

    規則：
    1. 含空格 → 以第一個空格切分，前為職稱、後為姓名
    2. 無空格且長度 > 3 → 後 3 字為姓名，其餘為職稱
    3. 無空格且長度 ≤ 3 → 全為姓名，無職稱

    回傳: (name, position) tuple
    """
    raw = raw.strip()
    if not raw:
        return "", ""

    if ' ' in raw:
        position, name = raw.split(' ', 1)
        return name.strip(), position.strip()

    if len(raw) > 3:
        # 後 3 字為姓名（中文姓名通常 3 字）
        return raw[-3:], raw[:-3]

    return raw, ""


def extract_section_info(soup: BeautifulSoup) -> Dict[str, str]:
    """
    從頁面 <p> 標籤中抽取組別層級的辦公位置、電話、傳真、Email。
    判斷依據為 img 的 alt 屬性文字。
    """
    info = {
        'office_location': '',
        'section_phone': '',
        'fax': '',
        'section_email': '',
    }
    for p in soup.find_all('p'):
        img = p.find('img')
        if not img:
            continue
        alt = img.get('alt', '')
        text = p.get_text(strip=True)

        if '辦公室' in alt or '位置' in alt:
            info['office_location'] = text
        elif '聯絡電話' in alt or '電話' in alt:
            if not info['section_phone']:  # 只取第一個電話
                info['section_phone'] = text
        elif '傳真' in alt:
            info['fax'] = text
        elif '電子郵件' in alt or 'mail' in alt.lower():
            link = p.find('a', href=re.compile(r'^mailto:'))
            if link:
                info['section_email'] = link['href'].replace('mailto:', '').strip()
            else:
                info['section_email'] = text

    return info


class CincStaffScraper(BaseScraper):
    """計算機及資訊網路中心人員職務資料爬蟲"""

    def __init__(self):
        super().__init__(
            source_url=SOURCE_URL,
            output_filename="cinc_staff.json",
            data_dir="staff/cinc",
        )

        # HTML 快取目錄
        staff_dir = self.data_dir.parent  # data/staff
        cache_dir = staff_dir / "cache" / "cinc_staff"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir

        # POST 請求所需的標頭
        self._ajax_headers = {
            'User-Agent': self.headers['User-Agent'],
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': SOURCE_URL,
        }

    def _init_session(self):
        """先訪問主頁取得 Session Cookie"""
        try:
            self.session.get(SOURCE_URL, headers=self.headers, timeout=15)
            logger.info("Session Cookie 取得成功")
        except Exception as e:
            logger.warning(f"取得 Session Cookie 失敗: {e}")

    def scrape(self) -> List[Dict[str, Any]]:
        """
        對每個組別 POST AJAX 端點，取得 HTML 原始資料。
        回傳: [{"section": 組別名稱, "html": HTML字串}, ...]
        若有快取則直接讀取快取。
        """
        self._init_session()
        sections_data = []

        for section_name, nbr in SECTION_NBR_MAP.items():
            cache_file = self.cache_dir / f"cinc_staff_{nbr}_cache.html"

            # 優先使用快取
            if cache_file.exists():
                logger.info(f"使用快取 [{section_name}]: {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    html = f.read()
            else:
                url = AJAX_URL.format(nbr=nbr)
                try:
                    resp = self.session.post(
                        url, headers=self._ajax_headers, data='', timeout=15
                    )
                    resp.raise_for_status()
                    html = resp.text
                    logger.info(f"爬取成功 [{section_name}]: {len(html)} bytes")

                    # 儲存快取
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.info(f"HTML 快取至: {cache_file}")

                except Exception as e:
                    logger.error(f"爬取 [{section_name}] 失敗: {e}")
                    html = ""

            sections_data.append({"section": section_name, "html": html})

        return sections_data

    def parse(self, raw_data: List[Dict[str, Any]]) -> List[Dict]:
        """
        解析各組別 HTML，回傳結構化資料列表。

        表格欄位（6 欄）：
          [0] 照片  [1] 姓名(含職稱)  [2] 工作職掌  [3] 聯絡電話  [4] 聯絡信箱  [5] 代理人

        回傳: 結構化資料列表
        """
        if not raw_data:
            logger.warning("沒有資料可解析")
            return []

        results = []

        for section_item in raw_data:
            section_name = section_item["section"]
            html = section_item["html"]

            if not html:
                logger.warning(f"[{section_name}] 無 HTML 內容，跳過")
                continue

            soup = BeautifulSoup(html, 'html.parser')

            # 抽取組別層級聯絡資訊
            section_info = extract_section_info(soup)

            table = soup.find('table')
            if not table:
                logger.warning(f"[{section_name}] 找不到資料表格")
                continue

            rows = table.find_all('tr')
            data_rows = [r for r in rows if not r.find('th')]
            logger.info(f"[{section_name}] 找到 {len(data_rows)} 位人員")

            for row in data_rows:
                cells = row.find_all('td')
                if len(cells) < 5:
                    continue

                try:
                    name_raw = cells[1].get_text(strip=True)
                    name, position = parse_name_position(name_raw)

                    if not name:
                        continue

                    # 職掌：以 <br> 分行轉為純文字列表
                    resp_cell = cells[2]
                    for br in resp_cell.find_all('br'):
                        br.replace_with('\n')
                    responsibilities = resp_cell.get_text(separator='\n').strip()

                    # Email：從 mailto 連結取得
                    email_cell = cells[4]
                    email_link = email_cell.find('a', href=re.compile(r'^mailto:'))
                    email = (
                        email_link['href'].replace('mailto:', '').strip()
                        if email_link
                        else email_cell.get_text(strip=True)
                    )

                    staff_data = {
                        'name': name,
                        'position': position,
                        'department': '計算機及資訊網路中心',
                        'section': section_name,
                        'phone': cells[3].get_text(strip=True),
                        'email': email,
                        'deputy': cells[5].get_text(strip=True) if len(cells) > 5 else '',
                        'responsibilities': responsibilities,
                        'office_location': section_info['office_location'],
                    }

                    results.append(staff_data)
                    logger.debug(f"成功解析: {name} ({position}) - {section_name}")

                except Exception as e:
                    logger.error(f"[{section_name}] 解析資料列失敗: {e}", exc_info=True)
                    continue

        logger.info(f"成功解析 {len(results)} 位人員資料")
        return results


def main():
    """測試用主函式"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    scraper = CincStaffScraper()
    scraper.force_update()


if __name__ == '__main__':
    main()
