#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學 EMI 教學資源中心工作坊資料"""

import logging
import re
from typing import List, Dict
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class EMIWorkshopsScraper(BaseScraper):
    """EMI 工作坊爬蟲"""

    def __init__(self):
        """初始化爬蟲"""
        super().__init__(
            source_url="https://emitlc.nchu.edu.tw/workshop",
            output_filename="emi_workshops.json",
            data_dir="activities"
        )
        self.base_url = "https://emitlc.nchu.edu.tw"

        # HTML cache 路徑
        self.html_cache_dir = self.data_dir / "emi_workshops_cache"
        self.html_cache_dir.mkdir(parents=True, exist_ok=True)

        # 工作坊類型
        self.workshop_types = {
            "1": "教師工作坊",
            "2": "TA工作坊"
        }

    def scrape(self) -> List[str]:
        """
        爬取所有工作坊類型的 HTML

        Returns:
            所有類型的 HTML 列表
        """
        all_pages_html = []

        for type_id, type_name in self.workshop_types.items():
            url = f"{self.source_url}?type={type_id}"
            cache_file = self.html_cache_dir / f"type_{type_id}.html"

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
                logger.error(f"無法取得 {type_name}")
                continue

            all_pages_html.append((html, type_id, type_name))
            logger.info(f"已爬取 {type_name}")

        logger.info(f"總共爬取了 {len(all_pages_html)} 種類型")
        return all_pages_html

    def parse(self, raw_data: List[tuple]) -> List[Dict]:
        """
        解析所有類型的工作坊資料

        Args:
            raw_data: 所有類型的 (HTML, type_id, type_name) 列表

        Returns:
            解析後的工作坊列表
        """
        if not raw_data:
            return []

        all_workshops = []

        for html, type_id, type_name in raw_data:
            soup = BeautifulSoup(html, 'html.parser')

            # 找到工作坊列表
            workshop_list = soup.find('ul', class_='workshop-list')
            if not workshop_list:
                logger.warning(f"{type_name} 沒有找到工作坊列表")
                continue

            workshop_items = workshop_list.find_all('li', class_='workshop-item')
            logger.info(f"{type_name} 找到 {len(workshop_items)} 個工作坊")

            for item in workshop_items:
                workshop_data = self._extract_workshop_info(item, type_id, type_name)
                if workshop_data and workshop_data['title']:
                    all_workshops.append(workshop_data)

        logger.info(f"總共解析出 {len(all_workshops)} 個工作坊")
        return all_workshops

    def _extract_workshop_info(self, item, type_id: str, type_name: str) -> Dict:
        """
        從工作坊項目中提取資訊

        Args:
            item: BeautifulSoup element (li)
            type_id: 工作坊類型 ID
            type_name: 工作坊類型名稱

        Returns:
            工作坊資料字典
        """
        workshop_info = {
            'title': '',
            'content': '',
            'event_date': '',
            'event_time': '',
            'location': '',
            'link': '',
            'images': [],
            'source_file': 'emi_workshops',
            'workshop_type': type_id,
            'workshop_type_name': type_name,
            'details': {
                'status': '',
                'registration_deadline': ''
            }
        }

        try:
            # 取得連結
            link_elem = item.find('a', class_='link')
            if link_elem and link_elem.get('href'):
                workshop_info['link'] = urljoin(self.base_url, link_elem['href'])

            # 取得圖片
            img_elem = item.find('img')
            if img_elem and img_elem.get('src'):
                img_url = img_elem['src']
                if img_url.startswith('http'):
                    workshop_info['images'].append(img_url)
                else:
                    workshop_info['images'].append(urljoin(self.base_url, img_url))

            # 取得狀態（已額滿、已截止等）
            status_elem = item.find('span', class_='status')
            if status_elem:
                workshop_info['details']['status'] = status_elem.get_text(strip=True)

            # 取得標題
            title_elem = item.find('p', class_='title')
            if title_elem:
                workshop_info['title'] = title_elem.get_text(strip=True)

            # 取得日期資訊
            date_elem = item.find('p', class_='date')
            if date_elem:
                # 取得日期文字，例如：「報名截止 2026-03-23 00:00」
                date_text = date_elem.get_text(strip=True)

                # 使用 time 標籤的內容
                time_elem = date_elem.find('time')
                if time_elem:
                    date_str = time_elem.get_text(strip=True)
                    # 解析日期時間
                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                        workshop_info['details']['registration_deadline'] = dt.isoformat()
                        # 只取日期部分作為 event_date
                        workshop_info['event_date'] = dt.strftime('%Y-%m-%d')
                    except ValueError:
                        logger.warning(f"無法解析日期: {date_str}")

                # 從文字中提取類型（報名截止、活動日期等）
                if '報名截止' in date_text:
                    workshop_info['details']['deadline_type'] = '報名截止'
                elif '活動日期' in date_text:
                    workshop_info['details']['deadline_type'] = '活動日期'

            # 設定 content 為標題（因為 HTML 中沒有更詳細的描述）
            workshop_info['content'] = workshop_info['title']

        except Exception as e:
            logger.error(f"解析工作坊資訊時發生錯誤: {e}", exc_info=True)
            return None

        return workshop_info if workshop_info['title'] else None
