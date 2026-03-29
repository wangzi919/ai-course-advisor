"""
爬蟲：學習規劃諮詢服務頁面
資料來源：https://interdisciplinary.nchu.edu.tw/consult
輸出：data/uibp/academic_advising_consultation.json

頁面結構：
  H1: 學習規劃諮詢服務
    H2: 關於學習規劃諮詢（第一個）
      H3: 我們是誰？
      H3: 我們能幫你什麼？
    H2: 如何預約學習規劃諮詢服務？
    H2: 如何開立學習規劃諮詢證明？
    H2: 關於學習規劃諮詢（第二個）
      H3: 專任學習規劃師諮詢
      H3: 學習規劃導師制度
      H3: 更多資訊請見學習規劃諮詢網頁
"""

import logging
import re
from typing import Dict, List

from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class ConsultationServiceScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_url="https://interdisciplinary.nchu.edu.tw/consult",
            output_filename="academic_advising_consultation.json",
            data_dir="uibp",
            cache_hours=24,
        )

    def scrape(self) -> str:
        resp = self.session.get(self.source_url, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    def parse(self, raw_data: str) -> List[Dict]:
        soup = BeautifulSoup(raw_data, "html.parser")

        # 找出所有 h2 和其下屬內容
        h2_sections = self._split_by_h2(soup)

        result = {}

        about_count = 0
        for title, section_soup in h2_sections:
            if title == "關於學習規劃諮詢":
                about_count += 1
                if about_count == 1:
                    result["關於學習規劃諮詢"] = self._parse_about_first(section_soup)
                else:
                    result["關於學習規劃諮詢服務"] = self._parse_about_second(section_soup)
            elif "預約" in title:
                result["如何預約學習規劃諮詢服務"] = self._parse_appointment(section_soup)
            elif "證明" in title:
                result["如何開立學習規劃諮詢證明"] = self._parse_certificate(section_soup)

        # 更多資訊
        result["更多資訊請見學習規劃諮詢網頁"] = self._parse_more_info(soup)

        return [result]

    def _split_by_h2(self, soup: BeautifulSoup) -> list:
        """將頁面按 h2 切分為多個區段，搜尋 h2 所在父容器內的所有子元素"""
        sections = []
        h2s = soup.find_all("h2")
        for h2 in h2s:
            title = h2.get_text(strip=True)
            parent = h2.parent
            sections.append((title, parent))
        return sections

    def _parse_about_first(self, container: Tag) -> Dict:
        """關於學習規劃諮詢（第一個）：我們是誰？＋我們能幫你什麼？"""
        subtitles = {}
        for h3 in container.find_all("h3"):
            h3_title = h3.get_text(strip=True)
            # 找 h3 後面最近的 p
            p = h3.find_next("p")
            subtitles[h3_title] = p.get_text(strip=True) if p else ""
        return subtitles

    def _parse_appointment(self, container: Tag) -> Dict:
        """如何預約學習規劃諮詢服務：流程圖片 + 預約連結"""
        url = ""
        flow_image_url = ""
        for img in container.find_all("img"):
            src = img.get("src", "")
            if src and "link-arrow" not in src:
                flow_image_url = src
        for a in container.find_all("a", href=True):
            text = a.get_text(strip=True)
            if "預約" in text:
                url = a["href"]

        return {
            "流程圖片": flow_image_url,
            "預約連結": {
                "label": "預約學習規劃諮詢",
                "url": url,
            },
        }

    def _parse_certificate(self, container: Tag) -> str:
        """如何開立學習規劃諮詢證明"""
        p = container.find("p")
        if p:
            return p.get_text(strip=True)
        return ""

    def _parse_about_second(self, container: Tag) -> Dict:
        """關於學習規劃諮詢（第二個）：專任學習規劃師諮詢 + 學習規劃導師制度"""
        subtitles = {}
        h3s = container.find_all("h3")
        for h3 in h3s:
            h3_title = h3.get_text(strip=True)
            if "更多資訊" in h3_title:
                continue
            entry = {"說明": "", "url": None}
            p = h3.find_next("p")
            if p:
                entry["說明"] = p.get_text(strip=True)
            # 找該 h3 區塊中的連結（在下一個 h3 之前）
            next_h3 = h3.find_next_sibling("h3") if h3.parent else None
            for a in h3.find_all_next("a", href=True):
                if next_h3 and a.sourceline and next_h3.sourceline and a.sourceline >= next_h3.sourceline:
                    break
                href = a["href"]
                if href.startswith("http"):
                    entry["url"] = {
                        "label": a.get_text(strip=True),
                        "url": href,
                    }
                    break
            subtitles[h3_title] = entry
        return subtitles

    def _parse_more_info(self, soup: BeautifulSoup) -> Dict:
        """更多資訊請見學習規劃諮詢網頁"""
        url = ""
        for a in soup.find_all("a", href=True):
            if "了解更多" in a.get_text(strip=True):
                url = a["href"]
                break
        return {
            "label": "了解更多",
            "url": url,
        }
