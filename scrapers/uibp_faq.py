#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取興大校學士 FAQ 資料"""

import logging
import re
from typing import Dict, List

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class UIBPFAQScraper(BaseScraper):
    """興大校務規劃處 FAQ 爬蟲"""

    BASE_URL = "https://uibp.nchu.edu.tw/qa.php"

    def __init__(self):
        super().__init__(
            source_url="https://uibp.nchu.edu.tw/qa.php?cID=0&page=1",
            output_filename="uibp_faq.json",
            data_dir="rules",
            enable_hot_reload=True
        )

    def _get_total_pages(self, html: str) -> int:
        """取得總頁數"""
        soup = BeautifulSoup(html, 'html.parser')
        page_links = soup.select('.page a, .pagination a')

        max_page = 1
        for link in page_links:
            href = link.get('href', '')
            match = re.search(r'page=(\d+)', href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)

        # 也檢查文字內容
        for link in page_links:
            text = link.get_text(strip=True)
            if text.isdigit():
                max_page = max(max_page, int(text))

        return max_page

    def scrape(self) -> str:
        """爬取所有頁面的 FAQ 資料"""
        # 先取得第一頁來判斷總頁數
        first_page_html = self.fetch_page(f"{self.BASE_URL}?cID=0&page=1")
        if not first_page_html:
            return ""

        total_pages = self._get_total_pages(first_page_html)
        logger.info(f"共有 {total_pages} 頁 FAQ 資料")

        # 收集所有頁面的 HTML
        all_html = [first_page_html]

        for page in range(2, total_pages + 1):
            url = f"{self.BASE_URL}?cID=0&page={page}"
            logger.info(f"爬取第 {page} 頁: {url}")
            html = self.fetch_page(url)
            if html:
                all_html.append(html)

        # 用分隔符號連接所有頁面的 HTML
        return "<!--PAGE_SEPARATOR-->".join(all_html)

    def parse(self, raw_data: str) -> List[Dict]:
        """解析 FAQ 資料"""
        if not raw_data:
            return []

        results = []
        pages = raw_data.split("<!--PAGE_SEPARATOR-->")

        for page_html in pages:
            soup = BeautifulSoup(page_html, 'html.parser')
            qa_boxes = soup.select('.qa_box')

            for box in qa_boxes:
                question_elem = box.select_one('.q')
                answer_elem = box.select_one('.a')

                if question_elem and answer_elem:
                    question = question_elem.get_text(strip=True)
                    answer = answer_elem.get_text(strip=True)

                    # 清理問題文字（移除編號）
                    question = re.sub(r'^[Q\d]+[.、\s]*', '', question).strip()

                    if question and answer:
                        results.append({
                            "question": question,
                            "answer": answer
                        })

        logger.info(f"共解析 {len(results)} 筆 FAQ 資料")
        return results
