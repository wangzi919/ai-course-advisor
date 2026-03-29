#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學圖書館活動資訊"""

import logging
import re
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper

# 使用標準 logging,讓 run_*.py 的設定統一管理
logger = logging.getLogger(__name__)


class LibraryActivitiesScraper(BaseScraper):
    """圖書館活動資訊爬蟲"""

    def __init__(self):
        super().__init__(
            source_url="https://www.lib.nchu.edu.tw/news.php?cID=4",
            output_filename="library_news.json",
            data_dir="news",
            enable_hot_reload=False  # 不在此處觸發熱重載，統一由 unify_news.py 處理
        )
        self.base_url = "https://www.lib.nchu.edu.tw"

    def _extract_event_dates(self, title: str, content: str, publish_date: str) -> Tuple[Optional[str], Optional[str]]:
        """
        從標題和內容中提取活動日期和時間

        Args:
            title: 活動標題
            content: 活動內容
            publish_date: 發布日期

        Returns:
            Tuple[event_date, event_time]: (活動日期, 活動時間)
        """
        event_date = None
        event_time = None
        current_year = datetime.now().year

        # 清除內容中的換行符號
        content_cleaned = content.replace('\n', ' ').strip()

        # 1. 從標題中提取日期範圍 (例如: "2025/11/18～2025/11/20" 或 "11/14(五)")
        # 優先匹配有年份的日期
        title_date_pattern = r'(\d{4})/(\d{1,2})/(\d{1,2})'
        title_matches = re.findall(title_date_pattern, title)
        if title_matches:
            year, month, day = title_matches[0]
            event_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            # 如果標題沒有年份，嘗試匹配無年份日期 11/14(五)
            title_no_year_pattern = r'(\d{1,2})/(\d{1,2})\s*[（(][一二三四五六日][）)]'
            title_no_year_match = re.search(title_no_year_pattern, title)
            if title_no_year_match:
                month, day = title_no_year_match.groups()
                event_date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"

        # 2. 從內容中提取活動時間（支援全形和半形括號）
        content_patterns = [
            # 有年份的日期範圍加時間: 2025/11/19(三) ~ 11/20(四) 10:00-16:00
            r'(\d{4})/(\d{1,2})/(\d{1,2})\s*[（(][一二三四五六日][）)]\s*[~～]\s*\d{1,2}/\d{1,2}\s*[（(][一二三四五六日][）)]\s*(\d{1,2}:\d{2})\s*[-~～–]\s*(\d{1,2}:\d{2})',
            # 時間｜11/14（五）9:00–12:00 （支援全形括號和全形破折號）
            r'時間[：:｜|]\s*(\d{1,2})/(\d{1,2})\s*[（(][一二三四五六日][）)]\s*(\d{1,2}:\d{2})\s*[-~～–]\s*(\d{1,2}:\d{2})',
            # 活動時間: 11/18(二)19:00-20:00
            r'活動時間[：:]\s*(\d{1,2})/(\d{1,2})\s*[（(][一二三四五六日][）)]\s*(\d{1,2}:\d{2})\s*[-~～–]\s*(\d{1,2}:\d{2})',
            # 時間: 2025年11月18日 or 2025/11/18
            r'時間[：:｜|]\s*(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})',
            # 有年份的日期: 2025/11/19(三)
            r'(\d{4})/(\d{1,2})/(\d{1,2})\s*[（(][一二三四五六日][）)]',
            # 無年份日期加時間: 11/18(二) 19:00
            r'(\d{1,2})/(\d{1,2})\s*[（(][一二三四五六日][）)]\s*(\d{1,2}:\d{2})',
            # 活動期間: 11/6－11/22 or 11/6-11/22
            r'期間[：:]*\s*(\d{1,2})/(\d{1,2})\s*[-－]',
            # 報名截止: 報名至2025/11/5
            r'報名至\s*(\d{4})/(\d{1,2})/(\d{1,2})',
        ]

        for pattern in content_patterns:
            match = re.search(pattern, content_cleaned)
            if match:
                groups = match.groups()

                # 判斷是否包含年份
                if len(groups) >= 3 and len(groups[0]) == 4:  # 有年份
                    year, month, day = groups[0], groups[1], groups[2]
                    if not event_date:
                        event_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    if len(groups) >= 4:  # 有時間
                        event_time = f"{groups[3]} ~ {groups[4] if len(groups) > 4 else groups[3]}"
                elif len(groups) >= 2:  # 沒有年份，使用當前年份
                    month, day = groups[0], groups[1]
                    if not event_date:
                        event_date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"
                    if len(groups) >= 3 and ':' in str(groups[2]):  # 有時間
                        event_time = groups[2]
                        if len(groups) >= 4:
                            event_time += f" ~ {groups[3]}"
                break

        # 3. 如果還是沒有日期，嘗試從 publish_date 推測
        if not event_date and publish_date:
            try:
                pub_date = datetime.strptime(publish_date, "%Y-%m-%d")
                if re.search(r'今[天日]|即日', content_cleaned):
                    event_date = publish_date
                elif re.search(r'明[天日]', content_cleaned):
                    from datetime import timedelta
                    next_day = pub_date + timedelta(days=1)
                    event_date = next_day.strftime("%Y-%m-%d")
            except:
                pass

        return event_date, event_time

    def _extract_location(self, content: str) -> Optional[str]:
        """
        從內容中提取活動地點

        Args:
            content: 活動內容

        Returns:
            活動地點
        """
        content_cleaned = content.replace('\n', ' ').strip()

        location_patterns = [
            r'活動地點[：:]\s*([^\n。，]+)',
            r'地點[：:]\s*([^\n。，]+)',
            r'於\s*([^，。]+?)[，。]',
            r'SITE[：:]\s*([^\n]+)',
        ]

        for pattern in location_patterns:
            match = re.search(pattern, content_cleaned)
            if match:
                location = match.group(1).strip()
                # 清理一些常見的干擾文字
                location = re.sub(r'\([^\)]*\)', '', location).strip()
                # 限制長度避免抓到太長的文字
                if len(location) < 50:
                    return location

        return None
    
    def scrape(self) -> List[Dict]:
        """爬取活動列表和詳細資訊"""
        # 1. 抓取列表頁
        html = self.fetch_page(self.source_url)
        if not html:
            return []
        
        # 2. 解析活動列表
        activities = self._parse_news_list(html)
        if not activities:
            logger.warning("未找到任何活動")
            return []
        
        # 3. 抓取每個活動的詳細資訊
        for idx, activity in enumerate(activities, 1):
            logger.info(f"正在處理第 {idx}/{len(activities)} 個活動: {activity['title']}")
            
            detail_html = self.fetch_page(activity['link'])
            if detail_html:
                activity['html'] = detail_html
            
            time.sleep(0.5)  # 避免請求過快
        
        return activities
    
    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """解析活動詳細資訊"""
        parsed_activities = []

        for activity in raw_data:
            if 'html' not in activity:
                continue

            detail = self._parse_activity_detail(
                activity['html'],
                activity['link'],
                activity['title']
            )

            # 合併標題和詳細資訊
            parsed_activity = {
                'title': activity['title'],
                **detail
            }

            parsed_activities.append(parsed_activity)

        return parsed_activities
    
    def _parse_news_list(self, html: str) -> List[Dict]:
        """解析活動列表頁面"""
        soup = BeautifulSoup(html, 'html.parser')
        news_items = soup.find_all('a', href=lambda x: x and 'news_detail.php' in x)
        
        logger.info(f"找到 {len(news_items)} 個活動項目")
        
        activities = []
        for item in news_items:
            try:
                title = item.get('title', '').strip()
                link = item.get('href', '')
                
                if link and not link.startswith('http'):
                    link = f"{self.base_url}/{link.lstrip('/')}"
                
                if title and link:
                    activities.append({'title': title, 'link': link})
            except Exception as e:
                logger.error(f"解析活動項目時發生錯誤: {str(e)}")
        
        return activities
    
    def _parse_activity_detail(self, html: str, link: str, title: str = '') -> Dict:
        """解析單個活動詳細頁面"""
        soup = BeautifulSoup(html, 'html.parser')
        detail = {
            'link': link,
            'author': '',
            'publish_date': '',
            'content': '',
            'images': [],
            'event_date': None,
            'event_time': None,
            'location': None
        }

        try:
            # 解析作者和日期
            author_date_elem = soup.find('div', class_='n_d_time')
            if author_date_elem:
                full_text = author_date_elem.get_text(strip=True)

                if '｜' in full_text:
                    parts = full_text.split('｜')
                    detail['author'] = parts[0].replace('作者', '').strip()
                    if len(parts) > 1:
                        detail['publish_date'] = parts[1].replace('發佈日', '').strip()

            # 解析內容和圖片
            content_area = soup.find('div', class_='n_d_content')
            if content_area:
                detail['content'] = content_area.get_text(strip=True)

                # 解析圖片
                images = content_area.find_all('img')
                for img in images:
                    img_src = img.get('src', '')
                    if img_src:
                        if not img_src.startswith('http'):
                            img_src = f"{self.base_url}/{img_src.lstrip('/')}"
                        detail['images'].append(img_src)

                # 提取活動日期和時間
                event_date, event_time = self._extract_event_dates(
                    title, detail['content'], detail['publish_date']
                )
                detail['event_date'] = event_date
                detail['event_time'] = event_time

                # 提取活動地點
                detail['location'] = self._extract_location(detail['content'])

        except Exception as e:
            logger.error(f"解析活動詳情時發生錯誤 {link}: {str(e)}")

        return detail