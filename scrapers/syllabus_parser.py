#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
課程大綱解析模組

提供共用的課程大綱 HTML 解析功能，供各種課程爬蟲使用。
"""

import re
from bs4 import BeautifulSoup
from typing import Dict, Any


def parse_syllabus(html: str) -> Dict[str, Any]:
    """
    解析課程大綱頁面 HTML

    Args:
        html: 課程大綱頁面的 HTML 內容

    Returns:
        解析後的課程大綱資料字典
    """
    soup = BeautifulSoup(html, 'html.parser')

    syllabus = {
        '課程名稱_中': '',
        '課程名稱_英': '',
        '開課單位': '',
        '課程類別': '',
        '學分': '',
        '授課教師': '',
        '選課單位': '',
        '授課使用語言': '',
        '英文/EMI': '',
        '開課學期': '',
        '課程簡述': '',
        '先修課程名稱': '',
        '課程目標': '',
        '核心能力與配比': [],
        '教學方法': [],
        '評量方法': [],
        '每週授課內容': {},
        '自主學習內容': '',
        '學習評量方式': "",
        '教科書與參考書目': '',
        '課程教材': [],
        '課程輔導時間': '',
        '聯合國全球永續發展目標': '',
        '提供體驗課程': ''
    }

    # 找所有主要的 table (border=1)
    tables = soup.find_all('table', attrs={'border': '1'})

    for table in tables:
        rows = table.find_all('tr', recursive=False)

        for row in rows:
            cells = row.find_all('td', recursive=False)
            if not cells:
                continue

            # 解析標題欄位 (bgcolor=#CCCCCC 是標題)
            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                is_header = cell.get('bgcolor') == '#CCCCCC'

                if not is_header:
                    continue

                # 取得下一個非標題 cell 的內容
                def get_next_value(start_idx):
                    for j in range(start_idx + 1, len(cells)):
                        if cells[j].get('bgcolor') != '#CCCCCC':
                            return cells[j].get_text(strip=True)
                    return ''

                # 課程名稱 (特殊處理 - 跨兩行)
                if '課程名稱' in cell_text:
                    next_cell = get_next_value(i)
                    match = re.search(r'\(中\)\s*(.+?)(?:\(\d+\))?$', next_cell)
                    if match:
                        syllabus['課程名稱_中'] = match.group(1).strip()

                # 開課單位
                elif cell_text == '開課單位':
                    syllabus['開課單位'] = get_next_value(i)

                # 課程類別
                elif cell_text == '課程類別':
                    syllabus['課程類別'] = get_next_value(i)

                # 學分
                elif cell_text == '學分':
                    syllabus['學分'] = get_next_value(i)

                # 授課教師
                elif cell_text == '授課教師':
                    syllabus['授課教師'] = get_next_value(i)

                # 選課單位
                elif cell_text == '選課單位':
                    syllabus['選課單位'] = get_next_value(i)

                # 授課使用語言
                elif cell_text == '授課使用語言':
                    syllabus['授課使用語言'] = get_next_value(i)

                # 英文/EMI
                elif cell_text == '英文/EMI':
                    syllabus['英文/EMI'] = get_next_value(i)

                # 開課學期
                elif cell_text == '開課學期':
                    syllabus['開課學期'] = get_next_value(i)

                # 課程簡述
                elif cell_text == '課程簡述':
                    syllabus['課程簡述'] = get_next_value(i)

                # 先修課程名稱
                elif cell_text == '先修課程名稱':
                    syllabus['先修課程名稱'] = get_next_value(i)

            # 處理課程名稱英文 (第二行只有英文名稱)
            if len(cells) == 1:
                text = cells[0].get_text(strip=True)
                if text.startswith('(Eng.)'):
                    syllabus['課程名稱_英'] = text.replace('(Eng.)', '').strip()

            # 課程目標表格的資料行 (非標題行)
            if len(cells) == 5 and cells[0].get('bgcolor') != '#CCCCCC':
                col0 = cells[0].get_text(strip=True)  # 課程目標
                col1 = cells[1]  # 核心能力 (可能有嵌套 table)
                col2 = cells[2]  # 配比
                col3 = cells[3]  # 教學方法
                col4 = cells[4]  # 評量方法

                if col0 and col0 not in ['課程目標', '']:
                    syllabus['課程目標'] = col0

                # 核心能力與配比 (從嵌套 table 取得，一一對應)
                core_abilities = []
                ratios = []

                nested_table = col1.find('table')
                if nested_table:
                    for tr in nested_table.find_all('tr'):
                        td = tr.find('td')
                        if td:
                            text = td.get_text(strip=True)
                            if text:
                                core_abilities.append(text)

                nested_table = col2.find('table')
                if nested_table:
                    for tr in nested_table.find_all('tr'):
                        td = tr.find('td')
                        if td:
                            text = td.get_text(strip=True)
                            if text:
                                ratios.append(text)

                # 組合成對應的結構
                for idx, ability in enumerate(core_abilities):
                    ratio = ratios[idx] if idx < len(ratios) else ''
                    syllabus['核心能力與配比'].append({
                        '核心能力': ability,
                        '配比': ratio
                    })

                # 教學方法 (從嵌套 table 取得)
                nested_table = col3.find('table')
                if nested_table:
                    for td in nested_table.find_all('td'):
                        text = td.get_text(strip=True)
                        if text and text not in syllabus['教學方法']:
                            syllabus['教學方法'].append(text)

                # 評量方法 (從嵌套 table 取得)
                nested_table = col4.find('table')
                if nested_table:
                    for td in nested_table.find_all('td'):
                        text = td.get_text(strip=True)
                        if text and text not in syllabus['評量方法']:
                            syllabus['評量方法'].append(text)

        # 處理嵌套的週次表格
        nested_tables = table.find_all('table', recursive=True)
        for nested in nested_tables:
            nested_rows = nested.find_all('tr')
            for nr in nested_rows:
                nested_cells = nr.find_all('td')
                if len(nested_cells) >= 2:
                    week_cell = nested_cells[0].get_text(strip=True)
                    content_cell = nested_cells[1].get_text('\n', strip=True)

                    # 週次內容
                    week_match = re.match(r'^第(\d+)週$', week_cell)
                    if week_match:
                        week_num = week_match.group(1)
                        syllabus['每週授課內容'][f'第{week_num}週'] = content_cell

                    # 自主學習內容
                    elif '自主學習' in week_cell:
                        syllabus['自主學習內容'] = content_cell

    # 處理特殊區塊 (值在標題的下一個 tr)
    for table in tables:
        rows = table.find_all('tr', recursive=False)
        for idx, row in enumerate(rows):
            cells = row.find_all('td', recursive=False)
            if not cells:
                continue

            first_cell = cells[0]
            first_text = first_cell.get_text(strip=True)

            # 檢查是否是標題行
            if first_cell.get('bgcolor') == '#CCCCCC':
                # 取得下一行的值
                if idx + 1 < len(rows):
                    next_row = rows[idx + 1]
                    next_cells = next_row.find_all('td', recursive=False)
                    if next_cells:
                        value = next_cells[0].get_text('\n', strip=True)

                        if first_text == '學習評量方式':
                            syllabus['學習評量方式'] = value

                        elif '教科書' in first_text and '參考書目' in first_text:
                            syllabus['教科書與參考書目'] = value

                        elif '課程教材' in first_text:
                            syllabus['課程教材'] = [
                                line.strip() for line in value.split('\n') if line.strip()]

                        elif first_text == '課程輔導時間':
                            syllabus['課程輔導時間'] = value

                        elif '聯合國全球永續發展目標' in first_text:
                            # 從下一行的嵌套 table 取得
                            nested = next_cells[0].find('table')
                            if nested:
                                sdg_text = nested.get_text(strip=True)
                            else:
                                sdg_text = value
                            # 提取「提供體驗課程」
                            exp_match = re.search(r'提供體驗課程：([YN])', sdg_text)
                            if exp_match:
                                syllabus['提供體驗課程'] = exp_match.group(1)
                            # 移除「提供體驗課程：N/Y」並清理 HTML 實體
                            sdg_text = re.sub(r'提供體驗課程：[YN]', '', sdg_text)
                            sdg_text = sdg_text.replace(
                                '\xa0', ' ').replace('&nbsp', ' ')
                            sdg_text = re.sub(r'\s+', ' ', sdg_text).strip()
                            syllabus['聯合國全球永續發展目標'] = sdg_text

    return syllabus
