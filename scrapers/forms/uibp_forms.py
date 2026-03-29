#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取興大校學士下載專區資料"""

import logging
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class UIBPFormsScraper(BaseScraper):
    """興大校學士文件下載爬蟲"""

    BASE_URL = "https://uibp.nchu.edu.tw/download.php?cID=1"

    def __init__(self):
        super().__init__(
            source_url="https://uibp.nchu.edu.tw/download.php?cID=1",
            output_filename="uibp_downloads.json",
            data_dir="forms",
            enable_hot_reload=True
        )

    def scrape(self) -> str:
        """爬取下載頁面"""
        html = self.fetch_page(self.BASE_URL)
        if not html:
            return ""
        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """解析下載資料"""
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        results = []

        # 尋找下載項目區塊
        # 通常下載項目會在特定的容器內
        download_items = soup.select(
            '.download_item, .file_item, .list-group-item')

        if not download_items:
            # 嘗試其他選擇器 - 找包含下載連結的區塊
            content_area = soup.select_one(
                '.content, .main-content, #content, .download_list')
            if content_area:
                download_items = self._parse_content_area(content_area)
            else:
                # 直接從整個頁面解析
                download_items = self._parse_from_links(soup)

        return download_items

    def _parse_content_area(self, content_area) -> List[Dict]:
        """從內容區域解析下載項目"""
        results = []

        # 找所有標題和連結
        current_item = None

        for elem in content_area.find_all(['h3', 'h4', 'p', 'div', 'a']):
            if elem.name in ['h3', 'h4']:
                # 儲存前一個項目
                if current_item and current_item.get('file_links'):
                    results.append(current_item)

                title = elem.get_text(strip=True)
                if title:
                    current_item = {
                        'title': title,
                        'file_links': []
                    }
            elif elem.name == 'a' and current_item:
                href = elem.get('href', '')
                if 'upload/download' in href or href.endswith(('.pdf', '.doc', '.docx', '.odt', '.xls', '.xlsx')):
                    file_url = urljoin(self.BASE_URL, href)
                    file_type = self._get_file_type(href)
                    link_text = elem.get_text(strip=True)

                    current_item['file_links'].append({
                        'url': file_url,
                        'type': link_text if link_text else file_type
                    })

        # 儲存最後一個項目
        if current_item and current_item.get('file_links'):
            results.append(current_item)

        return results

    def _parse_from_links(self, soup) -> List[Dict]:
        """直接從連結解析下載項目"""
        results = []

        # 找所有下載連結
        all_links = soup.find_all('a', href=True)

        for link in all_links:
            href = link.get('href', '')

            # 只處理下載連結
            if 'upload/download' not in href:
                continue

            file_url = urljoin(self.BASE_URL, href)
            file_type = self._get_file_type(href)
            link_text = link.get_text(strip=True)

            # 嘗試找到標題（往上尋找最近的標題元素）
            title = self._find_title_for_link(link)

            if not title:
                title = link_text if link_text and len(
                    link_text) > 5 else "未命名文件"

            # 檢查是否已有此標題的項目
            existing_item = None
            for item in results:
                if item['title'] == title:
                    existing_item = item
                    break

            if existing_item:
                # 新增檔案到現有項目
                existing_item['file_links'].append({
                    'url': file_url,
                    'type': link_text if link_text else file_type
                })
            else:
                # 建立新項目
                results.append({
                    'title': title,
                    'file_links': [{
                        'url': file_url,
                        'type': link_text if link_text else file_type
                    }]
                })

        logger.info(f"共解析 {len(results)} 筆下載項目")
        return results

    def _find_title_for_link(self, link) -> str:
        """尋找連結對應的標題"""
        # 往上尋找父元素中的標題
        parent = link.parent
        max_depth = 5
        depth = 0

        while parent and depth < max_depth:
            # 找同層級的標題
            title_elem = parent.find_previous_sibling(['h3', 'h4', 'h5'])
            if title_elem:
                return title_elem.get_text(strip=True)

            # 找父元素內的標題
            title_elem = parent.find(['h3', 'h4', 'h5'])
            if title_elem and title_elem != link:
                return title_elem.get_text(strip=True)

            # 檢查父元素的 class 或結構
            if parent.name in ['li', 'div', 'tr']:
                # 找這個容器內的標題文字
                text_parts = []
                for child in parent.children:
                    if hasattr(child, 'name') and child.name not in ['a', 'span']:
                        text = child.get_text(strip=True)
                        if text and len(text) > 3:
                            text_parts.append(text)
                    elif isinstance(child, str):
                        text = child.strip()
                        if text and len(text) > 3:
                            text_parts.append(text)

                if text_parts:
                    return text_parts[0]

            parent = parent.parent
            depth += 1

        return ""

    def _get_file_type(self, url: str) -> str:
        """從 URL 取得檔案類型"""
        url_lower = url.lower()
        if '.pdf' in url_lower:
            return 'PDF'
        elif '.docx' in url_lower:
            return 'DOCX'
        elif '.doc' in url_lower:
            return 'DOC'
        elif '.odt' in url_lower:
            return 'ODT'
        elif '.xlsx' in url_lower:
            return 'XLSX'
        elif '.xls' in url_lower:
            return 'XLS'
        elif '.pptx' in url_lower:
            return 'PPTX'
        elif '.ppt' in url_lower:
            return 'PPT'
        else:
            return 'FILE'
