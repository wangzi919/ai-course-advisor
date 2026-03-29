#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學研發處研發長辦公室教職員資料"""

import logging
from typing import List, Dict
from pathlib import Path
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class RDDirectorStaffScraper(BaseScraper):
    """研發處研發長辦公室教職員資料爬蟲"""

    def __init__(self):
        """初始化爬蟲"""
        super().__init__(
            source_url="https://research.nchu.edu.tw/about-1",
            output_filename="rd_director_staff.json",
            data_dir="staff/rdoffice"
        )

        # HTML cache 路徑 (在 staff/cache 目錄下)
        staff_dir = self.data_dir.parent  # 從 data/staff/rdoffice 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "rd_director_staff_cache.html"

    def scrape(self) -> str:
        """爬取教職員頁面（支援 HTML cache）"""
        # 檢查是否有快取的 HTML
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            try:
                with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"讀取快取失敗: {e}，將重新爬取")

        # 沒有快取，進行爬取（需要忽略 SSL 驗證）
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        try:
            logger.info(f"正在抓取: {self.source_url}")
            response = requests.get(
                self.source_url,
                headers=self.headers,
                timeout=10,
                verify=False  # 忽略 SSL 驗證警告
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            html = response.text
        except Exception as e:
            logger.error(f"抓取失敗 {self.source_url}: {str(e)}")
            return ""

        if not html:
            logger.error("無法取得教職員頁面")
            return ""

        # 儲存 HTML 快取
        try:
            with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML 已快取至: {self.html_cache_path}")
        except Exception as e:
            logger.warning(f"儲存 HTML 快取失敗: {e}")

        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """解析教職員資料"""
        if not raw_data:
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []

        # 找到所有教職員資料區塊 (每個 div class="item" 是一個職員)
        staff_divs = soup.find_all('div', class_='item')

        logger.info(f"找到 {len(staff_divs)} 個教職員區塊")

        for staff_div in staff_divs:
            staff_data = self._extract_staff_info(staff_div)
            if staff_data and staff_data['name']:
                staff_list.append(staff_data)

        return staff_list

    def _extract_staff_info(self, staff_div) -> Dict:
        """從 staff div 提取教職員資訊"""
        staff_info = {
            'name': '',
            'position': '',
            'department': '研發處研發長辦公室',
            'phone': '',
            'fax': '',
            'email': '',
            'website': '',
            'deputy': '',
            'photo_url': '',
            'responsibilities': []
        }

        try:
            # 提取姓名和職稱（在 h2 標籤中，格式：職稱 姓名）
            h2_tag = staff_div.find('h2')
            if h2_tag:
                full_text = h2_tag.get_text(strip=True)
                # 解析「職稱 姓名」格式
                # 例如: "研發長宋振銘教授", "秘書 李玉玲小姐", "行政組員 張雅惠小姐"

                # 先嘗試用空格分隔
                parts = full_text.split(' ', 1)
                if len(parts) == 2:
                    staff_info['position'] = parts[0].strip()
                    staff_info['name'] = parts[1].strip()
                elif len(parts) == 1:
                    # 沒有空格的情況，嘗試識別特定職稱
                    import re
                    # 處理 "研發長宋振銘教授" 或 "副研發長邱明斌教授" 格式
                    match = re.match(r'^(副?研發長)(.+)$', full_text)
                    if match:
                        staff_info['position'] = match.group(1)
                        staff_info['name'] = match.group(2)
                    else:
                        # 其他情況當作姓名
                        staff_info['name'] = full_text

            # 提取照片 URL
            img_tag = staff_div.find('img')
            if img_tag and img_tag.get('src'):
                staff_info['photo_url'] = img_tag.get('src')

            # 提取 profile 區域的資訊
            profile_div = staff_div.find('div', class_='profile')
            if profile_div:
                # 提取個人網頁
                web_link = profile_div.find('li', class_='icon-web')
                if web_link:
                    a_tag = web_link.find('a')
                    if a_tag and a_tag.get('href'):
                        staff_info['website'] = a_tag.get('href')

                # 提取電子信箱
                mail_link = profile_div.find('li', class_='icon-mail')
                if mail_link:
                    a_tag = mail_link.find('a')
                    if a_tag:
                        email = a_tag.get_text(strip=True)
                        staff_info['email'] = email

                # 提取電話
                tel_tag = profile_div.find('li', class_='icon-tel')
                if tel_tag:
                    staff_info['phone'] = tel_tag.get_text(strip=True)

                # 提取傳真
                fax_tag = profile_div.find('li', class_='icon-fax')
                if fax_tag:
                    staff_info['fax'] = fax_tag.get_text(strip=True)

                # 提取職務代理人
                deputy_p = profile_div.find('p')
                if deputy_p:
                    deputy_text = deputy_p.get_text(strip=True)
                    # 移除「職務代理：」前綴
                    if '：' in deputy_text:
                        staff_info['deputy'] = deputy_text.split('：', 1)[1]
                    else:
                        staff_info['deputy'] = deputy_text

            # 提取業務職掌
            business_div = staff_div.find('div', class_='business')
            if business_div:
                ol_tag = business_div.find('ol')
                if ol_tag:
                    li_tags = ol_tag.find_all('li')
                    for li in li_tags:
                        responsibility = li.get_text(strip=True)
                        if responsibility:
                            staff_info['responsibilities'].append(responsibility)

            logger.debug(f"解析職員: {staff_info['name']} - {staff_info['position']}")

        except Exception as e:
            logger.error(f"解析職員資料時發生錯誤: {e}")

        return staff_info
