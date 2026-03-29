#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學國際事務處雙聯學位計畫：締約說明與締約學校列表"""

import re
import time
import logging
from typing import List, Dict, Any

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.oia.nchu.edu.tw"
INFO_URL = f"{BASE_URL}/index.php/zh/7-partnership-with-nchu-tw/7-3-dual-degree-program-tw/7-3-1-agreement-signing-tw"
LIST_URL = f"{BASE_URL}/index.php/zh/7-partnership-with-nchu-tw/7-3-dual-degree-program-tw/7-3-2-list-of-partner-universities-of-dual-degree-program-tw"

REQUEST_DELAY = 0.5

# 兩個表格的程式類型對應
PROGRAM_TYPE_LABELS = {
    0: "dual_degree",   # 雙聯學位締約學校
    1: "3_plus_x",      # 已簽署（3+X）學位合約之學校
}


class DualDegreeScraper(BaseScraper):
    """雙聯學位計畫爬蟲"""

    def __init__(self):
        super().__init__(
            source_url=LIST_URL,
            output_filename="dual_degree.json",
            data_dir="oia",
        )
        self.html_cache_dir = self.data_dir / "dual_degree_cache"
        self.html_cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # 快取                                                                  #
    # ------------------------------------------------------------------ #

    def _fetch_cached(self, url: str, cache_name: str) -> str:
        cache_file = self.html_cache_dir / cache_name
        if cache_file.exists():
            logger.info(f"使用快取: {cache_file}")
            return cache_file.read_text(encoding="utf-8")
        html = self.fetch_page(url)
        if html:
            cache_file.write_text(html, encoding="utf-8")
        return html or ""

    # ------------------------------------------------------------------ #
    # scrape()                                                             #
    # ------------------------------------------------------------------ #

    def scrape(self) -> Dict[str, str]:
        info_html = self._fetch_cached(INFO_URL, "info.html")
        time.sleep(REQUEST_DELAY)
        list_html = self._fetch_cached(LIST_URL, "list.html")
        return {"info": info_html, "list": list_html}

    # ------------------------------------------------------------------ #
    # parse()                                                              #
    # ------------------------------------------------------------------ #

    def parse(self, raw_data: Dict[str, str]) -> List[Dict]:
        """回傳 [info_dict, *university_dicts]，save_data() 會拆分處理"""
        info = self._parse_info(raw_data.get("info", ""))
        universities = self._parse_list(raw_data.get("list", ""))
        logger.info(f"共解析 {len(universities)} 筆締約學校資料")
        # 回傳格式供 save_data() 使用
        return [{"_type": "info", **info}] + universities

    # ------------------------------------------------------------------ #
    # 解析締約說明頁                                                        #
    # ------------------------------------------------------------------ #

    def _parse_info(self, html: str) -> Dict:
        if not html:
            return {}
        soup = BeautifulSoup(html, "html.parser")

        # 找主內容區
        content = soup.find("div", class_="item-page") or soup.find("div", id="content")
        if not content:
            return {}

        sections: Dict[str, Any] = {}
        regulations: List[Dict] = []

        for h3 in content.find_all("h3"):
            title = h3.get_text(strip=True)
            # 蒐集 h3 後的所有同層文字直到下一個 h3
            parts = []
            for sib in h3.find_next_siblings():
                if sib.name == "h3":
                    break
                if sib.name in ("ol", "ul", "p") and "相關法規" in title:
                    for a in sib.find_all("a", href=True):
                        href = a["href"]
                        if not href.startswith("http"):
                            href = BASE_URL + href
                        regulations.append({"title": a.get_text(strip=True), "url": href})
                else:
                    text = sib.get_text(separator=" ", strip=True)
                    if text:
                        parts.append(text)
            sections[title] = " ".join(parts)

        return {"sections": sections, "regulations": regulations}

    # ------------------------------------------------------------------ #
    # 解析締約學校列表頁                                                    #
    # ------------------------------------------------------------------ #

    def _expand_table(self, table) -> List[List[str]]:
        """將含 rowspan 的表格展開為完整二維矩陣（7 欄）。"""
        COLS = 7
        carry: Dict[int, Any] = {}  # {col_idx: (remaining_rows, text)}
        grid: List[List[str]] = []

        for row in table.find_all("tr"):
            cells = iter(row.find_all(["td", "th"]))
            new_row: List[str] = []
            col = 0

            while col < COLS:
                if col in carry:
                    remaining, text = carry[col]
                    new_row.append(text)
                    if remaining - 1 > 0:
                        carry[col] = (remaining - 1, text)
                    else:
                        del carry[col]
                    col += 1
                else:
                    try:
                        cell = next(cells)
                        text = cell.get_text(strip=True)
                        rowspan = int(cell.get("rowspan", 1))
                        colspan = int(cell.get("colspan", 1))
                        for c in range(colspan):
                            new_row.append(text)
                            if rowspan > 1:
                                carry[col + c] = (rowspan - 1, text)
                        col += colspan
                    except StopIteration:
                        new_row.append("")
                        col += 1

            grid.append(new_row)

        return grid

    def _parse_list(self, html: str) -> List[Dict]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        universities: List[Dict] = []

        for table_idx, table in enumerate(tables):
            program_type = PROGRAM_TYPE_LABELS.get(table_idx, "dual_degree")
            grid = self._expand_table(table)

            for row in grid:
                # 跳過標頭列
                if any(h in row[0] for h in ("洲屬", "Continent")):
                    continue
                if not any(row):
                    continue

                dept_raw = row[6] if len(row) > 6 else ""
                is_expired = bool(re.search(r"已過期", " ".join(row)))
                dept = re.sub(r"[（(]已過期[）)]", "", dept_raw).strip()

                # 學校名稱有時包含國家前綴（因 rowspan 合併），去除之
                country = row[3]
                school = row[4]
                if country and school.startswith(country):
                    school = school[len(country):].strip()

                universities.append({
                    "program_type": program_type,
                    "洲屬": row[0],
                    "簽約日期": row[1],
                    "到期日": row[2],
                    "國家": country,
                    "學校名稱": school,
                    "學位": row[5],
                    "系所": dept,
                    "已過期": is_expired,
                })

        return universities

    # ------------------------------------------------------------------ #
    # save_data() 覆寫：拆分 info 與 data                                  #
    # ------------------------------------------------------------------ #

    def save_data(self, parsed: List[Dict]):
        from datetime import datetime
        import json

        info = {}
        universities = []
        for item in parsed:
            if item.get("_type") == "info":
                info = {k: v for k, v in item.items() if k != "_type"}
            else:
                universities.append(item)

        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(universities),
                "data_source": self.source_url,
                "info_source": INFO_URL,
            },
            "info": info,
            "data": universities,
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"資料已儲存至: {self.output_path}（共 {len(universities)} 筆）")
        if self.enable_hot_reload:
            self._trigger_hot_reload()
