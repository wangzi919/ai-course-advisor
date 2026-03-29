#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取 PSFCOST 研習暨演講活動報名系統
資料來源: https://psfcost.nchu.edu.tw/registration/
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 將專案根目錄加入 sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scrapers.base_scraper import BaseScraper

# 使用標準 logging,讓 run_*.py 的設定統一管理
logger = logging.getLogger(__name__)


class PsfcostActivitiesScraper(BaseScraper):
    """PSFCOST 研習暨演講活動爬蟲"""

    def __init__(self):
        super().__init__(
            source_url="https://psfcost.nchu.edu.tw/registration/index/actlist.jsp",
            output_filename="psfcost_activities.json",
            data_dir="activities",
            enable_hot_reload=False  # 不在此處觸發熱重載，統一由 unify_activities.py 處理
        )

    def scrape(self) -> str:
        """爬取活動列表頁面"""
        logger.info(f"開始爬取 PSFCOST 活動列表: {self.source_url}")
        html = self.fetch_page(self.source_url)
        if not html:
            logger.error("無法獲取活動列表頁面")
            return ""
        logger.info(f"成功獲取活動列表，HTML 長度: {len(html)}")
        return html

    def parse(self, raw_data: str) -> List[Dict]:
        """解析活動資料"""
        if not raw_data:
            logger.warning("沒有資料可解析")
            return []

        soup = BeautifulSoup(raw_data, 'html.parser')
        activities = []

        # 找到所有活動的 tr 標籤
        rows = soup.find_all('tr', id='tr1')
        logger.info(f"找到 {len(rows)} 個活動")

        for row in rows:
            try:
                activity = self._parse_activity_row(row)
                if activity:
                    activities.append(activity)
            except Exception as e:
                logger.error(f"解析活動時發生錯誤: {e}", exc_info=True)
                continue

        logger.info(f"成功解析 {len(activities)} 個活動")
        return activities

    def _parse_activity_row(self, row) -> Dict:
        """解析單個活動行"""
        tds = row.find_all('td')
        if len(tds) < 5:
            return None

        # 解析活動名稱
        title = tds[0].get_text(strip=True)

        # 解析報名時間
        registration_time_text = tds[1].get_text(strip=True)
        registration_start, registration_end = self._parse_time_range(registration_time_text)

        # 解析活動時間
        event_time_text = tds[2].get_text(strip=True)
        event_start, event_end = self._parse_time_range(event_time_text)

        # 解析人數狀況
        capacity_text = tds[3].get_text(strip=True)
        capacity_info = self._parse_capacity(capacity_text)

        # 解析活動ID（從按鈕）
        button = tds[4].find('button')
        activity_id = button.get('id', '') if button else ''

        # 生成報名連結
        registration_link = f"https://psfcost.nchu.edu.tw/registration/info.jsp?ACTID={activity_id}" if activity_id else ""

        activity = {
            "id": f"psfcost_{activity_id}",
            "source": "psfcost",
            "source_name": "PSFCOST研習暨演講活動",
            "title": title,
            "registration_start": registration_start,
            "registration_end": registration_end,
            "event_start": event_start,
            "event_end": event_end,
            "registration_link": registration_link,
            "capacity": capacity_info,
            "details": {
                "activity_id": activity_id
            }
        }

        return activity

    def _parse_time_range(self, time_text: str) -> tuple:
        """
        解析時間範圍文字
        格式: "2026/01/16 09:00 至<br>2026/03/27 14:00"
        """
        # 移除 HTML 標籤和多餘空白
        time_text = re.sub(r'<br\s*/?>', ' ', time_text)
        time_text = re.sub(r'\s+', ' ', time_text).strip()

        # 分割起始和結束時間
        parts = re.split(r'至', time_text)
        if len(parts) != 2:
            return None, None

        start_time = self._parse_datetime(parts[0].strip())
        end_time = self._parse_datetime(parts[1].strip())

        return start_time, end_time

    def _parse_datetime(self, datetime_str: str) -> str:
        """
        解析日期時間字串
        輸入格式: "2026/01/16 09:00"
        輸出格式: "2026-01-16T09:00:00"
        """
        try:
            # 移除可能的多餘空白
            datetime_str = datetime_str.strip()

            # 解析日期時間
            dt = datetime.strptime(datetime_str, "%Y/%m/%d %H:%M")
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception as e:
            logger.warning(f"無法解析日期時間: {datetime_str}, 錯誤: {e}")
            return None

    def _parse_capacity(self, capacity_text: str) -> Dict:
        """
        解析人數狀況
        格式:
        人數上限：300
        已報名人數：112
        待審核人數：0
        """
        capacity_info = {
            "max_capacity": None,
            "registered": None,
            "pending": None
        }

        # 提取人數上限
        max_match = re.search(r'人數上限：.*?(\d+)', capacity_text)
        if max_match:
            capacity_info["max_capacity"] = int(max_match.group(1))

        # 提取已報名人數
        registered_match = re.search(r'已報名人數：.*?(\d+)', capacity_text)
        if registered_match:
            capacity_info["registered"] = int(registered_match.group(1))

        # 提取待審核人數
        pending_match = re.search(r'待審核人數：.*?(\d+)', capacity_text)
        if pending_match:
            capacity_info["pending"] = int(pending_match.group(1))

        return capacity_info


def main():
    """主函式"""
    scraper = PsfcostActivitiesScraper()
    scraper.run()


if __name__ == '__main__':
    main()
