#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取興大校學士申請流程資料"""

import logging
import re
from typing import Dict, List

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class UIBPApplyScraper(BaseScraper):
    """興大校學士申請流程爬蟲"""

    BASE_URL = "https://uibp.nchu.edu.tw/apply.php?Key=2"

    def __init__(self):
        super().__init__(
            source_url=self.BASE_URL,
            output_filename="uibp_apply.json",
            data_dir="rules",
            enable_hot_reload=True
        )

    def scrape(self) -> str:
        """爬取申請流程頁面"""
        html = self.fetch_page(self.BASE_URL)
        if not html:
            return ""
        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """解析申請流程資料"""
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')

        result = {
            "steps": self._parse_steps(soup),
            "timeline": self._parse_timeline(soup),
            "contact": self._parse_contact_info(soup)
        }

        logger.info(f"共解析 {len(result['steps'])} 個申請步驟")
        return [result]

    def _parse_steps(self, soup: BeautifulSoup) -> List[Dict]:
        """解析申請步驟"""
        steps = []
        step_sections = soup.select('.in_scroll')

        for i, section in enumerate(step_sections, 1):
            step_data = {
                "step": i,
                "title": "",
                "content": []
            }

            # 取得步驟標題
            title_elem = section.select_one('h3')
            if title_elem:
                step_data["title"] = title_elem.get_text(strip=True)

            # 取得步驟內容
            content_boxes = section.select('.bg-white.rounded-2xl')

            for box in content_boxes:
                item = {}

                # 取得編號
                number_elem = box.select_one('b')
                if number_elem:
                    item["number"] = number_elem.get_text(strip=True).rstrip('.')

                # 取得子標題 (h4)
                subtitle_elem = box.select_one('h4')
                if subtitle_elem:
                    item["subtitle"] = subtitle_elem.get_text(strip=True)

                # 取得說明內容 (p) - 保留換行分隔
                content_elems = box.select('p')
                texts = []
                for p in content_elems:
                    # 複製一份來處理，避免修改原始 soup
                    p_copy = BeautifulSoup(str(p), 'html.parser').p
                    # 用 <br> 分隔取得各行
                    for br in p_copy.find_all('br'):
                        br.replace_with('|||LINEBREAK|||')
                    text = p_copy.get_text()
                    if text:
                        # 依換行分割成多個項目
                        lines = [line.strip() for line in text.split('|||LINEBREAK|||') if line.strip()]
                        texts.extend(lines)

                if texts:
                    item["text"] = texts

                # 檢查是否有下載連結
                download_link = box.select_one('a[href*="download"]')
                if download_link:
                    url = download_link.get('href', '')
                    if url and not url.startswith('http'):
                        url = f"https://uibp.nchu.edu.tw{url}"
                    item["download_url"] = url

                if item:
                    step_data["content"].append(item)

            if step_data["title"]:
                steps.append(step_data)

        return steps

    def _parse_timeline(self, soup: BeautifulSoup) -> Dict:
        """解析重要時程"""
        timeline = {}

        # 找繳交期間
        deadline_elem = soup.select_one('.bg-n-golden')
        if deadline_elem:
            timeline["submission_period"] = deadline_elem.get_text(strip=True)

        # 找結果公告
        result_elems = soup.select('h3.text-n-lblue')
        for elem in result_elems:
            text = elem.get_text(strip=True)
            if '結果公告' in text:
                timeline["result_announcement"] = text
                break

        # 找注意事項
        note_elem = soup.select_one('.xl\\:text-\\[1\\.375rem\\]')
        if note_elem:
            timeline["note"] = note_elem.get_text(strip=True)

        return timeline

    def _parse_contact_info(self, soup: BeautifulSoup) -> Dict:
        """解析聯絡資訊（從 footer）"""
        contact = {}

        footer = soup.select_one('footer')
        if footer:
            # 取得單位名稱
            unit_elem = footer.select_one('h4')
            if unit_elem:
                contact["department"] = unit_elem.get_text(strip=True)

            # 取得聯絡資訊
            contact_items = footer.select('dd.flex.items-center')
            for item in contact_items:
                text = item.get_text(strip=True)
                if '台中市' in text or '興大路' in text:
                    contact["address"] = text
                elif 'TEL' in text:
                    contact["phone"] = text
                elif '@' in text:
                    contact["email"] = text

        # 從頁面內容取得承辦信箱
        page_text = soup.get_text()
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.edu\.tw', page_text)
        if email_match:
            contact["submission_email"] = email_match.group(0)

        return contact
