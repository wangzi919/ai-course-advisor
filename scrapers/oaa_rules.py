#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學教務處規章"""

import logging
import re
import json
from typing import List, Dict, Any
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Chinese numeral to integer conversion
_CN_DIGITS = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9
}


def _chinese_to_int(cn: str) -> int:
    """Convert Chinese numeral string to integer.

    Supports numbers up to 百 (hundreds).
    Examples: 一 → 1, 十二 → 12, 二十 → 20, 一百零一 → 101
    """
    if not cn:
        return 0

    result = 0
    current = 0

    for char in cn:
        if char in _CN_DIGITS:
            current = _CN_DIGITS[char]
        elif char == '十':
            if current == 0:
                current = 1
            result += current * 10
            current = 0
        elif char == '百':
            if current == 0:
                current = 1
            result += current * 100
            current = 0

    result += current
    return result


# Regex patterns for article splitting
_ARTICLE_PATTERN = re.compile(r'(第[一二三四五六七八九十百零]+條)')
_ITEM_PATTERN = re.compile(r'([一二三四五六七八九十百零]+、)')


class OAARulesScraper(BaseScraper):
    """教務處規章爬蟲"""

    def __init__(self):
        """初始化爬蟲"""
        super().__init__(
            source_url="https://oaa.nchu.edu.tw/zh-tw/rule",
            output_filename="oaa_regulations.json",
            data_dir="rules"
        )
        self.base_url = "https://oaa.nchu.edu.tw"

        # HTML cache 路徑
        self.html_cache_dir = self.data_dir / "oaa_rules_cache"
        self.html_cache_dir.mkdir(parents=True, exist_ok=True)

        # PDF cache 路徑
        self.pdf_cache_dir = self.data_dir / "oaa_rules_pdf_cache"
        self.pdf_cache_dir.mkdir(parents=True, exist_ok=True)

    def scrape(self) -> List[str]:
        """
        爬取所有頁面的 HTML

        Returns:
            所有頁面的 HTML 列表
        """
        all_pages_html = []

        # 先爬取第一頁以獲取總頁數
        url = self.source_url
        cache_file = self.html_cache_dir / "page_1.html"

        html = self._fetch_with_cache(url, cache_file)
        if not html:
            logger.error("無法取得第一頁")
            return []

        soup = BeautifulSoup(html, 'html.parser')
        all_pages_html.append(html)

        # 檢查表格
        table = soup.find('table')
        if not table:
            logger.warning("第一頁沒有找到表格")
            return all_pages_html

        tbody = table.find('tbody')
        if not tbody:
            logger.warning("第一頁沒有找到 tbody")
            return all_pages_html

        items = tbody.find_all('tr')
        logger.info(f"第 1 頁找到 {len(items)} 個規章")

        # 查找分頁信息
        page_limit = soup.find('div', class_='page-limit')
        if not page_limit:
            logger.info("沒有分頁，只有一頁")
            return all_pages_html

        # 從「最後一頁」連結中獲取最大 offset
        last_page_link = page_limit.find('li', class_='last')
        max_offset = 0
        total_pages = 1

        if last_page_link:
            link = last_page_link.find('a')
            if link:
                href = link.get('href', '')
                # URL 格式：/zh-tw/rule/download-list.0.XX.
                parts = href.split('.')
                if len(parts) >= 3:
                    try:
                        max_offset = int(parts[-2])
                        total_pages = (max_offset // 10) + 1
                        logger.info(f"檢測到共 {total_pages} 頁（offset 0 到 {max_offset}）")
                    except ValueError:
                        logger.warning(f"無法解析 offset: {href}")

        # 爬取其餘頁面
        if total_pages > 1:
            for page_num in range(2, total_pages + 1):
                offset = (page_num - 1) * 10
                url = f"{self.base_url}/zh-tw/rule/download-list.0.{offset}."
                cache_file = self.html_cache_dir / f"page_{page_num}.html"

                html = self._fetch_with_cache(url, cache_file)
                if not html:
                    logger.warning(f"無法取得第 {page_num} 頁")
                    continue

                # 檢查是否有內容
                soup = BeautifulSoup(html, 'html.parser')
                table = soup.find('table')
                if table:
                    tbody = table.find('tbody')
                    if tbody:
                        items = tbody.find_all('tr')
                        if items:
                            all_pages_html.append(html)
                            logger.info(f"已爬取第 {page_num} 頁，找到 {len(items)} 個規章")
                        else:
                            logger.warning(f"第 {page_num} 頁沒有規章項目")
                    else:
                        logger.warning(f"第 {page_num} 頁沒有 tbody")
                else:
                    logger.warning(f"第 {page_num} 頁沒有表格")

        logger.info(f"總共爬取了 {len(all_pages_html)} 頁")
        return all_pages_html

    def _fetch_with_cache(self, url: str, cache_file: Path) -> str:
        """
        帶快取的頁面抓取

        Args:
            url: 要抓取的 URL
            cache_file: 快取檔案路徑

        Returns:
            HTML 內容
        """
        if cache_file.exists():
            logger.info(f"使用快取的 HTML: {cache_file}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"讀取快取失敗: {e}，將重新爬取")

        html = self.fetch_page(url)
        if html:
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info(f"HTML 已快取至: {cache_file}")
            except Exception as e:
                logger.warning(f"儲存 HTML 快取失敗: {e}")

        return html

    def parse(self, raw_data: List[str]) -> Dict[str, Dict[str, str]]:
        """
        解析所有頁面的規章資料

        Args:
            raw_data: 所有頁面的 HTML 列表

        Returns:
            平面字典格式的規章資料
        """
        if not raw_data:
            return {}

        all_rules = {}

        for page_num, html in enumerate(raw_data, start=1):
            soup = BeautifulSoup(html, 'html.parser')

            table = soup.find('table')
            if not table:
                logger.warning(f"第 {page_num} 頁沒有找到表格")
                continue

            tbody = table.find('tbody')
            if not tbody:
                logger.warning(f"第 {page_num} 頁沒有找到 tbody")
                continue

            items = tbody.find_all('tr')
            logger.info(f"第 {page_num} 頁找到 {len(items)} 個規章")

            for item in items:
                rule = self._extract_rule_info(item)
                if not rule:
                    continue

                pdf_name = rule['pdf_name']
                pdf_url = rule['pdf_url']

                if not pdf_url:
                    logger.warning(f"規章 {rule['title']} 沒有 PDF 下載連結")
                    continue

                # 下載 PDF
                pdf_path = self._download_pdf(pdf_url, pdf_name)
                if not pdf_path:
                    logger.warning(f"下載 PDF 失敗: {pdf_name}")
                    continue

                # 提取 PDF 文字
                text = self._extract_pdf_text(pdf_path)
                if not text:
                    logger.warning(f"無法提取 PDF 文字: {pdf_name}")
                    continue

                # 解析條文
                key = pdf_name[:-4] if pdf_name.endswith('.pdf') else pdf_name
                articles = self._parse_articles(text)
                all_rules[key] = articles
                logger.info(f"已解析: {key}（{len(articles)} 條）")

        logger.info(f"總共解析出 {len(all_rules)} 個規章")
        return all_rules

    def _extract_rule_info(self, item) -> Dict:
        """
        從規章項目中提取資訊

        Args:
            item: BeautifulSoup element (tr)

        Returns:
            規章資料字典，或 None
        """
        try:
            tds = item.find_all('td')
            if len(tds) < 4:
                return None

            # 第一個 td：規章標題
            title = ''
            title_elem = tds[0].find('h3', class_='text')
            if title_elem:
                title = title_elem.get_text(strip=True)

            if not title:
                return None

            # 第四個 td：下載連結
            pdf_url = ''
            pdf_name = ''
            download_area = tds[3].find('div', class_='btn-wrap')
            if download_area:
                for link in download_area.find_all('a', href=True):
                    href = link['href']
                    link_text = link.get_text(strip=True).upper()
                    # 優先取 PDF 連結
                    if 'PDF' in link_text:
                        absolute_url = urljoin(self.base_url, href)
                        pdf_url = absolute_url
                        # 從 URL 的 name 參數提取檔名
                        parsed = urlparse(absolute_url)
                        qs = parse_qs(parsed.query)
                        if 'name' in qs:
                            pdf_name = qs['name'][0]
                        break

            return {
                'title': title,
                'pdf_url': pdf_url,
                'pdf_name': pdf_name,
            }

        except Exception as e:
            logger.error(f"解析規章資訊時發生錯誤: {e}")
            return None

    def _download_pdf(self, url: str, filename: str) -> Path:
        """
        下載 PDF 到快取目錄

        Args:
            url: PDF 下載 URL
            filename: PDF 檔名

        Returns:
            PDF 檔案路徑，或 None
        """
        if not filename:
            import hashlib
            filename = hashlib.md5(url.encode()).hexdigest() + '.pdf'

        pdf_path = self.pdf_cache_dir / filename

        # 檢查快取
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            logger.debug(f"使用快取的 PDF: {pdf_path}")
            return pdf_path

        try:
            logger.info(f"下載 PDF: {filename}")
            response = self.session.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            with open(pdf_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"PDF 已儲存至: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"下載 PDF 失敗 {url}: {e}")
            return None

    @staticmethod
    def _extract_pdf_text(pdf_path: Path) -> str:
        """
        使用 PyMuPDF 提取 PDF 文字

        Args:
            pdf_path: PDF 檔案路徑

        Returns:
            提取的文字
        """
        try:
            import fitz  # PyMuPDF

            text_parts = []
            with fitz.open(str(pdf_path)) as doc:
                for page in doc:
                    text_parts.append(page.get_text())

            return '\n'.join(text_parts)

        except Exception as e:
            logger.error(f"提取 PDF 文字失敗 {pdf_path}: {e}")
            return ''

    @staticmethod
    def _parse_articles(text: str) -> Dict[str, str]:
        """
        從 PDF 文字中解析條文

        支援兩種格式：
        1. 第X條 格式（如「第一條」、「第二十條」）
        2. X、格式（如「一、」、「二、」）— 作為 fallback

        使用順序編號檢查來區分真正的條文標頭與內文中引用其他法規的「第X條」。

        Args:
            text: PDF 全文

        Returns:
            {條號: 條文內容} 字典
        """
        # 移除換行符號，產生連續文字
        text_flat = text.replace('\n', '').strip()

        if not text_flat:
            return {"1": ""}

        # 優先使用「第X條」格式
        splits = _ARTICLE_PATTERN.split(text_flat)
        if len(splits) > 1:
            # 收集所有 marker 及其編號
            markers = []
            for i in range(1, len(splits), 2):
                marker = splits[i]
                content = splits[i + 1] if i + 1 < len(splits) else ""
                cn_num = marker.replace('第', '').replace('條', '')
                num = _chinese_to_int(cn_num)
                markers.append((marker, content, num))

            # 找到第一條作為錨點
            anchor_idx = 0
            for idx, (_, _, num) in enumerate(markers):
                if num == 1:
                    anchor_idx = idx
                    break

            # 從錨點開始，使用順序編號檢查來篩選真正的條文
            # 允許最多 +3 的間隔（處理少數被刪除的條文）
            articles = {}
            last_num = 0
            current_parts = []

            for idx in range(anchor_idx, len(markers)):
                marker, content, num = markers[idx]

                if num > last_num and num <= last_num + 3:
                    # 順序遞增 → 新的條文
                    if last_num > 0:
                        articles[str(last_num)] = ''.join(current_parts).strip()
                    current_parts = [marker, content]
                    last_num = num
                else:
                    # 非順序 → 內文引用，合併到當前條文
                    current_parts.extend([marker, content])

            if last_num > 0:
                articles[str(last_num)] = ''.join(current_parts).strip()

            if articles:
                return articles

        # Fallback：「X、」格式
        splits = _ITEM_PATTERN.split(text_flat)
        if len(splits) > 1:
            articles = {}
            for i in range(1, len(splits), 2):
                marker = splits[i]
                content = splits[i + 1] if i + 1 < len(splits) else ""
                cn_num = marker.replace('、', '')
                article_num = _chinese_to_int(cn_num)
                if article_num > 0:
                    articles[str(article_num)] = (marker + content).strip()
            if articles:
                return articles

        # 最終 fallback：整段文字存為 "1"
        return {"1": text_flat}

    def save_data(self, data: Any):
        """
        覆寫 BaseScraper 的 save_data，以平面字典格式儲存（不包裹 metadata）

        Args:
            data: 規章字典 {規章名: {條號: 條文}}
        """
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.info(f"資料已儲存至: {self.output_path}")
            logger.info(f"共 {len(data)} 個規章")

            # 觸發熱重載
            if self.enable_hot_reload:
                self._trigger_hot_reload()

        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {str(e)}")
