#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學圖書館各空間的預約及使用規則"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# 各空間名稱與對應的頁面 Key
SPACE_PAGES = [
    {"name": "自習室",       "key": "13"},
    {"name": "研究小間",     "key": "40"},
    {"name": "讀者討論室",   "key": "41"},
    {"name": "多媒體聆聽席", "key": "42"},
    {"name": "小團體視聽室", "key": "43"},
    {"name": "多媒體創作坊", "key": "44"},
    {"name": "興閱坊愛學區", "key": "45"},
    {"name": "興閱坊討論室", "key": "46"},
]

BASE_URL = "https://www.lib.nchu.edu.tw/service.php?cID=20&Key={key}"


class SpaceRulesScraper(BaseScraper):
    """圖書館空間預約及使用規則爬蟲"""

    def __init__(self):
        super().__init__(
            source_url="https://www.lib.nchu.edu.tw/service.php?cID=20",
            output_filename="space_rules.json",
            data_dir="library",
        )
        self.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.lib.nchu.edu.tw/",
        })

    def scrape(self) -> List[Dict]:
        """逐一爬取各空間規則頁面，回傳原始 HTML 列表"""
        pages = []
        with httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            for space in SPACE_PAGES:
                url = BASE_URL.format(key=space["key"])
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    logger.info(f"成功抓取 {space['name']} ({url})")
                    pages.append({
                        "name": space["name"],
                        "key": space["key"],
                        "url": url,
                        "html": response.text,
                    })
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP 錯誤 {space['name']}: {e.response.status_code}")
                except httpx.RequestError as e:
                    logger.error(f"請求失敗 {space['name']}: {e}")
        return pages

    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """解析各空間頁面，提取預約及使用規則"""
        results = []
        for page in raw_data:
            parsed = self._parse_space_page(page)
            if parsed:
                results.append(parsed)
        return results

    def _parse_space_page(self, page: Dict) -> Optional[Dict]:
        """解析單一空間頁面"""
        html = page.get("html")
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # 嘗試找主要內容區域（常見的 class：content、main-content 等）
        content_area = (
            soup.find("div", class_="content")
            or soup.find("div", id="content")
            or soup.find("div", class_="main-content")
            or soup.find("article")
            or soup.find("div", class_="article")
            or soup.find("div", id="main")
        )

        if not content_area:
            # fallback：取 body 下最大的 div
            body = soup.find("body")
            if body:
                divs = body.find_all("div", recursive=False)
                content_area = max(divs, key=lambda d: len(d.get_text()), default=None) if divs else body

        if not content_area:
            logger.warning(f"找不到內容區域：{page['name']}")
            return None

        # 移除導覽列、頁尾等雜訊
        for tag in content_area.find_all(["nav", "header", "footer", "script", "style"]):
            tag.decompose()

        # 提取標題
        title = ""
        h_tag = content_area.find(["h1", "h2", "h3"])
        if h_tag:
            title = h_tag.get_text(strip=True)

        # 提取純文字內容
        raw_text = content_area.get_text(separator="\n", strip=True)
        # 移除多餘空行
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        # 提取表格（如有預約規則表格）
        tables = self._parse_tables(content_area)

        # 提取清單項目（使用規則常以 ul/ol 呈現）
        lists = self._parse_lists(content_area)

        return {
            "name": page["name"],
            "key": page["key"],
            "url": page["url"],
            "title": title,
            "content": clean_text,
            "tables": tables,
            "lists": lists,
        }

    def _parse_tables(self, soup) -> List[Dict]:
        """提取頁面中的所有表格"""
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if any(cells):
                    rows.append(cells)
            if rows:
                tables.append({"rows": rows})
        return tables

    def _parse_lists(self, soup) -> List[List[str]]:
        """提取頁面中的所有清單"""
        all_lists = []
        for ul_ol in soup.find_all(["ul", "ol"]):
            items = [li.get_text(strip=True) for li in ul_ol.find_all("li") if li.get_text(strip=True)]
            if items:
                all_lists.append(items)
        return all_lists

    def save_data(self, data: List[Dict]):
        """覆寫儲存方法，加入 metadata"""
        import json

        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(data),
                "data_source": self.source_url,
                "spaces": [s["name"] for s in SPACE_PAGES],
            },
            "data": data,
        }

        try:
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"空間規則資料已儲存至：{self.output_path}（共 {len(data)} 筆）")

            if self.enable_hot_reload:
                self._trigger_hot_reload()
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤：{e}")
