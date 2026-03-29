#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學產學研鏈結中心人員職務資料"""

import re
from typing import List, Dict
from bs4 import BeautifulSoup, Tag
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

SOURCE_URL = 'https://www.gcaic.nchu.edu.tw/allmember-introduction.php?did=1&id=320'

# h3 外側文字若含有這些關鍵字，代表是組別名稱，否則是職稱
SECTION_MARKERS = ['組', '室', '平台', '中心', '基地', '課']

# 職稱後綴，由長至短排列以避免部分匹配
POSITION_SUFFIXES = [
    '副組長', '組長',
    '副主任', '中心主任', '主任',
    '計畫專員', '專員',
    '副理', '經理',
    '專任助理',
]


def _clean_text(text: str) -> str:
    """去除多餘空白與換行"""
    return re.sub(r'\s+', ' ', text).strip()


def _extract_after_colon(text: str) -> str:
    """取出冒號（：或:）後的內容並清除空白"""
    for sep in ('：', ':'):
        if sep in text:
            return _clean_text(text.split(sep, 1)[1])
    return _clean_text(text)


def _parse_name_position(raw: str) -> tuple[str, str]:
    """
    從「姓名職稱」或「姓名 職稱」格式解析出姓名與職稱。
    例：「王丕中組長」→ ("王丕中", "組長")
        「蔡祁欽 組長」→ ("蔡祁欽", "組長")
        「張麗月」      → ("張麗月", "")
    """
    raw = raw.strip()
    # 有空格：最後一個 token 當職稱
    parts = raw.split()
    if len(parts) >= 2:
        return parts[0], ' '.join(parts[1:])
    # 無空格：嘗試剝除職稱後綴
    for suf in POSITION_SUFFIXES:
        if raw.endswith(suf):
            return raw[: -len(suf)], suf
    return raw, ''


def _parse_header(h3_outside: str, span_text: str) -> tuple[str, str, str]:
    """
    解析 h3 標題，回傳 (section, name, position)。

    h3 有三種格式：
      A. h3_outside="產學長",         span="張健忠"          → position=產學長, name=張健忠, section=""
      B. h3_outside="產學推動組",     span="程德勝 組長"      → section=產學推動組, name=程德勝, position=組長
      C. h3_outside="",               span="創業育成組 蔡祁欽 組長" → 從 span 解析 section+name+position
    """
    h3_outside = h3_outside.strip()
    span_text = span_text.strip()

    if not h3_outside:
        # Case C：span 內含 section + name [position]
        parts = span_text.split()
        if len(parts) >= 2:
            section = parts[0]
            name, position = _parse_name_position(' '.join(parts[1:]))
        else:
            section, name, position = '', span_text, ''
    else:
        # h3_outside 有內容：判斷是組別或職稱
        is_section = any(marker in h3_outside for marker in SECTION_MARKERS)
        if is_section:
            # Case B：h3_outside = section，span = name [position]
            section = h3_outside
            name, position = _parse_name_position(span_text)
        else:
            # Case A：h3_outside = position，span = name
            section = ''
            position = h3_outside
            name = span_text

    return section, name, position


def _extract_office(elem: Tag) -> str:
    """從包含「辦公室位置：」的元素取出位置文字（去除 Google 地圖連結文字）"""
    # 暫時移除 <a> 標籤再取文字
    for a in elem.find_all('a'):
        a.decompose()
    text = _clean_text(elem.get_text())
    return _extract_after_colon(text)


class AiccStaffScraper(BaseScraper):
    """產學研鏈結中心人員職務資料爬蟲"""

    def __init__(self):
        super().__init__(
            source_url=SOURCE_URL,
            output_filename='aicc_staff.json',
            data_dir='staff/aicc',
        )

        staff_dir = self.data_dir.parent  # data/staff
        cache_dir = staff_dir / 'cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / 'aicc_staff_cache.html'

    def scrape(self) -> str:
        """爬取網頁，回傳 HTML 字串"""
        if self.html_cache_path.exists():
            logger.info(f'使用快取的 HTML: {self.html_cache_path}')
            with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                return f.read()

        html = self.fetch_page(self.source_url)
        if not html:
            logger.error('無法爬取產學研鏈結中心網頁')
            return ''

        try:
            with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f'HTML 已快取至: {self.html_cache_path}')
        except Exception as e:
            logger.warning(f'無法儲存 HTML 快取: {e}')

        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """
        解析各人員區塊，回傳結構化資料列表。

        頁面結構（每人一個 div.row.member-list）：
          <h3 class="intro_title_01">
            [h3_outside 文字] <span class="subtitle">span 文字</span>
          </h3>
          <div class="col-md-9">
            <h4>最高學歷：...</h4>      ← 略過
            <h4>重要經歷：</h4>          ← 略過
            <h4>業務職掌：</h4>          ← 從此開始收集
              <ol><li>...</li></ol>      ← 有序職掌清單
              <p>...</p>                 ← 職掌文字 / 電話 / 傳真 / 辦公室 / 代理人
              <ul>                       ← 電話 / 辦公室 in li
              <ul class="contact_list_1"> ← email
          </div>

        回傳: 結構化資料列表
        """
        if not raw_data:
            logger.warning('沒有資料可解析')
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        members = soup.find_all('div', class_='member-list')
        logger.info(f'找到 {len(members)} 個人員區塊')

        results = []

        for idx, m in enumerate(members, 1):
            try:
                # ── 解析 h3：section / name / position ────────────────
                h3 = m.find('h3', class_='intro_title_01')
                if not h3:
                    logger.warning(f'第 {idx} 個區塊找不到 h3，略過')
                    continue

                span = h3.find('span', class_='subtitle')
                span_text = _clean_text(span.get_text()) if span else ''
                # h3 外側文字 = h3 全文字 - span 文字
                h3_full = _clean_text(h3.get_text())
                h3_outside = _clean_text(h3_full.replace(span_text, ''))

                section, name, position = _parse_header(h3_outside, span_text)

                if not name:
                    logger.warning(f'第 {idx} 個區塊解析不到姓名，略過')
                    continue

                # ── 解析聯絡資訊與職掌 ────────────────────────────────
                col = m.find('div', class_='col-md-9')
                if not col:
                    results.append(self._build_record(name, position, section))
                    continue

                phone = fax = office = deputy = email = ''
                responsibilities_parts: List[str] = []

                # 找到「業務職掌」h4，從它之後開始蒐集
                duties_h4 = None
                for h4 in col.find_all('h4'):
                    if '業務職掌' in h4.get_text():
                        duties_h4 = h4
                        break

                if duties_h4:
                    for sib in duties_h4.next_siblings:
                        if not isinstance(sib, Tag):
                            continue
                        tag = sib.name

                        # <ul class="contact_list_1"> → email，停止蒐集
                        if tag == 'ul' and 'contact_list_1' in (sib.get('class') or []):
                            a = sib.find('a', href=re.compile(r'^mailto:'))
                            if a:
                                addr = a['href'].replace('mailto:', '').strip()
                                if addr:
                                    email = addr
                            break  # email ul 是最後一個元素

                        # <ol><li> → 有序職掌清單
                        if tag == 'ol':
                            for li in sib.find_all('li'):
                                t = _clean_text(li.get_text())
                                if t:
                                    responsibilities_parts.append(t)
                            continue

                        # <ul> (非 contact_list_1) → 電話 / 辦公室 in li
                        if tag == 'ul':
                            for li in sib.find_all('li'):
                                t = _clean_text(li.get_text())
                                if not t:
                                    continue
                                if '電話' in t:
                                    if not phone:
                                        phone = _extract_after_colon(t)
                                elif '傳真' in t:
                                    if not fax:
                                        fax = _extract_after_colon(t)
                                elif '辦公室' in t:
                                    if not office:
                                        # 使用 li 元素移除 a 標籤再取文字
                                        import copy
                                        li_copy = copy.copy(li)
                                        office = _extract_office(li_copy)
                            continue

                        # <p> 或 <p class="MsoListParagraph"> → 分類各欄位
                        if tag == 'p':
                            t = _clean_text(sib.get_text())
                            if not t:
                                continue
                            if '電話' in t:
                                if not phone:
                                    phone = _extract_after_colon(t)
                            elif '傳真' in t:
                                if not fax:
                                    fax = _extract_after_colon(t)
                            elif '辦公室位置' in t or '辦公室' in t and '位置' in t:
                                if not office:
                                    import copy
                                    p_copy = copy.copy(sib)
                                    office = _extract_office(p_copy)
                            elif '職務代理人' in t:
                                deputy = _extract_after_colon(
                                    t.replace('職務代理人', '職務代理人:')
                                    if '：' not in t and ':' not in t
                                    else t
                                )
                            else:
                                responsibilities_parts.append(t)

                # email（如果 duties_h4 之後沒有，再往整個 col 找）
                if not email:
                    email_ul = col.find('ul', class_='contact_list_1')
                    if email_ul:
                        a = email_ul.find('a', href=re.compile(r'^mailto:'))
                        if a:
                            addr = a['href'].replace('mailto:', '').strip()
                            if addr:
                                email = addr

                responsibilities = '\n'.join(
                    f'- {r}' for r in responsibilities_parts if r
                )

                record = {
                    'name': name,
                    'position': position,
                    'department': '產學研鏈結中心',
                    'section': section,
                    'phone': phone,
                    'fax': fax,
                    'email': email,
                    'office': office,
                    'deputy': deputy,
                    'responsibilities': responsibilities,
                }
                results.append(record)
                logger.debug(f'成功解析: {name} ({position}) [{section}]')

            except Exception as e:
                logger.error(f'第 {idx} 個區塊解析失敗: {e}', exc_info=True)
                continue

        logger.info(f'成功解析 {len(results)} 位人員資料')
        return results

    def _build_record(self, name: str, position: str, section: str) -> Dict:
        """建立空白聯絡資訊的人員記錄"""
        return {
            'name': name,
            'position': position,
            'department': '產學研鏈結中心',
            'section': section,
            'phone': '',
            'fax': '',
            'email': '',
            'office': '',
            'deputy': '',
            'responsibilities': '',
        }


def main():
    """測試用主函式"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    scraper = AiccStaffScraper()
    scraper.force_update()


if __name__ == '__main__':
    main()
