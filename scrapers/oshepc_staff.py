#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學環境保護暨安全衛生中心人員職務資料"""

import re
import json
from typing import List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

# 各組別對應的爬取 URL（section_name 僅作快取檔命名用，實際組別名稱從 HTML 解析）
SECTIONS = [
    {
        'name': '中心主任',
        'url': (
            'https://safety.nchu.edu.tw/web/about.php'
            '?action=people&searchwords=%E4%B8%AD%E5%BF%83%E4%B8%BB%E4%BB%BB'
            '&bar=1&Site_ID=1&title_id=267'
        ),
    },
    {
        'name': '環境保護組',
        'url': (
            'https://safety.nchu.edu.tw/web/about.php'
            '?action=people&searchwords=%E7%92%B0%E5%A2%83%E4%BF%9D%E8%AD%B7%E7%B5%84'
            '&bar=1&Site_ID=1&title_id=44'
        ),
    },
    {
        'name': '安全衛生組',
        'url': (
            'https://safety.nchu.edu.tw/web/about.php'
            '?action=people&searchwords=%E5%AE%89%E5%85%A8%E8%A1%9B%E7%94%9F%E7%B5%84'
            '&bar=1&Site_ID=1&title_id=45'
        ),
    },
]

SOURCE_URL = 'https://safety.nchu.edu.tw/web/about.php?action=people&bar=1&Site_ID=1'


class OshepcStaffScraper(BaseScraper):
    """環境保護暨安全衛生中心人員職務資料爬蟲"""

    def __init__(self):
        super().__init__(
            source_url=SOURCE_URL,
            output_filename='oshepc_staff.json',
            data_dir='staff/oshepc',
        )

        # HTML 快取目錄
        staff_dir = self.data_dir.parent  # data/staff
        cache_dir = staff_dir / 'cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir

        # 中心位置（由 parse 時解析並儲存）
        self._location = ""

    def scrape(self) -> List[Dict[str, Any]]:
        """
        依序爬取各組別頁面，回傳 [{"name": 組別名, "url": url, "html": HTML}, ...]。
        若快取存在則直接讀取。
        """
        sections_data = []

        for section in SECTIONS:
            section_name = section['name']
            url = section['url']
            cache_file = self.cache_dir / f"oshepc_staff_{section_name}_cache.html"

            if cache_file.exists():
                logger.info(f"使用快取 [{section_name}]: {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    html = f.read()
            else:
                html = self.fetch_page(url)
                if not html:
                    logger.error(f"無法爬取 [{section_name}]: {url}")
                    html = ''
                else:
                    try:
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            f.write(html)
                        logger.info(f"HTML 快取至: {cache_file}")
                    except Exception as e:
                        logger.warning(f"無法儲存快取: {e}")

            sections_data.append({'name': section_name, 'url': url, 'html': html})

        return sections_data

    def parse(self, raw_data: List[Dict[str, Any]]) -> List[Dict]:
        """
        解析各組別頁面，回傳結構化資料列表。

        每位人員對應一個 <table class="meet02">，結構如下：
          <td class="meetnumber03" colspan="2">
            <div id="姓名">組別 ： 姓名 職稱</div>
          </td>
          <th>學歷及現職</th><td>...</td>
          <th>電話</th><td>...</td>
          <th>電子郵件</th><td><a href="mailto:...">...</a></td>
          <th>證照及資格</th><td>...</td>   ← 選填
          <th>職掌</th><td><ul><li>...</li></ul></td>
          <th>職務代理人</th><td>...</td>

        回傳: 結構化資料列表
        """
        if not raw_data:
            logger.warning('沒有資料可解析')
            return []

        # 從第一個非空的 HTML 提取中心位置
        for section_item in raw_data:
            if section_item.get('html'):
                soup_loc = BeautifulSoup(section_item['html'], 'html.parser')
                text = soup_loc.get_text()
                match = re.search(r'\d+號\s*([\u4e00-\u9fff\d]+)', text)
                if match:
                    self._location = match.group(1)
                    logger.debug(f"找到中心位置: {self._location}")
                break

        results = []

        for section_item in raw_data:
            section_label = section_item['name']  # 預設組別標籤（用於 log）
            html = section_item['html']

            if not html:
                logger.warning(f'[{section_label}] 無 HTML 內容，跳過')
                continue

            soup = BeautifulSoup(html, 'html.parser')
            tables = soup.find_all('table', class_='meet02')
            logger.info(f'[{section_label}] 找到 {len(tables)} 位人員')

            for table in tables:
                try:
                    # ── 標題行：「組別 ： 姓名 職稱」─────────────────
                    header_div = table.find('div')
                    if not header_div:
                        continue

                    header_text = header_div.get_text(strip=True)
                    # 格式：「A ： B C」，其中 A=組別, B=姓名, C=職稱
                    if '：' in header_text:
                        left, right = header_text.split('：', 1)
                        section_from_html = left.strip()
                        name_pos = right.strip()
                    else:
                        section_from_html = section_label
                        name_pos = header_text

                    # 姓名與職稱以第一個空格切分
                    if ' ' in name_pos:
                        name, position = name_pos.split(' ', 1)
                    else:
                        name, position = name_pos, ''

                    name = name.strip()
                    position = position.strip()

                    if not name:
                        continue

                    # ── 資訊行：th→label, td→value ───────────────────
                    fields: Dict[str, str] = {}
                    for row in table.find_all('tr'):
                        th = row.find('th')
                        td = row.find('td')
                        if not th or not td:
                            continue

                        label = th.get_text(strip=True)

                        # 職掌：取 <li> 列表文字
                        if '職掌' in label:
                            items = td.find_all('li')
                            if items:
                                duties = [li.get_text(strip=True) for li in items if li.get_text(strip=True)]
                                fields['職掌'] = '\n'.join(f'- {d}' for d in duties)
                            else:
                                fields['職掌'] = td.get_text(strip=True)
                        # 電子郵件：優先從 mailto 連結取得
                        elif '電子郵件' in label or 'mail' in label.lower():
                            a = td.find('a', href=re.compile(r'^mailto:'))
                            fields['電子郵件'] = (
                                a['href'].replace('mailto:', '').strip() if a
                                else td.get_text(strip=True)
                            )
                        # 學歷及現職：略過不收錄
                        elif '學歷' in label:
                            pass
                        else:
                            fields[label] = td.get_text(strip=True)

                    staff_data = {
                        'name': name,
                        'position': position,
                        'department': '環境保護暨安全衛生中心',
                        'section': section_from_html,
                        'phone': fields.get('電話', ''),
                        'email': fields.get('電子郵件', ''),
                        'deputy': fields.get('職務代理人', ''),
                        'responsibilities': fields.get('職掌', ''),
                        'certifications': fields.get('證照及資格', ''),
                    }

                    results.append(staff_data)
                    logger.debug(f'成功解析: {name} ({position}) - {section_from_html}')

                except Exception as e:
                    logger.error(f'[{section_label}] 解析人員資料失敗: {e}', exc_info=True)
                    continue

        logger.info(f'成功解析 {len(results)} 位人員資料')
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
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    scraper = OshepcStaffScraper()
    scraper.force_update()


if __name__ == '__main__':
    main()
