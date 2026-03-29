#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學圖書館各空間的開放時間"""

import logging
from datetime import datetime
from typing import List, Dict

import httpx
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

# 使用標準 logging,讓 run_*.py 的設定統一管理
logger = logging.getLogger(__name__)


class LibraryHoursScraper(BaseScraper):
    """圖書館開放時間爬蟲"""
    
    def __init__(self):
        super().__init__(
            source_url="https://www.lib.nchu.edu.tw/service.php?cID=35",
            output_filename="library_hours.json",
            data_dir="library"
        )
        self.base_url = "https://www.lib.nchu.edu.tw"
        
        # 更新 headers 為更完整的瀏覽器標頭
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': self.base_url,
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def scrape(self) -> str:
        """爬取圖書館開放時間頁面"""
        try:
            # 使用 httpx 客戶端
            with httpx.Client(
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                # 發送請求到目標頁面
                response = client.get(self.source_url)
                response.raise_for_status()
                
                logger.info(f"成功獲取網頁，狀態碼: {response.status_code}")
                return response.text
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 錯誤: {e.response.status_code} - {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"請求失敗: {e}")
            return None
        except Exception as e:
            logger.error(f"爬取過程發生錯誤: {e}", exc_info=True)
            return None
    
    def parse(self, html: str) -> List[Dict]:
        """解析圖書館開放時間資料"""
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')

        library_data = {
            'main_library': {},
            'department_library': []
        }

        tables = soup.find_all('table')
        logger.info(f"找到 {len(tables)} 個表格")

        # 解析前三個表格（學期中、寒假、暑假）
        for table_idx in range(min(3, len(tables))):
            period_data = self._parse_period_table(tables[table_idx], table_idx)
            if period_data:
                library_data['main_library'].update(period_data)

        # 解析系所圖書館（第四個表格）
        if len(tables) > 3:
            dept_libraries = self._parse_department_libraries(tables[3])
            library_data['department_library'] = dept_libraries

        return [library_data]
    
    def _parse_period_table(self, table, table_idx: int) -> Dict:
        """解析單個時段表格"""
        rows = table.find_all('tr')
        
        if len(rows) < 3:
            return {}
        
        first_row_cells = rows[0].find_all(['th', 'td'])
        period_info = first_row_cells[1].get_text(strip=True) if len(first_row_cells) > 1 else f"時段{table_idx + 1}"
        
        header_cells = rows[1].find_all(['th', 'td'])
        headers_raw = [cell.get_text(strip=True) for cell in header_cells]
        
        has_rowspan = len(first_row_cells) > 0 and first_row_cells[0].get('rowspan')
        headers = ['各區域服務時間'] + headers_raw if has_rowspan else headers_raw
        
        period_data = []
        rowspan_tracker = {}
        
        for row_idx, row in enumerate(rows[2:], start=2):
            cells = row.find_all(['td', 'th'])
            if not cells: continue

            full_cell_texts = []
            cell_idx = 0
            
            for col_idx in range(len(headers)):
                if col_idx in rowspan_tracker and rowspan_tracker[col_idx]['remaining'] > 0:
                    full_cell_texts.append(rowspan_tracker[col_idx]['value'])
                    rowspan_tracker[col_idx]['remaining'] -= 1
                    if rowspan_tracker[col_idx]['remaining'] == 0:
                        del rowspan_tracker[col_idx]
                else:
                    if cell_idx < len(cells):
                        cell = cells[cell_idx]
                        value = cell.get_text(strip=True)
                        full_cell_texts.append(value)
                        
                        rowspan = int(cell.get('rowspan', 1))
                        if rowspan > 1:
                            rowspan_tracker[col_idx] = {'value': value, 'remaining': rowspan - 1}
                        cell_idx += 1
                    else:
                        full_cell_texts.append('')
            
            if not full_cell_texts or not full_cell_texts[0]: continue
            
            space_info = {'space_name': full_cell_texts[0]}
            for i in range(1, len(headers)):
                header_name = headers[i]
                cell_value = full_cell_texts[i] if i < len(full_cell_texts) else ''
                field_name = self._map_header_to_field(header_name)
                space_info[field_name] = cell_value
            
            period_data.append(space_info)
        
        return { period_info: { 'headers': headers, 'data': period_data } }
    
    def _map_header_to_field(self, header_name: str) -> str:
        """將表格標題映射到欄位名稱"""
        if '週一' in header_name and '週五' in header_name: return 'weekday'
        if '週六' in header_name and '週日' in header_name: return 'weekend'
        if '週六' in header_name: return 'saturday'
        if '週日' in header_name: return 'sunday'
        if '國定假日' in header_name: return 'holiday'
        return header_name.lower().replace(' ', '_')
    
    def _parse_department_libraries(self, table) -> List[Dict]:
        """解析系所圖書館表格"""
        rows = table.find_all('tr')
        if len(rows) <= 2: return []

        first_row_cells = rows[0].find_all(['th', 'td'])
        first_row_texts = [{'text': cell.get_text(strip=True), 'colspan': int(cell.get('colspan', 1))} for cell in first_row_cells]
        
        second_row_cells = rows[1].find_all(['th', 'td'])
        second_row_texts = [cell.get_text(strip=True) for cell in second_row_cells]
        
        field_mapping = []
        second_row_idx = 0
        for header_info in first_row_texts:
            header_text, colspan = header_info['text'], header_info['colspan']
            if colspan == 1:
                field_mapping.append({'header': header_text, 'subheader': None})
            else:
                for _ in range(colspan):
                    if second_row_idx < len(second_row_texts):
                        subheader = second_row_texts[second_row_idx]
                        field_mapping.append({'header': header_text, 'subheader': subheader})
                        second_row_idx += 1
        
        dept_libraries = []
        current_college = ''
        rowspan_tracker = {}

        for row in rows[2:]:
            cells = row.find_all(['td', 'th'])
            if not cells: continue

            cells_info = [{'value': cell.get_text(strip=True), 'rowspan': int(cell.get('rowspan', 1))} for cell in cells]

            full_cell_texts = []
            cell_idx = 0
            new_rowspans = {}

            for col_idx in range(len(field_mapping)):
                if col_idx in rowspan_tracker and rowspan_tracker[col_idx]['remaining'] > 0:
                    full_cell_texts.append(rowspan_tracker[col_idx]['value'])
                    rowspan_tracker[col_idx]['remaining'] -= 1
                    if rowspan_tracker[col_idx]['remaining'] == 0: del rowspan_tracker[col_idx]
                else:
                    if cell_idx < len(cells_info):
                        cell_info = cells_info[cell_idx]
                        value, rowspan = cell_info['value'], cell_info['rowspan']
                        full_cell_texts.append(value)
                        if rowspan > 1: new_rowspans[col_idx] = {'value': value, 'remaining': rowspan - 1}
                        cell_idx += 1
                    else:
                        full_cell_texts.append('')

            rowspan_tracker.update(new_rowspans)

            # 更新當前學院：當第一欄（學院別）有新的 rowspan 或有實際內容時
            if 0 in new_rowspans or (len(full_cell_texts) > 0 and full_cell_texts[0] and 0 not in rowspan_tracker):
                current_college = full_cell_texts[0]
            
            dept_lib = {'college': current_college}
            for col_idx, field_info in enumerate(field_mapping):
                header, subheader = field_info['header'], field_info['subheader']
                value = full_cell_texts[col_idx] if col_idx < len(full_cell_texts) else ''
                
                if header == '學院別': continue
                elif header == '系所圖名稱': dept_lib['name'] = value
                elif header == '與總圖連線': dept_lib['connected_to_main'] = value
                elif header in ['連絡電話 (＃表分機)', '連絡電話(＃表分機)']: dept_lib['phone'] = value
                elif header == '圖書室所在位置': dept_lib['location'] = value
                elif header == '開放時間':
                    if subheader and '寒暑假' in subheader: dept_lib['hours_vacation'] = value
                    elif subheader and '學期中' in subheader: dept_lib['hours_regular'] = value
                elif header == '借書方式': dept_lib['borrowing_method'] = value
            
            if dept_lib.get('name') and dept_lib['name'] != current_college:
                dept_libraries.append(dept_lib)
        
        return dept_libraries
    
    def save_data(self, data: List[Dict]):
        """覆寫儲存方法，使用特殊的資料結構"""
        try:
            library_data = data[0] if data else {}

            result = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_count": len(library_data.get('main_library', {})),
                    "data_source": self.source_url
                },
                **library_data
            }

            import json
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logger.info(f"資料已儲存至: {self.output_path}")
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {str(e)}")