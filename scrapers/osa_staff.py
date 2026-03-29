#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學學務處職員資料"""

import logging
import json
import re
from typing import List, Dict
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class OSAStaffScraper(BaseScraper):
    """學務處職員資料爬蟲（支援多單位）"""

    # 單位設定：單位代碼 -> (單位名稱, 資料來源 URL, 資料類型)
    UNITS = {
        'dean': ('學務長', 'https://www.osa.nchu.edu.tw/osa/dean.html', 'html'),
        'deputy': ('副學務長', 'https://www.osa.nchu.edu.tw/osa/deputy.html', 'html'),
        'office': ('學務長室', 'https://www.osa.nchu.edu.tw/osa/js/staff.json', 'json'),
        'arm': ('學安室', 'https://www.osa.nchu.edu.tw/osa/arm/js/staff.json', 'json'),
        'laa': ('生活輔導組', 'https://www.osa.nchu.edu.tw/osa/laa/js/staff.json', 'json'),
        'act': ('課外活動組', 'https://www.osa.nchu.edu.tw/osa/act/staff_detail.html', 'html'),
        'cdc': ('生涯發展中心', 'https://www.osa.nchu.edu.tw/osa/cdc/js/staff.json', 'json'),
        'dorm': ('住宿輔導組', 'https://www.osa.nchu.edu.tw/osa/dorm/js/staff.json', 'json'),
        'isrc': ('原資中心', 'https://www.osa.nchu.edu.tw/osa/cdc/isrc/about.html', 'html'),
    }

    def __init__(self, unit_code="office"):
        """
        初始化爬蟲

        Args:
            unit_code: 單位代碼（dean, deputy, office, arm, laa, act, cdc, dorm, isrc）
        """
        if unit_code not in self.UNITS:
            raise ValueError(f"無效的單位代碼: {unit_code}，可用代碼: {list(self.UNITS.keys())}")

        self.unit_code = unit_code
        self.unit_name, source_url, self.data_type = self.UNITS[unit_code]

        super().__init__(
            source_url=source_url,
            output_filename=f"osa_staff_{unit_code}.json",
            data_dir="staff/osa"
        )

        # HTML cache 路徑
        staff_dir = self.data_dir.parent
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / f"osa_staff_{unit_code}_cache.html"

        # 各處室位置（由 scrape 或 parse 時解析並儲存）
        self._location = ""

        # JSON 型態單位需額外抓 HTML 主頁以取得位置資訊
        if self.data_type == 'json' and '/js/' in self.source_url:
            unit_base = self.source_url.rsplit('/js/', 1)[0]
            self.location_page_url = unit_base + '/'
            self.location_cache_path = cache_dir / f"osa_staff_{unit_code}_location_cache.html"
        else:
            self.location_page_url = None
            self.location_cache_path = None

    @staticmethod
    def _extract_location(html_text: str) -> str:
        """從 HTML 頁面中提取處室位置（地址號碼後面的建築物+樓層）"""
        try:
            soup = BeautifulSoup(html_text, 'html.parser')
            for tag in soup.find_all(['a', 'p', 'li']):
                text = tag.get_text(strip=True)
                if '號' in text and len(text) < 80:
                    match = re.search(
                        r'\d+號\s+([\u4e00-\u9fff]+[樓館堂棟][\s\u4e00-\u9fff0-9]*)',
                        text
                    )
                    if match:
                        return match.group(1).strip()
        except Exception as e:
            logger.warning(f"提取位置時發生錯誤: {e}")
        return ""

    def _fetch_location_for_json_unit(self):
        """為 JSON 型態的單位抓取 HTML 主頁以取得位置資訊（支援快取）"""
        if not self.location_page_url:
            return

        # 先嘗試讀取快取
        if self.location_cache_path and self.location_cache_path.exists():
            try:
                with open(self.location_cache_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                self._location = self._extract_location(html)
                logger.debug(f"從位置快取讀取: {self._location}")
                return
            except Exception as e:
                logger.warning(f"讀取位置快取失敗: {e}")

        # 從網路抓取
        logger.info(f"抓取位置頁面: {self.location_page_url}")
        location_html = self.fetch_page(self.location_page_url)
        if location_html:
            self._location = self._extract_location(location_html)
            logger.info(f"解析到位置: {self._location}")
            if self.location_cache_path:
                try:
                    with open(self.location_cache_path, 'w', encoding='utf-8') as f:
                        f.write(location_html)
                except Exception as e:
                    logger.warning(f"儲存位置快取失敗: {e}")

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

    def scrape(self) -> str:
        """爬取職員頁面（支援 HTML cache）"""
        # 檢查是否有快取的 HTML
        if self.html_cache_path.exists():
            logger.info(f"使用快取的 HTML: {self.html_cache_path}")
            try:
                with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"讀取快取失敗: {e}，將重新爬取")

        # 沒有快取，進行爬取
        html = self.fetch_page(self.source_url)
        if not html:
            logger.error("無法取得職員頁面")
            return ""

        # 儲存 HTML 快取（只有 HTML 類型才需要）
        if self.data_type == 'html':
            try:
                with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info(f"HTML 已快取至: {self.html_cache_path}")
            except Exception as e:
                logger.warning(f"儲存 HTML 快取失敗: {e}")

        # JSON 型態單位額外抓取主頁以取得位置資訊
        if self.data_type == 'json' and self.location_page_url:
            self._fetch_location_for_json_unit()

        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """解析職員資料"""
        if not raw_data:
            return []

        # HTML 型態單位：從 raw_data 中提取位置資訊
        if self.data_type == 'html':
            self._location = self._extract_location(raw_data)

        # 根據資料類型選擇解析方法
        if self.data_type == 'json':
            return self._parse_json(raw_data)
        else:  # html
            if self.unit_code in ['dean', 'deputy']:
                return self._parse_dean_html(raw_data)
            elif self.unit_code == 'isrc':
                return self._parse_isrc_html(raw_data)
            else:  # act
                return self._parse_staff_html(raw_data)

    def _parse_json(self, raw_data: str) -> List[Dict]:
        """解析 JSON 格式的職員資料"""
        try:
            staff_json = json.loads(raw_data)
            logger.info(f"成功解析 JSON，找到 {len(staff_json)} 個職員")

            staff_list = []
            for item in staff_json:
                # 組合姓名和職稱
                name = f"{item.get('name', '')} {item.get('title', '')}".strip()

                # 處理 status 欄位（如：南投校區宿舍）
                status = item.get('status', '').strip()
                if status:
                    name = f"{name} ({status})"

                # 組合單位名稱（如果有 status，也加入單位中）
                department = f'學務處{self.unit_name}'
                if status:
                    department = f'學務處{self.unit_name} - {status}'

                staff_data = {
                    'name': name,
                    'department': department,
                    'phone': item.get('phone', ''),
                    'email': item.get('email', ''),
                    'deputy': item.get('substitute', item.get('note', '')),
                    'responsibilities': self._format_responsibilities(item.get('job', ''))
                }

                # 過濾空姓名
                if staff_data['name'] and '待聘' not in staff_data['name']:
                    staff_list.append(staff_data)

            return staff_list

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失敗: {e}")
            return []

    def _parse_dean_html(self, raw_data: str) -> List[Dict]:
        """解析學務長/副學務長 HTML 頁面"""
        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []

        # 從圖片 alt 屬性提取姓名
        name = ''
        # 先嘗試找包含「副學務長」的圖片（更明確）
        img_tag = soup.find('img', alt=re.compile(r'副學務長'))
        if not img_tag:
            # 如果沒找到，再找包含「學務長」的圖片
            img_tag = soup.find('img', alt=re.compile(r'學務長'))

        if img_tag and img_tag.get('alt'):
            alt_text = img_tag['alt']
            # 提取姓名（如：副學務長吳嘉哲 -> 吳嘉哲 副學務長）
            name_match = re.search(r'(副?學務長)?([^\s]+)(副?學務長)?', alt_text)
            if name_match:
                # 如果是「副學務長XXX」格式
                if '副學務長' in alt_text:
                    staff_name = re.search(r'副學務長(.+)', alt_text)
                    if staff_name:
                        name = f"{staff_name.group(1)} 副學務長"
                # 如果是「XXX學務長」格式
                elif '學務長' in alt_text and '副' not in alt_text:
                    staff_name = re.search(r'(.+)學務長', alt_text)
                    if staff_name:
                        name = f"{staff_name.group(1)} 學務長"

        # 提取聯絡方式
        phone = ''
        email = ''
        contact_section = soup.find('h3', string=re.compile('聯絡方式'))
        if contact_section:
            contact_ul = contact_section.find_next('ul')
            if contact_ul:
                for li in contact_ul.find_all('li'):
                    text = li.get_text(strip=True)
                    if '電話' in text:
                        phone = text.replace('電話：', '').replace('電話:', '').strip()
                    elif '信箱' in text or 'mail' in text.lower():
                        email_tag = li.find('a')
                        if email_tag:
                            email = email_tag.get_text(strip=True)

        # 提取學歷
        education = []
        edu_section = soup.find('h3', string=re.compile('學歷'))
        if edu_section:
            edu_ul = edu_section.find_next('ul')
            if edu_ul:
                education = [li.get_text(strip=True) for li in edu_ul.find_all('li')]

        # 提取經歷
        experience = []
        exp_section = soup.find('h3', string=re.compile('經歷'))
        if exp_section:
            exp_ul = exp_section.find_next('ul')
            if exp_ul:
                experience = [li.get_text(strip=True) for li in exp_ul.find_all('li')]

        # 組合職責資訊
        responsibilities = []
        if education:
            responsibilities.append('【學歷】')
            responsibilities.extend([f"- {item}" for item in education])
        if experience:
            responsibilities.append('【經歷】')
            responsibilities.extend([f"- {item}" for item in experience])

        staff_data = {
            'name': name,
            'department': f'學務處{self.unit_name}',
            'phone': phone,
            'email': email,
            'deputy': '',
            'responsibilities': '\n'.join(responsibilities)
        }

        if staff_data['name']:
            staff_list.append(staff_data)

        return staff_list

    def _parse_staff_html(self, raw_data: str) -> List[Dict]:
        """解析一般職員 HTML 頁面（課外活動組等）"""
        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []

        # 找到所有職員區塊
        team_divs = soup.find_all('div', class_='team team-list')
        logger.info(f"找到 {len(team_divs)} 個職員區塊")

        for team_div in team_divs:
            staff_data = self._extract_staff_from_team_div(team_div)
            if staff_data and staff_data['name']:
                staff_list.append(staff_data)

        return staff_list

    def _extract_staff_from_team_div(self, team_div) -> Dict:
        """從 team div 提取職員資訊"""
        staff_info = {
            'name': '',
            'department': f'學務處{self.unit_name}',
            'phone': '',
            'email': '',
            'deputy': '',
            'responsibilities': ''
        }

        try:
            # 提取姓名和職稱
            team_info = team_div.find('div', class_='team-info')
            if team_info:
                h5 = team_info.find('h5')
                span = team_info.find('span')
                if h5:
                    name = h5.get_text(strip=True)
                    position = span.get_text(strip=True) if span else ''
                    # 處理換行符號的職稱（如：行政辦事員(職代)<br>楊小姐(育嬰留停)）
                    position = position.replace('\n', ' ')
                    staff_info['name'] = f"{name} {position}".strip()

            # 提取聯絡資訊
            team_contact = team_div.find('div', class_='team-contact')
            if team_contact:
                # 電話
                call_span = team_contact.find('span', class_='call')
                if call_span:
                    # 移除 icon 標籤
                    icon = call_span.find('i')
                    if icon:
                        icon.decompose()
                    staff_info['phone'] = call_span.get_text(strip=True)

                # Email
                email_span = team_contact.find('span', class_='email')
                if email_span:
                    email_tag = email_span.find('a')
                    if email_tag:
                        staff_info['email'] = email_tag.get_text(strip=True)

                # 職務代理人
                deputy_spans = [s for s in team_contact.find_all('span')
                               if '職務代理' in s.get_text() or '代理' in s.get_text()]
                if deputy_spans:
                    deputy_text = deputy_spans[0].get_text(strip=True)
                    staff_info['deputy'] = deputy_text.replace('職務代理人：', '').strip()

            # 提取業務執掌
            team_description = team_div.find('div', class_='team-description')
            if team_description:
                ul = team_description.find('ul', class_='list-02')
                if ul:
                    responsibilities = []
                    for li in ul.find_all('li'):
                        resp = li.get_text(strip=True)
                        if resp:
                            responsibilities.append(f"- {resp}")
                    staff_info['responsibilities'] = '\n'.join(responsibilities)

        except Exception as e:
            logger.error(f"解析職員資訊時發生錯誤: {e}")

        return staff_info if staff_info['name'] else None

    def _parse_isrc_html(self, raw_data: str) -> List[Dict]:
        """解析原資中心 HTML 頁面"""
        soup = BeautifulSoup(raw_data, 'html.parser')
        staff_list = []

        # 找到 s02 區塊（原資團隊）
        s02_anchor = soup.find('a', attrs={'name': 's02'})
        if not s02_anchor:
            logger.warning("未找到原資團隊區塊 (#s02)")
            return []

        # 找到所有 member div
        article = s02_anchor.find_next('article')
        if not article:
            logger.warning("未找到 article 區塊")
            return []

        members = article.find_all('div', class_='member')
        logger.info(f"找到 {len(members)} 位原資中心人員")

        for member in members:
            staff_data = self._extract_isrc_member(member)
            if staff_data and staff_data['name']:
                staff_list.append(staff_data)

        return staff_list

    def _extract_isrc_member(self, member_div) -> Dict:
        """從 member div 提取原資中心人員資訊"""
        staff_info = {
            'name': '',
            'department': f'學務處{self.unit_name}',
            'phone': '',
            'email': '',
            'deputy': '',
            'responsibilities': ''
        }

        try:
            # 提取職稱
            title_div = member_div.find('div', class_='title')
            position = title_div.get_text(strip=True) if title_div else ''

            # 提取描述資訊
            description_div = member_div.find('div', class_='description')
            if not description_div:
                return None

            # 獲取文字內容，保留換行
            # 先複製一份避免修改原始 DOM
            description_copy = BeautifulSoup(str(description_div), 'html.parser').find('div')

            # 將所有 <br> 標籤替換成換行符號
            for br in description_copy.find_all('br'):
                br.replace_with('\n')

            # 取得文字內容
            text_content = description_copy.get_text()
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]

            # 解析各行資訊
            name = ''
            phone = ''
            email = ''
            responsibilities = []
            in_responsibilities = False

            for line in lines:
                if line.startswith('姓名：') or line.startswith('姓名:'):
                    name = line.replace('姓名：', '').replace('姓名:', '').strip()
                elif line.startswith('電話：') or line.startswith('電話:'):
                    phone = line.replace('電話：', '').replace('電話:', '').strip()
                elif line.startswith('電子信箱：') or line.startswith('電子信箱:'):
                    # 從原始 description_div 提取 email（可能在 <a> 標籤中）
                    email_tag = description_div.find('a', href=re.compile(r'mailto:'))
                    if email_tag:
                        email = email_tag.get_text(strip=True)
                    else:
                        email = line.replace('電子信箱：', '').replace('電子信箱:', '').strip()
                elif line.startswith('服務內容：') or line.startswith('服務內容:'):
                    in_responsibilities = True
                    resp = line.replace('服務內容：', '').replace('服務內容:', '').strip()
                    if resp:
                        responsibilities.append(f"- {resp}")
                elif in_responsibilities:
                    # 在服務內容區塊中的所有後續行
                    if line.startswith('-'):
                        responsibilities.append(line)
                    else:
                        responsibilities.append(f"- {line}")

            # 組合姓名和職稱
            if name and position:
                staff_info['name'] = f"{name} {position}"
            elif name:
                staff_info['name'] = name

            staff_info['phone'] = phone
            staff_info['email'] = email
            staff_info['responsibilities'] = '\n'.join(responsibilities)

        except Exception as e:
            logger.error(f"解析原資中心人員資訊時發生錯誤: {e}")

        return staff_info if staff_info['name'] else None

    def _format_responsibilities(self, job_text: str) -> str:
        """格式化業務職掌文字"""
        if not job_text:
            return ''

        # 如果是分號分隔的，轉換成列表格式
        if ';' in job_text:
            items = [item.strip() for item in job_text.split(';') if item.strip()]
            return '\n'.join([f"- {item}" for item in items])
        else:
            return f"- {job_text}"
