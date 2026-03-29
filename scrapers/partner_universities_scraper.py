#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學國際事務處締約學校資料（OIA_data.csv）"""

import csv
import io
import logging
from typing import List, Dict, Any

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CSV_URL = "https://www.oia.nchu.edu.tw/images/partner_schools/OIA_data.csv"


class PartnerUniversitiesScraper(BaseScraper):
    """締約學校爬蟲（直接下載 CSV）"""

    def __init__(self):
        super().__init__(
            source_url=CSV_URL,
            output_filename="partner_universities.json",
            data_dir="oia",
        )

    def scrape(self) -> str:
        """下載 CSV 原始文字"""
        response = self.session.get(CSV_URL, headers=self.headers, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8-sig"  # 處理 BOM
        return response.text

    def parse(self, raw_data: str) -> List[Dict]:
        """解析 CSV，每列轉為 dict"""
        reader = csv.DictReader(io.StringIO(raw_data))
        universities = []
        for row in reader:
            universities.append({
                "洲別": row.get("洲別", "").strip(),
                "continent": row.get("Overseas Continent", "").strip(),
                "國家": row.get("國家", "").strip(),
                "country": row.get("Overseas Country", "").strip(),
                "學校名稱": row.get("學校名稱", "").strip(),
                "institution": row.get("Overseas Institution", "").strip(),
                "合作項目": row.get("合作項目", "").strip(),
                "program": row.get("Cooperative Program", "").strip(),
                "本校合作範圍": row.get("本校合作範圍", "").strip(),
                "nchu_unit": row.get("Cooperative Institution at NCHU", "").strip(),
                "簽約時間": row.get("簽約時間", "").strip(),
                "學校網址": row.get("學校網址", "").strip(),
            })
        logger.info(f"共解析 {len(universities)} 筆締約學校資料")
        return universities
