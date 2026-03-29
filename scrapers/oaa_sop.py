#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學教務處 SOP 標準作業流程"""

import logging
import re
from typing import List, Dict
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class OAASOPScraper(BaseScraper):
    """教務處 SOP 標準作業流程爬蟲"""

    def __init__(self):
        """初始化爬蟲"""
        super().__init__(
            source_url="https://oaa.nchu.edu.tw/zh-tw/sop",
            output_filename="oaa_sop.json",
            data_dir="sop"
        )
        self.base_url = "https://oaa.nchu.edu.tw"

        # HTML cache 路徑
        self.html_cache_dir = self.data_dir / "oaa_sop_cache"
        self.html_cache_dir.mkdir(parents=True, exist_ok=True)

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

        # 檢查快取
        if cache_file.exists():
            logger.info(f"使用快取的 HTML: {cache_file}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    html = f.read()
            except Exception as e:
                logger.warning(f"讀取快取失敗: {e}，將重新爬取")
                html = self.fetch_page(url)
        else:
            html = self.fetch_page(url)
            if html:
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.info(f"HTML 已快取至: {cache_file}")
                except Exception as e:
                    logger.warning(f"儲存 HTML 快取失敗: {e}")

        if not html:
            logger.error("無法取得第一頁")
            return []

        # 解析第一頁以獲取總頁數
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

        sop_items = tbody.find_all('tr')
        logger.info(f"第 1 頁找到 {len(sop_items)} 個 SOP")

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
                # URL 格式：/zh-tw/sop/download-list.0.XX.
                # 提取 offset
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
                url = f"{self.base_url}/zh-tw/sop/download-list.0.{offset}."
                cache_file = self.html_cache_dir / f"page_{page_num}.html"

                # 檢查快取
                if cache_file.exists():
                    logger.info(f"使用快取的 HTML: {cache_file}")
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            html = f.read()
                    except Exception as e:
                        logger.warning(f"讀取快取失敗: {e}，將重新爬取")
                        html = self.fetch_page(url)
                else:
                    html = self.fetch_page(url)
                    if html:
                        try:
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                f.write(html)
                            logger.info(f"HTML 已快取至: {cache_file}")
                        except Exception as e:
                            logger.warning(f"儲存 HTML 快取失敗: {e}")

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
                            logger.info(f"已爬取第 {page_num} 頁，找到 {len(items)} 個 SOP")
                        else:
                            logger.warning(f"第 {page_num} 頁沒有 SOP 項目")
                    else:
                        logger.warning(f"第 {page_num} 頁沒有 tbody")
                else:
                    logger.warning(f"第 {page_num} 頁沒有表格")

        logger.info(f"總共爬取了 {len(all_pages_html)} 頁")
        return all_pages_html

    def parse(self, raw_data: List[str]) -> List[Dict]:
        """
        解析所有頁面的 SOP 資料

        Args:
            raw_data: 所有頁面的 HTML 列表

        Returns:
            解析後的 SOP 列表
        """
        if not raw_data:
            return []

        all_sops = []

        for page_num, html in enumerate(raw_data, start=1):
            soup = BeautifulSoup(html, 'html.parser')

            # 找到表格中的所有 SOP 項目
            table = soup.find('table')
            if not table:
                logger.warning(f"第 {page_num} 頁沒有找到表格")
                continue

            tbody = table.find('tbody')
            if not tbody:
                logger.warning(f"第 {page_num} 頁沒有找到 tbody")
                continue

            sop_items = tbody.find_all('tr')
            logger.info(f"第 {page_num} 頁找到 {len(sop_items)} 個 SOP")

            for item in sop_items:
                sop_data = self._extract_sop_info(item)
                if sop_data and sop_data['title']:
                    all_sops.append(sop_data)

        logger.info(f"總共解析出 {len(all_sops)} 個 SOP")
        return all_sops

    def _extract_sop_info(self, item) -> Dict:
        """
        從 SOP 項目中提取資訊

        Args:
            item: BeautifulSoup element (tr)

        Returns:
            SOP 資料字典
        """
        sop_info = {
            'title': '',
            'description': '',
            'department': '',
            'file_links': []
        }

        try:
            # 取得所有 td 元素
            tds = item.find_all('td')
            if len(tds) < 4:
                logger.warning(f"表格行的 td 數量不足：{len(tds)}")
                return None

            # 第一個 td：SOP 標題
            title_elem = tds[0].find('h3', class_='text')
            if title_elem:
                sop_info['title'] = title_elem.get_text(strip=True)

            # 第二個 td：說明
            desc_elem = tds[1].find('div')
            if desc_elem:
                sop_info['description'] = desc_elem.get_text(strip=True)

            # 第三個 td：發佈單位
            unit_elem = tds[2].find('div', class_='skin-label')
            if unit_elem:
                sop_info['department'] = unit_elem.get_text(strip=True)

            # 第四個 td：下載連結
            download_area = tds[3].find('div', class_='btn-wrap')
            if download_area:
                file_links = []
                for link in download_area.find_all('a', href=True):
                    href = link['href']
                    # 轉換為絕對 URL
                    absolute_url = urljoin(self.base_url, href)

                    # 提取檔案類型和大小資訊（例如：PDF(100.5 KB)）
                    link_text = link.get_text(strip=True)

                    # 解析檔案類型和大小
                    # 格式：PDF(100.5 KB) 或 DOCX(20.1 KB)
                    if '(' in link_text and ')' in link_text:
                        file_type = link_text.split('(')[0].strip()
                        file_size = link_text.split('(')[1].replace(')', '').strip()
                    else:
                        file_type = link_text
                        file_size = ''

                    file_info = {
                        'url': absolute_url,
                        'type': file_type,
                        'size': file_size
                    }

                    file_links.append(file_info)

                sop_info['file_links'] = file_links

        except Exception as e:
            logger.error(f"解析 SOP 資訊時發生錯誤: {e}")

        return sop_info if sop_info['title'] else None
