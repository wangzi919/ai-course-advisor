#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學校友中心人員職務資料"""

import re
import json
from typing import List, Dict
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class AlumniStaffScraper(BaseScraper):
    """校友中心人員職務資料爬蟲"""

    def __init__(self):
        super().__init__(
            source_url="https://alumni.nchu.edu.tw/team.php",
            output_filename="alumni_staff.json",
            data_dir="staff/alumni",
        )

        # HTML 快取路徑
        staff_dir = self.data_dir.parent  # data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "alumni_staff_cache.html"

        # 校友中心位置（由 parse 時解析並儲存）
        self._location = ""

    def scrape(self) -> str:
        """
        爬取網頁內容
        回傳: HTML 字串
        """
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            with open(self.html_cache_path, "r", encoding="utf-8") as f:
                return f.read()

        html = self.fetch_page(self.source_url)
        if not html:
            logger.error("無法爬取校友中心網頁")
            return ""

        try:
            with open(self.html_cache_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"HTML 已快取至: {self.html_cache_path}")
        except Exception as e:
            logger.warning(f"無法儲存 HTML 快取: {e}")

        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """
        解析爬取的資料。

        頁面結構：
          <h3>組別名稱</h3>
          <div class="row">
            <div class="col-lg-4 col-md-6 mb-5">
              <div class="member-card">
                <div class="top-box">
                  <div class="name">姓名（職務代理）</div>
                  <span>職稱</span>
                </div>
                <div class="item">  <!-- 電話 -->
                <div class="item">  <!-- 信箱 -->
                <div class="item">  <!-- 負責業務 -->
              </div>
            </div>
            ...
          </div>

        回傳: 結構化資料列表
        """
        if not raw_data:
            logger.warning("沒有資料可解析")
            return []

        # 從主頁面提取位置
        loc_match = re.search(r'\d+號\s*(行政大樓\d+樓)', raw_data)
        self._location = loc_match.group(1) if loc_match else ""
        if self._location:
            logger.debug(f"找到校友中心位置: {self._location}")

        soup = BeautifulSoup(raw_data, "html.parser")
        results = []

        # 以 h3 為組別分隔點
        section_headings = soup.find_all("h3")
        logger.info(f"找到 {len(section_headings)} 個組別")

        for h3 in section_headings:
            section_name = h3.get_text(strip=True)
            logger.info(f"解析組別: {section_name}")

            # h3 的下一個兄弟 div.row 是該組的人員容器
            row_div = h3.find_next_sibling("div", class_="row")
            if not row_div:
                logger.warning(f"找不到 [{section_name}] 的人員列表")
                continue

            cards = row_div.find_all("div", class_="member-card")
            logger.info(f"[{section_name}] 找到 {len(cards)} 位人員")

            for card in cards:
                try:
                    # ── 姓名與是否為職務代理 ──────────────────────
                    name_div = card.find("div", class_="name")
                    raw_name = name_div.get_text(strip=True) if name_div else ""

                    is_acting = "職務代理" in raw_name
                    name = re.sub(r"[（(]職務代理[）)]", "", raw_name).strip()

                    # ── 職稱 ─────────────────────────────────────
                    top_box = card.find("div", class_="top-box")
                    pos_span = top_box.find("span") if top_box else None
                    position = pos_span.get_text(strip=True) if pos_span else ""
                    if is_acting:
                        position = f"{position}（職務代理）"

                    # ── 聯絡資訊（電話 / 信箱 / 負責業務）─────────
                    phone = email = responsibilities = ""
                    for item in card.find_all("div", class_="item"):
                        item_tag = item.find("div", class_="item-tag")
                        item_content = item.find("div", class_="item-content")
                        if not item_tag or not item_content:
                            continue

                        label = item_tag.get_text(strip=True)
                        if "電話" in label:
                            a = item_content.find("a")
                            phone = a.get_text(strip=True) if a else item_content.get_text(strip=True)
                        elif "信箱" in label:
                            a = item_content.find("a", href=re.compile(r"^mailto:"))
                            email = (
                                a["href"].replace("mailto:", "").strip()
                                if a
                                else item_content.get_text(strip=True)
                            )
                        elif "負責業務" in label:
                            responsibilities = item_content.get_text(strip=True)

                    if not name:
                        continue

                    staff_data = {
                        "name": name,
                        "position": position,
                        "department": "校友中心",
                        "section": section_name,
                        "phone": phone,
                        "email": email,
                        "is_acting": is_acting,
                        "responsibilities": responsibilities,
                    }

                    results.append(staff_data)
                    logger.debug(f"成功解析: {name} ({position}) - {section_name}")

                except Exception as e:
                    logger.error(f"[{section_name}] 解析人員資料失敗: {e}", exc_info=True)
                    continue

        logger.info(f"成功解析 {len(results)} 位人員資料")
        return results


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


def main():
    """測試用主函式"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    scraper = AlumniStaffScraper()
    scraper.force_update()


if __name__ == "__main__":
    main()
