#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學圖書館申請借書證等表單文件"""

import logging
from typing import List, Dict

import httpx
from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class LibraryFormsScraper(BaseScraper):
    """圖書館表單文件爬蟲"""
    
    def __init__(self):
        super().__init__(
            source_url="https://www.lib.nchu.edu.tw/service.php?cID=11&Key=101",
            output_filename="library_forms.json",
            data_dir="forms"
        )
        self.base_url = "https://www.lib.nchu.edu.tw"
        self.keys = list(range(101, 109))
        
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': self.base_url,
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def scrape(self) -> List[str]:
        """爬取圖書館表單頁面（所有 key 101-108）"""
        html_contents = []
        
        try:
            with httpx.Client(
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                for key in self.keys:
                    url = f"https://www.lib.nchu.edu.tw/service.php?cID=11&Key={key}"
                    try:
                        logger.info(f"正在爬取 Key={key} 的頁面...")
                        response = client.get(url)
                        response.raise_for_status()
                        
                        logger.info(f"成功獲取 Key={key} 網頁，狀態碼: {response.status_code}")
                        html_contents.append(response.text)
                    
                    except httpx.HTTPStatusError as e:
                        logger.error(f"Key={key} HTTP 錯誤: {e.response.status_code} - {e}")
                    except httpx.RequestError as e:
                        logger.error(f"Key={key} 請求失敗: {e}")
                    except Exception as e:
                        logger.error(f"Key={key} 爬取過程發生錯誤: {e}", exc_info=True)
                
                return html_contents
                
        except Exception as e:
            logger.error(f"爬取過程發生錯誤: {e}", exc_info=True)
            return []
    
    def parse(self, html_contents: List[str]) -> List[Dict]:
        """解析圖書館表單資料（所有頁面）"""
        if not html_contents:
            return []
        
        all_forms = []
        
        for idx, html in enumerate(html_contents):
            if not html:
                continue
            
            key = self.keys[idx]
            logger.info(f"正在解析 Key={key} 的資料...")
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 找到所有的表單區塊 (sitemap_box)
            form_boxes = soup.find_all('div', class_='sitemap_box')
            logger.info(f"Key={key} 找到 {len(form_boxes)} 個表單區塊")
            
            for box in form_boxes:
                form_data = self._parse_form_box(box)
                if form_data:
                    form_data['source_key'] = key  # 記錄來源 key
                    all_forms.append(form_data)
        
        logger.info(f"總共成功解析 {len(all_forms)} 個表單")
        return all_forms
    
    def _parse_form_box(self, box) -> Dict:
        """解析單個表單區塊"""
        try:
            # 取得標題
            title_tag = box.find('h3')
            if not title_tag:
                return None
            
            title = title_tag.get_text(strip=True)
            
            # 取得所有檔案連結
            file_links = []
            links = box.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                if not href or href == '###':
                    continue
                
                # 取得連結文字
                link_text = link.get_text(strip=True)
                
                # 處理相對路徑
                if href.startswith('/'):
                    full_url = self.base_url + href
                elif not href.startswith('http'):
                    full_url = self.base_url + '/' + href
                else:
                    full_url = href
                
                # 判斷檔案類型
                file_type = self._get_file_type(href, link)
                
                if file_type:
                    file_links.append({
                        'url': full_url,
                        'type': file_type,
                        'description': link_text
                    })
            
            # 取得聯絡資訊
            contact_info = None

            # 方法1：從 span 標籤中找
            contact_spans = box.find_all('span')
            for span in contact_spans:
                text = span.get_text(strip=True)
                if text and (('組' in text or '室' in text) or '#' in text):
                    contact_info = text
                    break

            # 方法2：如果 span 找不到，從整個 box 的文字內容中找
            if not contact_info:
                # 獲取 box 的所有文字內容，並分行
                box_text = box.get_text()
                lines = box_text.split('\n')

                # 找出包含「組」或「室」且包含「#」的行
                for line in lines:
                    line = line.strip()
                    if line and ('組' in line or '室' in line) and '#' in line:
                        # 如果包含括號（例如 "(PDF)"），提取括號後的內容
                        if ')' in line:
                            last_paren = line.rfind(')')
                            after_paren = line[last_paren+1:].strip()
                            # 檢查括號後的內容是否包含組/室和#
                            if any(x in after_paren for x in ['組', '室']) and '#' in after_paren:
                                contact_info = after_paren
                                break

                        # 如果沒有括號，但不包含檔案副檔名，直接使用
                        if not contact_info and not any(ext in line for ext in ['.pdf', '.doc', '.odt', '.xls', '.ppt']):
                            contact_info = line
                            break

            # 取得描述文字 (如果有)
            description = None
            ul_tag = box.find('ul')
            if ul_tag:
                # 嘗試找到不在 a 標籤內的文字
                for li in ul_tag.find_all('li'):
                    # 移除所有 a 標籤後的文字
                    li_copy = li.__copy__()
                    for a in li_copy.find_all('a'):
                        a.decompose()
                    desc_text = li_copy.get_text(strip=True)
                    if desc_text and desc_text != contact_info:
                        description = desc_text
                        break
            
            form_data = {
                'title': title,
                'file_links': file_links,
            }

            # 統一使用 contact 欄位：優先使用 contact_info，沒有的話用 description
            if contact_info:
                form_data['contact'] = contact_info
            elif description:
                form_data['contact'] = description

            return form_data
            
        except Exception as e:
            logger.error(f"解析表單區塊時發生錯誤: {e}")
            return None
    
    def _get_file_type(self, href: str, link_tag) -> str:
        """判斷檔案類型"""
        # 從 URL 判斷
        href_lower = href.lower()
        if '.pdf' in href_lower:
            return 'PDF'
        elif '.docx' in href_lower:
            return 'DOCX'
        elif '.doc' in href_lower and '.docx' not in href_lower:
            return 'DOC'
        elif '.odt' in href_lower:
            return 'ODT'
        
        # 從 img 標籤的 alt 或 src 判斷
        img = link_tag.find('img')
        if img:
            alt = img.get('alt', '').lower()
            src = img.get('src', '').lower()
            
            if 'pdf' in alt or 'pdf' in src:
                return 'PDF'
            elif 'word' in alt or 'word' in src or 'doc' in src:
                return 'DOCX'
            elif 'odt' in alt or 'odt' in src:
                return 'ODT'
        
        return None
