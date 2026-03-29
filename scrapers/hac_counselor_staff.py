#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學健康與諮商中心院系所專輔人員資料"""

import re
import json
from typing import List, Dict, Tuple
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class HACCounselorStaffScraper(BaseScraper):
    """健康與諮商中心院系所專輔人員資料爬蟲"""

    # 主要電話（健康與諮商中心）
    MAIN_PHONE = '04-22840241'

    # 主頁面 URL（包含輔導工作項目）
    MAIN_PAGE_URL = "https://www.osa.nchu.edu.tw/osa/hac/health_services_3.html"

    def __init__(self):
        super().__init__(
            source_url="https://www.osa.nchu.edu.tw/osa/hac/js/service.php?op=list_college",
            output_filename="hac_counselor_staff.json",
            data_dir="staff/hac"  # 輸出到 data/staff/hac/
        )

        # HTML 快取路徑（在 data/staff/cache 目錄下）
        staff_dir = self.data_dir.parent  # 從 data/staff/hac 到 data/staff
        cache_dir = staff_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.html_cache_path = cache_dir / "hac_counselor_staff_cache.html"
        self.main_page_cache_path = cache_dir / "hac_main_page_cache.html"

        # 中心位置（由 parse 時解析並儲存）
        self._location = ""

    def scrape(self) -> Tuple[str, str]:
        """
        爬取網頁內容
        回傳: (聯絡人資料 HTML, 主頁面 HTML)
        """
        # 爬取聯絡人資料
        if self.html_cache_path.exists():
            logger.info(f"使用快取的聯絡人資料: {self.html_cache_path}")
            with open(self.html_cache_path, 'r', encoding='utf-8') as f:
                contact_html = f.read()
        else:
            contact_html = self.fetch_page(self.source_url)
            if not contact_html:
                logger.error("無法爬取專輔人員聯絡資料")
                return "", ""

            try:
                with open(self.html_cache_path, 'w', encoding='utf-8') as f:
                    f.write(contact_html)
                logger.info(f"聯絡人資料已快取至: {self.html_cache_path}")
            except Exception as e:
                logger.warning(f"無法儲存聯絡人資料快取: {e}")

        # 爬取主頁面（包含輔導工作項目）
        if self.main_page_cache_path.exists():
            logger.info(f"使用快取的主頁面: {self.main_page_cache_path}")
            with open(self.main_page_cache_path, 'r', encoding='utf-8') as f:
                main_page_html = f.read()
        else:
            main_page_html = self.fetch_page(self.MAIN_PAGE_URL)
            if not main_page_html:
                logger.warning("無法爬取主頁面，將跳過輔導工作項目")
                main_page_html = ""
            else:
                try:
                    with open(self.main_page_cache_path, 'w', encoding='utf-8') as f:
                        f.write(main_page_html)
                    logger.info(f"主頁面已快取至: {self.main_page_cache_path}")
                except Exception as e:
                    logger.warning(f"無法儲存主頁面快取: {e}")

        return contact_html, main_page_html

    def parse(self, raw_data: Tuple[str, str]) -> List[Dict]:
        """
        解析爬取的資料
        參數: raw_data - scrape() 回傳的 (聯絡人資料, 主頁面資料)
        回傳: 結構化資料列表
        """
        contact_html, main_page_html = raw_data

        if not contact_html:
            logger.warning("沒有聯絡人資料可解析")
            return []

        # 解析中心位置
        self._location = self._extract_location(main_page_html)

        # 解析輔導工作項目
        self.counseling_duties = self._parse_counseling_duties(main_page_html)

        # 解析聯絡人資料
        soup = BeautifulSoup(contact_html, 'html.parser')
        results = []

        # 找到主要表格
        table = soup.find('table', class_='table')
        if not table:
            logger.error("找不到資料表格")
            return []

        # 取得所有 tr，跳過表頭
        rows = table.find_all('tr')[1:]  # 跳過第一個 tr (表頭)
        logger.info(f"找到 {len(rows)} 行資料")

        current_college = ""  # 用於追蹤當前學院

        for row in rows:
            try:
                tds = row.find_all('td')

                # 如果有 3 個 td，表示是新學院的第一行
                if len(tds) == 3:
                    current_college = tds[0].get_text(strip=True)
                    department = tds[1].get_text(strip=True)
                    contact_info = tds[2].get_text(strip=True)
                # 如果只有 2 個 td，表示是同學院的其他科系
                elif len(tds) == 2:
                    department = tds[0].get_text(strip=True)
                    contact_info = tds[1].get_text(strip=True)
                else:
                    logger.warning(f"不符合預期的 td 數量: {len(tds)}")
                    continue

                # 解析聯絡資訊（格式：姓名 校內分機241轉28）
                # 使用正則表達式提取姓名和分機
                pattern = r'(.+?)\s+校內分機(\d+)轉(\d+)'
                match = re.match(pattern, contact_info)

                if match:
                    counselor_name = match.group(1).strip()
                    main_ext = match.group(2)  # 241
                    sub_ext = match.group(3)   # 28

                    # 組合完整電話
                    phone = f"{self.MAIN_PHONE}轉{sub_ext}"
                    full_contact = f"校內分機{main_ext}轉{sub_ext}"
                else:
                    # 如果不符合預期格式，保留原始資訊
                    counselor_name = contact_info
                    phone = ""
                    full_contact = contact_info

                # 建立資料字典
                staff_data = {
                    'college': current_college,
                    'department': department,
                    'counselor_name': counselor_name,
                    'phone': phone,
                    'extension': full_contact,
                    'office_location': '健康與諮商中心'
                }

                results.append(staff_data)
                logger.debug(f"成功解析: {current_college} - {department} - {counselor_name}")

            except Exception as e:
                logger.error(f"解析資料行時發生錯誤: {e}", exc_info=True)
                continue

        logger.info(f"成功解析 {len(results)} 筆專輔人員資料")
        return results

    def _extract_location(self, main_page_html: str) -> str:
        """從主頁面中提取健康與諮商中心位置"""
        if not main_page_html:
            return ""
        try:
            soup = BeautifulSoup(main_page_html, 'html.parser')
            for li in soup.find_all('li'):
                text = li.get_text(strip=True)
                if '中心位置' in text:
                    match = re.search(r'本校(\S+)', text)
                    if match:
                        location = match.group(1).strip()
                        logger.debug(f"找到中心位置: {location}")
                        return location
        except Exception as e:
            logger.warning(f"提取位置時發生錯誤: {e}")
        return ""

    def _parse_counseling_duties(self, main_page_html: str) -> List[Dict[str, str]]:
        """
        解析輔導工作項目
        參數: main_page_html - 主頁面 HTML
        回傳: 輔導工作項目列表
        """
        if not main_page_html:
            logger.warning("沒有主頁面資料，無法解析輔導工作項目")
            return []

        soup = BeautifulSoup(main_page_html, 'html.parser')
        duties = []

        # 先找到「院系專輔人員輔導工作項目」標題
        h3 = soup.find('h3', string=lambda text: '院系專輔人員輔導工作項目' in text if text else False)
        if not h3:
            logger.warning("找不到輔導工作項目標題")
            return []

        # 找標題後的 ul 標籤
        ul = h3.find_next('ul', class_='list-02')
        if not ul:
            logger.warning("找不到輔導工作項目列表")
            return []

        # 解析每個 li
        for li in ul.find_all('li'):
            try:
                # 獲取完整文字
                full_text = li.get_text(separator=' ', strip=True)

                # 提取標題（strong 標籤內容）
                strong_tag = li.find('strong')
                if strong_tag:
                    title = strong_tag.get_text(strip=True)
                    # 移除冒號
                    title = title.rstrip('：:')

                    # 提取描述（從完整文字中移除標題部分）
                    # 先獲取 strong 的完整文字（包含冒號）
                    strong_text = strong_tag.get_text(strip=True)
                    # 從完整文字中移除 strong 部分
                    description = full_text.replace(strong_text, '', 1).strip()

                    duties.append({
                        'title': title,
                        'description': description
                    })
                    logger.debug(f"解析輔導工作項目: {title}")
            except Exception as e:
                logger.error(f"解析輔導工作項目時發生錯誤: {e}", exc_info=True)
                continue

        logger.info(f"成功解析 {len(duties)} 個輔導工作項目")
        return duties

    def save_data(self, data: List[Dict]):
        """
        儲存資料為 JSON 檔案，自動加上 metadata（含輔導工作項目）

        Args:
            data: 要儲存的資料列表
        """
        try:
            result = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_count": len(data),
                    "data_source": self.source_url,
                    "location": getattr(self, '_location', ''),
                    "counseling_duties": getattr(self, 'counseling_duties', [])
                },
                "data": data
            }

            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logger.info(f"資料已儲存至: {self.output_path}")
            logger.info(f"Metadata - 最後更新: {result['metadata']['last_updated']}, "
                        f"總數: {result['metadata']['total_count']}, "
                        f"位置: {result['metadata']['location']}, "
                        f"輔導工作項目: {len(result['metadata']['counseling_duties'])}")

            # 觸發熱重載
            if self.enable_hot_reload:
                self._trigger_hot_reload()
        except Exception as e:
            logger.error(f"儲存資料時發生錯誤: {str(e)}")


def main():
    """測試用主函式"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    scraper = HACCounselorStaffScraper()
    scraper.force_update()


if __name__ == '__main__':
    main()
