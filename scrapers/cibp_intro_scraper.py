"""
爬蟲：院學士介紹頁面
資料來源：https://interdisciplinary.nchu.edu.tw/uibp
輸出：data/uibp/cibp_intro.json

頁面結構：
  H1: 院學士是什麼
    figure13.svg: 整合院內課程(主題/領域)
    figure14.svg: 以雙主修形式修讀
    figure15.svg: 畢業學分至少128學分
    figure16.svg: 院學士學位畢業學分
    inline SVG:   參照各學院院學士修讀規定（含 5 個學院 QR code）

備註：頁面文字皆以 SVG path 向量方式呈現，非 <text> 元素，
      因此以人工判讀後寫入結構化文字，搭配圖片 URL 儲存。
"""

import logging
from typing import Dict, List

from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# 各學院名稱對應的 QR code 圖片順序（從 inline SVG 的 <image> 標籤依序取得）
COLLEGE_NAMES = [
    "農資院院學士",
    "理學院院學士",
    "管理學院院學士",
    "工學院院學士",
    "文學院院學士",
]


class CibpIntroScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_url="https://interdisciplinary.nchu.edu.tw/uibp",
            output_filename="cibp_intro.json",
            data_dir="uibp",
        )

    def scrape(self) -> str:
        resp = self.session.get(self.source_url, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    def parse(self, raw_data: str) -> List[Dict]:
        soup = BeautifulSoup(raw_data, "html.parser")
        editor = soup.find("div", class_="editor")
        if not editor:
            logger.warning("找不到 editor 區塊")
            return []

        w15 = editor.find("div", class_="w15")
        if not w15:
            logger.warning("找不到 w15 區塊")
            return []

        sections = self._parse_sections(w15)
        return [sections]

    def _parse_sections(self, container: Tag) -> Dict:
        result = {}

        # 取得所有 <picture> 中的 figure SVG URL（figure13~16）
        pictures = container.find_all("picture", class_="figure")
        figure_urls = {}
        for pic in pictures:
            img = pic.find("img")
            if img:
                src = img.get("src", "")
                if "figure13" in src:
                    figure_urls["figure13"] = self._get_picture_urls(pic)
                elif "figure14" in src:
                    figure_urls["figure14"] = self._get_picture_urls(pic)
                elif "figure15" in src:
                    figure_urls["figure15"] = self._get_picture_urls(pic)
                elif "figure16" in src:
                    figure_urls["figure16"] = self._get_picture_urls(pic)

        # 1. 整合院內課程(主題/領域)
        result["整合院內課程"] = {
            "說明": "重新檢視與革新課程架構，整合多元、跨領域之學習機會，學生得不限於就讀學系，修習更彈性且多元的課程。",
            "圖片": figure_urls.get("figure13", {}),
        }

        # 2. 以雙主修形式修讀
        result["以雙主修形式修讀"] = {
            "說明": "學士班學生於修業年限最後一年第一學期註冊日前，於行事曆規定之申請期限內，依公告提出申請。",
            "圖片": figure_urls.get("figure14", {}),
        }

        # 3. 畢業學分至少128學分
        result["畢業學分至少128學分"] = {
            "說明": [
                {"路徑": "所屬學系＋院學士畢業", "結果": "取得雙學位"},
                {"路徑": "放棄原所屬學系，以院學士學位畢業", "結果": "取得院學士學位"},
                {"路徑": "放棄院學士，以原就讀學系畢業", "結果": "取得所屬學系學位"},
            ],
            "圖片": figure_urls.get("figure15", {}),
        }

        # 4. 院學士學位畢業學分
        result["院學士學位畢業學分"] = {
            "說明": {
                "畢業學分至少": "128學分",
                "組成": [
                    "校共同必修及通識科目",
                    "院指定必修科目",
                    "領域模組",
                    "選修科目",
                ],
            },
            "圖片": figure_urls.get("figure16", {}),
        }

        # 5. 參照各學院院學士修讀規定（inline SVG 區塊）
        result["參照各學院院學士修讀規定"] = self._parse_college_requirements(container)

        return result

    def _get_picture_urls(self, picture: Tag) -> Dict:
        urls = {}
        sources = picture.find_all("source")
        for source in sources:
            srcset = source.get("srcset", "")
            media = source.get("media", "")
            if "max-width" in media:
                urls["mobile"] = srcset
            elif "min-width" in media:
                urls["desktop"] = srcset
        img = picture.find("img")
        if img:
            urls["default"] = img.get("src", "")
        return urls

    def _parse_college_requirements(self, container: Tag) -> List[Dict]:
        """解析「參照各學院院學士修讀規定」區塊中的 QR code 圖片"""
        colleges = []

        # 找到含有 inline SVG 的最後一個 div（包含 desktop 和 mobile 版本）
        all_divs = [d for d in container.find_all("div", recursive=False)]
        if not all_divs:
            return colleges

        last_div = all_divs[-1]
        # 從桌面版 SVG（width=1300）取得 image href
        svgs = last_div.find_all("svg")
        for svg in svgs:
            w = svg.get("width", "")
            if w == "1300":
                images = svg.find_all("image")
                for i, img in enumerate(images):
                    href = img.get("href", "") or img.get("xlink:href", "")
                    if href and i < len(COLLEGE_NAMES):
                        colleges.append({
                            "學院": COLLEGE_NAMES[i],
                            "QR_code圖片": href,
                        })
                break

        return colleges
