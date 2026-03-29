#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學領域模組實施要點及課程資訊"""

import re
import time
import logging
import json
from typing import List, Dict, Tuple, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin
from datetime import datetime

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://oaa.nchu.edu.tw"
RULES_URL = f"{BASE_URL}/zh-tw/rule/download-list.0.0.L3%EF%BC%8D28"
MODULES_INDEX_URL = f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2923"

COLLEGE_PAGES: Dict[str, str] = {
    "文學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2943",
    "農資學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2944",
    "理學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2945",
    "工學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2946",
    "生命科學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2947",
    "獸醫學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.3169",
    "管理學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.3105",
    "法政學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2948",
    "電機資訊學院": f"{BASE_URL}/zh-tw/unit-page-p.342/page-list.2949",
}

REQUEST_DELAY = 0.5


class DomainModulesScraper(BaseScraper):
    """領域模組實施要點及課程資訊爬蟲"""

    def __init__(self):
        super().__init__(
            source_url=MODULES_INDEX_URL,
            output_filename="domain_modules.json",
            data_dir="modules",
        )
        self.base_url = BASE_URL
        self.rules_url = RULES_URL

        self.html_cache_dir = self.data_dir / "domain_modules_cache"
        self.html_cache_dir.mkdir(parents=True, exist_ok=True)

        self._rules_data: Dict = {}

    # ------------------------------------------------------------------ #
    # 快取工具                                                              #
    # ------------------------------------------------------------------ #

    def _fetch_cached(self, url: str, cache_name: str) -> str:
        cache_file = self.html_cache_dir / cache_name
        if cache_file.exists():
            logger.info(f"使用快取: {cache_file}")
            return cache_file.read_text(encoding="utf-8")
        html = self.fetch_page(url)
        if html:
            cache_file.write_text(html, encoding="utf-8")
            logger.info(f"HTML 已快取: {cache_file}")
        return html or ""

    # ------------------------------------------------------------------ #
    # scrape()                                                             #
    # ------------------------------------------------------------------ #

    def scrape(self) -> Dict:
        result: Dict[str, Any] = {"rules_html": "", "colleges": {}}

        logger.info("正在爬取領域模組實施要點...")
        result["rules_html"] = self._fetch_cached(self.rules_url, "rules.html")
        time.sleep(REQUEST_DELAY)

        for college, college_url in COLLEGE_PAGES.items():
            logger.info(f"正在爬取 [{college}] 模組列表...")
            safe = college.replace("/", "_")
            module_urls = self._collect_all_module_urls(college_url, safe)
            logger.info(f"[{college}] 找到 {len(module_urls)} 個模組")
            result["colleges"][college] = {"url": college_url, "modules": {}}

            for module_url in module_urls:
                mid = module_url.rstrip("/").split(".")[-1]
                html = self._fetch_cached(module_url, f"module_{mid}.html")
                if html:
                    result["colleges"][college]["modules"][module_url] = html
                time.sleep(REQUEST_DELAY)

        return result

    def _collect_all_module_urls(self, base_college_url: str, cache_prefix: str) -> List[str]:
        """取得某學院所有分頁中的模組 URL（處理分頁）。"""
        seen: set = set()
        urls: List[str] = []

        # 第一頁
        first_html = self._fetch_cached(base_college_url, f"college_{cache_prefix}_p0.html")
        if not first_html:
            logger.warning(f"[{cache_prefix}] 第一頁爬取失敗，跳過")
            return urls
        time.sleep(REQUEST_DELAY)

        urls += self._extract_module_urls(first_html, seen)

        # 找其餘分頁
        page_urls = self._extract_pagination_urls(first_html, base_college_url)
        for page_num, page_url in enumerate(page_urls, start=1):
            page_html = self._fetch_cached(page_url, f"college_{cache_prefix}_p{page_num}.html")
            if not page_html:
                logger.warning(f"[{cache_prefix}] 第 {page_num+1} 頁爬取失敗，跳過")
                continue
            time.sleep(REQUEST_DELAY)
            urls += self._extract_module_urls(page_html, seen)

        return urls

    def _extract_pagination_urls(self, html: str, base_url: str) -> List[str]:
        """從分頁列 (.page-limit) 取得除第一頁外的所有分頁 URL。"""
        soup = BeautifulSoup(html, "html.parser")
        pager = soup.find(class_="page-limit")
        if not pager:
            return []

        seen: set = {base_url}
        pages: List[str] = []
        skip_texts = {"下一頁", "最後一頁", "上一頁", "第一頁"}
        for a in pager.find_all("a", href=True):
            if a.get_text(strip=True) in skip_texts:
                continue
            full = a["href"] if a["href"].startswith("http") else urljoin(self.base_url, a["href"])
            if full not in seen:
                seen.add(full)
                pages.append(full)
        return pages

    def _extract_module_urls(self, html: str, seen: set = None) -> List[str]:
        if seen is None:
            seen = set()
        soup = BeautifulSoup(html, "html.parser")
        urls: List[str] = []
        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            if "page-detail" not in href:
                continue
            full = href if href.startswith("http") else urljoin(self.base_url, href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    # ------------------------------------------------------------------ #
    # parse()                                                              #
    # ------------------------------------------------------------------ #

    def parse(self, raw_data: Dict) -> List[Tuple[str, Dict]]:
        """
        解析所有頁面，回傳 [(key, module_dict), ...] 列表。
        key 格式為 "{主責教學單位}_{模組中文名稱}"。
        """
        self._rules_data = self._parse_rules(raw_data.get("rules_html", ""))
        logger.info(f"實施要點: {self._rules_data.get('title', '（未找到）')}")

        items: List[Tuple[str, Dict]] = []
        for college, college_data in raw_data.get("colleges", {}).items():
            for module_url, html in college_data.get("modules", {}).items():
                key, module = self._parse_module_detail(html, module_url, college)
                if key and module:
                    items.append((key, module))

        logger.info(f"共解析 {len(items)} 個領域模組")
        return items

    # ------------------------------------------------------------------ #
    # 解析實施要點                                                          #
    # ------------------------------------------------------------------ #

    def _parse_rules(self, html: str) -> Dict:
        if not html:
            return {}
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return {}
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < 3:
                continue
            title = cells[0].get_text(strip=True)
            if not title or title in ("文件標題",):
                continue
            description = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            unit = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            pdf_url = ""
            if len(cells) > 3:
                a = cells[3].find("a")
                if a and a.get("href"):
                    pdf_url = urljoin(self.base_url, a["href"])
            return {
                "title": title,
                "description": description,
                "publishing_unit": unit,
                "pdf_url": pdf_url,
                "source_url": self.rules_url,
            }
        return {}

    # ------------------------------------------------------------------ #
    # 解析單一模組詳細頁                                                    #
    # ------------------------------------------------------------------ #

    def _parse_module_detail(
        self, html: str, url: str, college: str
    ) -> Tuple[str, Dict]:
        """回傳 (key, module_dict)。解析失敗時回傳 ("", {})。"""
        if not html:
            return "", {}

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return "", {}

        # 只取主表格的直接子 tr（避免嵌套 table 的 tr 混入）
        tbody = table.find("tbody")
        container = tbody if tbody else table
        all_rows: List[Tag] = [
            ch for ch in container.children
            if isinstance(ch, Tag) and ch.name == "tr"
        ]

        # ---- 切分 架構計畫 / 模組總表 ---- #
        plan_rows: List[Tag] = []
        course_rows: List[Tag] = []
        in_courses = False

        _COURSE_SECTION_MARKERS = ("所有相關課程列表", "課程規劃內容如下")

        for row in all_rows:
            first_cell = row.find(["td", "th"])
            if first_cell and any(m in first_cell.get_text() for m in _COURSE_SECTION_MARKERS):
                in_courses = True
                continue
            if in_courses:
                course_rows.append(row)
            else:
                plan_rows.append(row)

        # ---- 提取模組代碼（從 h2，用於唯一識別） ---- #
        module_code = self._extract_module_code(soup)

        # ---- 解析 基本資訊 + 架構計畫 ---- #
        basic_info, plan_info = self._parse_plan_rows(plan_rows)

        # 用 h2 標題的系所全名覆蓋表格可能填寫的縮寫
        dept_from_title = self._extract_dept_from_title(soup)
        if dept_from_title:
            basic_info["主責教學單位"] = dept_from_title

        # 將代碼與學院加入 基本資訊
        if module_code:
            basic_info["模組代碼"] = module_code
        basic_info["學院"] = college

        # ---- 解析 模組總表 ---- #
        module_table = self._parse_course_rows(course_rows)

        # ---- 建立 key ---- #
        dept = basic_info.get("主責教學單位", "")
        name_zh = basic_info.get("中文", "")
        if not dept or not name_zh:
            return "", {}
        # 代碼納入 key 以確保唯一性（如有同名不同版本的模組）
        key = f"{dept}_{module_code}_{name_zh}" if module_code else f"{dept}_{name_zh}"

        module: Dict[str, Any] = {
            "基本資訊": basic_info,
            "架構計畫": plan_info,
            "模組總表": module_table,
            "超連結": url,
        }
        return key, module

    def _extract_module_code(self, soup: BeautifulSoup) -> str:
        """從 h2 標題提取模組代碼，如 U11-A01、U53F-A01 等。"""
        h2 = soup.find("h2")
        if not h2:
            return ""
        text = h2.get_text(strip=True)
        m = re.search(r'([A-Z]\d+[A-Z]?-[A-Z]\d+)', text)
        return m.group(1) if m else ""

    def _extract_dept_from_title(self, soup: BeautifulSoup) -> str:
        """從 h2 標題提取主責教學單位全名。
        h2 格式為 "{系所名稱}-{模組代碼}{模組名稱}"，例如 "電機工程學系-U64-D01半導體"。
        """
        h2 = soup.find("h2")
        if not h2:
            return ""
        text = h2.get_text(strip=True)
        m = re.search(r'([A-Z]\d+[A-Z]?-[A-Z]\d+)', text)
        if not m:
            return ""
        return text[:m.start()].rstrip("-").strip()

    # ---- 架構計畫 section -------------------------------------------- #

    def _parse_plan_rows(self, rows: List[Tag]) -> Tuple[Dict, Dict]:
        """解析 架構計畫 section 中的所有 key-value 列，回傳 (basic_info, plan_info)。"""
        # 先收集所有 key-value pairs
        kv: Dict[str, str] = {}
        convener_dept: str = ""
        convener_name: str = ""

        for row in rows:
            # recursive=False 避免嵌套 table 的 td 混入
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            # 使用 separator=" " 保留 <br/> 造成的空白
            key0 = cells[0].get_text(separator=" ", strip=True)

            # 跳過 section header（只有一格）
            if len(cells) == 1:
                continue

            # 特殊 4-cell 列：主責教學單位 | dept | 召集人 | name
            if len(cells) >= 4 and "主責教學單位" in key0:
                kv["主責教學單位"] = cells[1].get_text(strip=True)
                convener_dept = cells[1].get_text(strip=True)
                convener_name = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                continue

            # 一般 2-cell 列
            if len(cells) >= 2:
                val = self._cell_direct_text(cells[1])
                if key0:
                    kv[key0] = val

        dept = kv.get("主責教學單位", "")
        name_zh = kv.get("中文", "")
        name_en = kv.get("英文", "")
        start_time = kv.get("領域模組開始施行時間", "")

        basic_info: Dict[str, Any] = {
            "中文": name_zh,
            "英文": name_en,
            "領域模組預計開始施行時間": start_time,
            "主責教學單位": dept,
            "召集人": {convener_name: dept} if convener_name else {},
        }

        plan_info: Dict[str, str] = {
            "領域模組名稱": name_zh,
            "領域模組召集人": convener_name,
            "領域模組預計開始施行時間": start_time,
        }
        # 其餘 key-value 放入 plan_info
        skip = {"中文", "英文", "領域模組開始施行時間", "主責教學單位", "領域模組名稱"}
        for k, v in kv.items():
            if k not in skip:
                plan_info[k] = v

        return basic_info, plan_info

    def _cell_direct_text(self, cell: Tag) -> str:
        """取得 cell 的直接文字，略過嵌套 <table>。"""
        parts: List[str] = []
        for child in cell.children:
            if isinstance(child, Tag) and child.name == "table":
                break  # 遇到嵌套 table 就停
            if isinstance(child, Tag):
                text = child.get_text(separator=" ", strip=True)
            else:
                text = str(child).strip()
            if text:
                parts.append(text)
        return " ".join(parts).strip()

    # ---- 模組總表 section -------------------------------------------- #

    def _parse_course_rows(self, rows: List[Tag]) -> Dict:
        """
        解析課程列表表格（所有相關課程列表 section）。
        回傳 {"課程規劃內容": [...], "認證要求": {...}}。
        """
        courses: List[Dict] = []
        cert_req: Dict[str, str] = {}
        pending_data: Optional[Dict] = None

        # 追蹤備註跨課程 rowspan carry-over
        carried_remark: str = ""
        carried_remark_left: int = 0  # 還剩幾個 (中文) row 沿用此備註

        for row in rows:
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue

            first_text = cells[0].get_text(strip=True)

            # 認證要求列
            if "取得認證需修習總課程數" in first_text:
                cert_req = self._parse_cert_row(cells)
                continue

            # 附註列（略過）
            if first_text.startswith("附註"):
                continue

            # 標頭列（略過）
            if first_text in ("課程名稱", "1"):
                continue

            # 英文名稱列
            if first_text.startswith("(英文)"):
                en_name = first_text[4:].strip()
                if pending_data is not None:
                    pending_data["課程名稱_英文"] = en_name
                    courses.append(pending_data)
                    pending_data = None
                continue

            # 中文課程列（有 規劃要點 欄位）
            if first_text.startswith("(中文)") and len(cells) >= 7:
                zh_name = first_text[4:].strip()
                plan_vals = self._extract_plan_values(cells)
                dept_unit = cells[7].get_text(strip=True) if len(cells) > 7 else ""

                # 備註：有 cell 時更新 carry；否則沿用前一個跨 rowspan 的值
                if len(cells) > 8:
                    remark_cell = cells[8]
                    carried_remark = remark_cell.get_text(strip=True)
                    rs = int(remark_cell.get("rowspan") or 2)
                    # rowspan 以 2 為單位（zh+en 各算一行），換算剩餘課程數
                    carried_remark_left = rs // 2 - 1
                elif carried_remark_left > 0:
                    carried_remark_left -= 1
                else:
                    carried_remark = ""

                if pending_data is not None:
                    courses.append(pending_data)

                pending_data = {
                    "課程名稱_中文": zh_name,
                    "課程名稱_英文": "",
                    "規劃要點": plan_vals,
                    "開課單位": dept_unit,
                    "備註": carried_remark,
                }
                continue

        # 最後一筆可能沒有英文名稱列
        if pending_data is not None:
            courses.append(pending_data)

        return {
            "課程規劃內容": courses,
            "認證要求": cert_req,
        }

    def _extract_plan_values(self, cells: List[Tag]) -> Dict[str, str]:
        """從課程資料列提取 規劃要點 欄位 1-6。"""
        # cells[0]=課程名稱(colspan=4), cells[1-6]=規劃要點 1-6
        vals: Dict[str, str] = {}
        col_indices = range(1, 7)
        for i, idx in enumerate(col_indices):
            if idx < len(cells):
                vals[str(i + 1)] = cells[idx].get_text(strip=True)
        return vals

    def _parse_cert_row(self, cells: List[Tag]) -> Dict[str, str]:
        """解析 取得認證需修習總課程數 / 總學分數 列。"""
        result: Dict[str, str] = {}
        # 通常是 4-cell 列：key1 | val1 | key2 | val2
        if len(cells) >= 2:
            result[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)
        if len(cells) >= 4:
            result[cells[2].get_text(strip=True)] = cells[3].get_text(strip=True)
        return result

    # ------------------------------------------------------------------ #
    # save_data() — 覆寫：輸出 dict 格式                                   #
    # ------------------------------------------------------------------ #

    def _load_rules_text(self) -> Dict[str, str]:
        """從 oaa_regulations.json 載入 L3-28 領域模組實施要點條文。"""
        regulations_path = self.data_dir.parent / "rules" / "oaa_regulations.json"
        if not regulations_path.exists():
            logger.warning(f"找不到規章檔案: {regulations_path}")
            return {}
        try:
            with open(regulations_path, encoding="utf-8") as f:
                reg_data = json.load(f)
            # 找 L3-28 的 key
            key = next((k for k in reg_data if "L3-28" in k), None)
            if not key:
                logger.warning("oaa_regulations.json 中找不到 L3-28 條目")
                return {}
            articles: Dict[str, str] = reg_data[key]
            logger.info(f"已載入 L3-28 條文，共 {len(articles)} 條")
            return articles
        except Exception as e:
            logger.error(f"載入規章條文失敗: {e}")
            return {}

    def save_data(self, data: List[Tuple[str, Dict]]):
        """將模組列表轉換為 dict 格式並儲存。"""
        modules_dict: Dict[str, Dict] = {}
        for key, module in data:
            modules_dict[key] = module

        # 載入實施要點條文
        rules_articles = self._load_rules_text()
        rules = {
            **self._rules_data,
            "articles": rules_articles,
            "full_text": "\n\n".join(rules_articles.values()) if rules_articles else "",
        }

        result = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(modules_dict),
                "data_source": self.source_url,
                "rules_source": self.rules_url,
                "規劃要點說明": {
                    "1": "U-學士課程、M-碩士課程",
                    "2": "A-正課、B-實習課、C-台下指導之科目如學生講述或邀請演講之專題討論、專題研究……等",
                    "3": "R-必修、E-選修",
                    "4": "S-學期課、Y-學年課",
                    "5": "科目（學期或全年）總學分數（阿拉伯數字）",
                    "6": "Level：1-基礎課程、2-核心(理論/方法)課程、3-應用(總整/實務)課程（阿拉伯數字）",
                },
            },
            "rules": rules,
            "data": modules_dict,
        }

        try:
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"資料已儲存至: {self.output_path}")
            logger.info(
                f"Metadata - 最後更新: {result['metadata']['last_updated']}, "
                f"總數: {result['metadata']['total_count']}"
            )
            if self.enable_hot_reload:
                self._trigger_hot_reload()
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {e}")

    # ------------------------------------------------------------------ #
    # run() — 覆寫以配合 List[Tuple] 格式                                  #
    # ------------------------------------------------------------------ #

    def run(self):
        logger.info("=" * 50)
        logger.info(f"開始爬取: {self.source_url}")
        logger.info("=" * 50)

        raw_data = self.scrape()
        if not raw_data:
            logger.warning("未抓取到任何資料")
            return {}

        parsed = self.parse(raw_data)
        self.save_data(parsed)

        logger.info("=" * 50)
        logger.info(f"爬蟲完成! 共抓取 {len(parsed)} 筆資料")
        logger.info("=" * 50)
        return dict(parsed)
