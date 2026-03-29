#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學教學發展中心教學計畫申請頁面"""

import logging
from typing import List, Dict, Any

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://cdtl.nchu.edu.tw/2019application"
INDEX_URL = f"{BASE_URL}/index.php"

# 依圖片檔名識別類別
CATEGORY_BY_IMG = {
    "teacher_link.png": "教師計畫",
    "creativity_program.png": "學生計畫",
}


class CdtlApplicationsScraper(BaseScraper):
    """教學計畫申請爬蟲"""

    def __init__(self):
        super().__init__(
            source_url=INDEX_URL,
            output_filename="cdtl_applications.json",
            data_dir="cdtl",
        )

    def scrape(self) -> str:
        return self.fetch_page(INDEX_URL) or ""

    def parse(self, raw_data: str) -> List[Dict]:
        soup = BeautifulSoup(raw_data, "html.parser")
        plans: List[Dict] = []

        for row in soup.find_all("div", class_="row"):
            # 從 h3 的圖片辨識類別
            img = row.find("img", src=lambda s: s and "assets/img/" in s)
            img_name = img["src"].split("/")[-1] if img else ""
            category = CATEGORY_BY_IMG.get(img_name, "其他")

            for card in row.find_all("div", class_="card"):
                body = card.find("div", class_="card-body")
                if not body:
                    continue

                title = body.find("h4")
                name = title.get_text(strip=True) if title else ""

                english = body.find("p", class_="remind_s1")
                english_name = english.get_text(strip=True) if english else ""

                # 資訊段落：「申請期間：...」、「適用對象：...」等
                info: Dict[str, str] = {}
                for p in body.find_all("p", class_="card-text"):
                    text = p.get_text(separator=" ", strip=True)
                    if "：" in text:
                        key, _, val = text.partition("：")
                        info[key.strip()] = val.strip()
                    elif text:
                        info["說明"] = text

                # 檔案連結與申請連結
                files: List[Dict[str, str]] = []
                apply_url = ""
                for a in body.find_all("a", href=True):
                    link_text = a.get_text(strip=True)
                    href = a["href"]
                    if link_text == "前往申請":
                        apply_url = f"{BASE_URL}/{href}" if not href.startswith("http") else href
                    else:
                        full_url = f"{BASE_URL}/{href}" if not href.startswith("http") else href
                        files.append({"name": link_text, "url": full_url})

                plans.append({
                    "category": category,
                    "name": name,
                    "english_name": english_name,
                    "info": info,
                    "files": files,
                    "apply_url": apply_url,
                })

        logger.info(f"共解析 {len(plans)} 個教學計畫申請")
        return plans
