#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爬取中興大學教務處最新消息"""

import logging
import re
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper

# 使用標準 logging,讓 run_*.py 的設定統一管理
logger = logging.getLogger(__name__)


class OAANewsScraper(BaseScraper):
    """教務處最新消息爬蟲"""

    def __init__(self):
        super().__init__(
            source_url="https://oaa.nchu.edu.tw/zh-tw/news",
            output_filename="oaa_news.json",
            data_dir="news",
            enable_hot_reload=False
        )
        self.base_url = "https://oaa.nchu.edu.tw"

    def scrape(self) -> List[Dict]:
        """爬取教務處最新消息（近一個月內）的列表和詳細內容"""
        all_news_list = []

        # 計算一個月前的日期
        one_month_ago = datetime.now() - timedelta(days=30)
        logger.info(f"只抓取 {one_month_ago.strftime('%Y-%m-%d')} 之後的新聞")

        # 1. 抓取第一頁以取得總頁數
        logger.info("正在抓取第 1 頁...")
        first_page_html = self.fetch_page(self.source_url)
        if not first_page_html:
            logger.error("無法取得第一頁")
            return []

        # 2. 解析第一頁的新聞列表
        first_page_news = self._parse_news_list(first_page_html)
        if first_page_news:
            # 過濾出近一個月的新聞
            recent_news = self._filter_recent_news(first_page_news, one_month_ago)
            all_news_list.extend(recent_news)
            logger.info(f"第 1 頁找到 {len(first_page_news)} 則消息，其中 {len(recent_news)} 則為近一個月內")

        # 3. 取得總頁數
        total_pages = self._get_total_pages(first_page_html)
        logger.info(f"共有 {total_pages} 個分頁")

        # 4. 抓取第 2 頁及之後的頁面（直到遇到超過一個月的新聞）
        should_continue = True
        for page_num in range(2, total_pages + 1):
            if not should_continue:
                logger.info(f"已找到所有近一個月的新聞，停止抓取後續分頁")
                break

            page_offset = (page_num - 1) * 10  # 每頁偏移量為 10
            page_url = f"{self.base_url}/zh-tw/news/news-list.0.{page_offset}"
            logger.info(f"正在抓取第 {page_num} 頁: {page_url}")

            page_html = self.fetch_page(page_url)
            if page_html:
                page_news = self._parse_news_list(page_html)
                if page_news:
                    # 過濾出近一個月的新聞
                    recent_news = self._filter_recent_news(page_news, one_month_ago)

                    if recent_news:
                        all_news_list.extend(recent_news)
                        logger.info(f"第 {page_num} 頁找到 {len(page_news)} 則消息，其中 {len(recent_news)} 則為近一個月內")
                    else:
                        # 如果這一頁完全沒有近一個月的新聞，停止抓取
                        logger.info(f"第 {page_num} 頁沒有近一個月的新聞，停止抓取")
                        should_continue = False
                        break
            else:
                logger.warning(f"無法取得第 {page_num} 頁")

            time.sleep(0.3)  # 避免請求過快

        logger.info(f"總共找到 {len(all_news_list)} 則近一個月內的消息")

        if not all_news_list:
            logger.warning("未找到任何近一個月的消息")
            return []

        # 5. 抓取每則消息的詳細內容
        for idx, news in enumerate(all_news_list, 1):
            logger.info(f"正在處理第 {idx}/{len(all_news_list)} 則消息: {news['title']}")

            detail_html = self.fetch_page(news['link'])
            if detail_html:
                news['html'] = detail_html

            time.sleep(0.3)  # 避免請求過快

        return all_news_list

    def _filter_recent_news(self, news_list: List[Dict], cutoff_date: datetime) -> List[Dict]:
        """過濾出指定日期之後的新聞"""
        recent_news = []

        for news in news_list:
            publish_date_str = news.get('publish_date', '')
            if not publish_date_str:
                # 如果沒有日期，保留該新聞
                recent_news.append(news)
                continue

            try:
                # 解析日期
                publish_date = datetime.strptime(publish_date_str, '%Y-%m-%d')

                # 檢查是否在截止日期之後
                if publish_date >= cutoff_date:
                    recent_news.append(news)
            except Exception as e:
                # 如果日期解析失敗，保留該新聞
                logger.warning(f"無法解析日期 '{publish_date_str}': {e}")
                recent_news.append(news)

        return recent_news

    def _get_total_pages(self, html: str) -> int:
        """從 HTML 中取得總頁數"""
        soup = BeautifulSoup(html, "html.parser")

        try:
            # 找到分頁區域
            page_limit = soup.find("div", class_="page-limit")
            if not page_limit:
                logger.info("沒有找到分頁元素，只有單一頁面")
                return 1

            # 找到所有分頁連結
            page_links = page_limit.find_all("li")
            if not page_links:
                return 1

            # 取得最大頁碼
            max_page = 1
            for li in page_links:
                link = li.find("a")
                if link:
                    page_text = link.get_text(strip=True)
                    if page_text.isdigit():
                        page_num = int(page_text)
                        max_page = max(max_page, page_num)

            return max_page
        except Exception as e:
            logger.warning(f"取得總頁數時發生錯誤: {e}，預設為 1 頁")
            return 1

    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """解析新聞詳細內容"""
        parsed_news = []

        for news in raw_data:
            if 'html' not in news:
                # 如果沒有詳細內容，保留基本資訊
                parsed_news.append({
                    "id": news.get("id"),
                    "unit": news.get("unit"),
                    "category": news.get("category"),
                    "publish_date": news.get("publish_date"),
                    "title": news.get("title"),
                    "link": news.get("link"),
                    "content": "",
                    "images": []
                })
                continue

            # 解析詳細內容
            detail = self._parse_news_detail(news['html'], news['link'])

            # 合併基本資訊和詳細內容
            parsed_news.append({
                "id": news.get("id"),
                "unit": news.get("unit"),
                "category": news.get("category"),
                "publish_date": news.get("publish_date"),
                "title": news.get("title"),
                "link": news.get("link"),
                "content": detail.get("content", ""),
                "images": detail.get("images", [])
            })

        logger.info(f"成功解析 {len(parsed_news)} 則消息")
        return parsed_news

    def _parse_news_list(self, html: str) -> List[Dict]:
        """解析新聞列表頁面"""
        soup = BeautifulSoup(html, "html.parser")
        news_items = []

        # 找到消息表格
        table = soup.find("table")
        if not table:
            logger.warning("找不到消息表格")
            return news_items

        rows = table.find("tbody")
        if not rows:
            logger.warning("找不到 tbody")
            return news_items

        # 解析每一行
        for row in rows.find_all("tr", class_="tb-row"):
            try:
                news_item = self._parse_news_row(row)
                if news_item:
                    news_items.append(news_item)
            except Exception as e:
                logger.warning(f"解析消息時發生錯誤: {e}")
                continue

        logger.info(f"找到 {len(news_items)} 則消息")
        return news_items

    def _parse_news_row(self, row) -> Optional[Dict]:
        """解析單則消息"""
        cells = row.find_all("td")
        if len(cells) < 4:
            return None

        # 解析單位
        unit_div = cells[0].find("div", class_="skin-label")
        unit = unit_div.get_text(strip=True) if unit_div else ""

        # 解析類別（對象）
        category_div = cells[1].find("div", class_="cate")
        category = category_div.get_text(strip=True) if category_div else ""

        # 解析日期
        date_div = cells[2].find("div", class_="date")
        publish_date = date_div.get_text(strip=True) if date_div else ""

        # 解析標題和連結
        title_cell = cells[3].find("a")
        if not title_cell:
            return None

        title = title_cell.get_text(strip=True)
        link = title_cell.get("href", "")

        # 確保連結是完整 URL
        if link and not link.startswith("http"):
            link = f"{self.base_url}/{link.lstrip('/')}"

        # 從連結中提取 ID
        news_id = self._extract_news_id(link)

        return {
            "id": news_id,
            "unit": unit,
            "category": category,
            "publish_date": self._normalize_date(publish_date),
            "title": title,
            "link": link,
        }

    def _parse_news_detail(self, html: str, link: str) -> Dict:
        """解析單則新聞的詳細頁面"""
        soup = BeautifulSoup(html, "html.parser")
        detail = {
            "content": "",
            "images": []
        }

        try:
            # 找到內容區域
            content_area = soup.find("div", class_="editor")
            if content_area:
                # 提取文字內容
                detail["content"] = content_area.get_text(strip=True)

                # 提取圖片
                images = content_area.find_all("img")
                for img in images:
                    img_src = img.get("src", "")
                    if img_src:
                        # 確保圖片連結是完整 URL
                        if not img_src.startswith("http"):
                            img_src = f"{self.base_url}/{img_src.lstrip('/')}"
                        detail["images"].append(img_src)

        except Exception as e:
            logger.error(f"解析新聞詳情時發生錯誤 {link}: {str(e)}")

        return detail

    @staticmethod
    def _extract_news_id(link: str) -> str:
        """從連結中提取新聞 ID"""
        # 例如: https://oaa.nchu.edu.tw/zh-tw/news-detail/content-p.2051 -> 2051
        match = re.search(r'content-p\.(\d+)', link)
        if match:
            return f"oaa_news_{match.group(1)}"
        return f"oaa_news_unknown"

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """正規化日期格式"""
        if not date_str:
            return ""
        try:
            # 嘗試解析 YYYY-MM-DD 格式
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            return date_str

    def format_data(self, parsed_data: List[Dict]) -> Dict:
        """格式化輸出資料"""
        return {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_count": len(parsed_data),
                "data_source": self.source_url
            },
            "data": parsed_data
        }


if __name__ == "__main__":
    # 測試用
    scraper = OAANewsScraper()
    scraper.force_update()
