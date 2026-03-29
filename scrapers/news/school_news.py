import logging
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from ..base_scraper import BaseScraper

# 使用標準 logging,讓 run_*.py 的設定統一管理
logger = logging.getLogger(__name__)

class SchoolActivitiesNewsScraper(BaseScraper):
    """興大活動新聞爬蟲"""

    def __init__(self):
        super().__init__(
            source_url="https://www2.nchu.edu.tw/news/id/7",
            output_filename="school_news.json",
            data_dir="news",
            enable_hot_reload=False  # 不在此處觸發熱重載，統一由 unify_news.py 處理
        )

    def _extract_event_dates(self, title: str, content: str, publish_date: str) -> Tuple[Optional[str], Optional[str]]:
        """
        從標題和內容中提取活動日期和時間

        Args:
            title: 活動標題
            content: 活動內容
            publish_date: 發布日期

        Returns:
            Tuple[event_date, event_time]: (活動日期, 活動時間)
        """
        event_date = None
        event_time = None
        current_year = datetime.now().year

        # 1. 從標題中提取日期範圍 (例如: "2025/11/18～2025/11/20")
        title_date_pattern = r'(\d{4})/(\d{1,2})/(\d{1,2})'
        title_matches = re.findall(title_date_pattern, title)
        if title_matches:
            # 取第一個日期作為活動日期
            year, month, day = title_matches[0]
            event_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        # 2. 從內容中提取活動時間 (例如: "11/18(二)19:00-20:00" 或 "2025/11/19(三)")
        content_patterns = [
            r'活動時間[：:]\s*(\d{1,2})/(\d{1,2})\([一二三四五六日]\)[\s]*(\d{1,2}:\d{2})[\s]*[-~～][\s]*(\d{1,2}:\d{2})',  # 11/18(二)19:00-20:00
            r'時間[：:]\s*(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})',  # 2025年11月18日 or 2025/11/18
            r'(\d{4})/(\d{1,2})/(\d{1,2})\([一二三四五六日]\)',  # 2025/11/19(三)
            r'(\d{1,2})/(\d{1,2})\([一二三四五六日]\)[\s]*(\d{1,2}:\d{2})',  # 11/18(二) 19:00
        ]

        for pattern in content_patterns:
            match = re.search(pattern, content)
            if match:
                groups = match.groups()

                # 判斷是否包含年份
                if len(groups) >= 3 and len(groups[0]) == 4:  # 有年份
                    year, month, day = groups[0], groups[1], groups[2]
                    if not event_date:  # 只在還沒有日期時才設定
                        event_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    if len(groups) >= 4:  # 有時間
                        event_time = f"{groups[3]} ~ {groups[4] if len(groups) > 4 else groups[3]}"
                elif len(groups) >= 2:  # 沒有年份，使用當前年份
                    month, day = groups[0], groups[1]
                    if not event_date:
                        event_date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"
                    if len(groups) >= 3 and ':' in groups[2]:  # 有時間
                        event_time = groups[2]
                        if len(groups) >= 4:
                            event_time += f" ~ {groups[3]}"
                break

        # 3. 如果還是沒有日期，嘗試從 publish_date 推測
        if not event_date and publish_date and publish_date != "No Date":
            try:
                # 嘗試解析 publish_date
                pub_date = datetime.strptime(publish_date, "%Y-%m-%d")
                # 如果內容中有提到今天、明天等關鍵字
                if re.search(r'今[天日]|即日', content):
                    event_date = publish_date
                elif re.search(r'明[天日]', content):
                    next_day = pub_date.replace(day=pub_date.day + 1)
                    event_date = next_day.strftime("%Y-%m-%d")
            except:
                pass

        return event_date, event_time

    def _extract_location(self, content: str) -> Optional[str]:
        """
        從內容中提取活動地點

        Args:
            content: 活動內容

        Returns:
            活動地點
        """
        location_patterns = [
            r'活動地點[：:]\s*([^\n]+)',
            r'地點[：:]\s*([^\n]+)',
            r'SITE[：:]\s*([^\n]+)',
        ]

        for pattern in location_patterns:
            match = re.search(pattern, content)
            if match:
                location = match.group(1).strip()
                # 清理一些常見的干擾文字
                location = re.sub(r'\([^\)]*\)', '', location).strip()
                return location

        return None

    def scrape(self) -> List[str]:
        """
        爬取新聞列表所有分頁的 HTML 內容（近一個月內）
        """
        all_pages_html = []

        # 計算一個月前的日期
        one_month_ago = datetime.now() - timedelta(days=30)
        logger.info(f"只抓取 {one_month_ago.strftime('%Y-%m-%d')} 之後的新聞")

        # 1. 抓取第一頁以取得總頁數
        logger.info("正在抓取第 1 頁...")
        first_page_html = self.fetch_page(self.source_url)
        if not first_page_html:
            logger.error("無法取得第一頁")
            return []

        all_pages_html.append(first_page_html)

        # 檢查第一頁是否有近一個月的新聞
        if not self._has_recent_news(first_page_html, one_month_ago):
            logger.info("第 1 頁沒有近一個月的新聞，停止抓取")
            return all_pages_html

        # 2. 取得總頁數
        total_pages = self._get_total_pages(first_page_html)
        logger.info(f"共有 {total_pages} 個分頁")

        # 3. 抓取第 2 頁及之後的頁面（直到遇到超過一個月的新聞）
        should_continue = True
        for page_num in range(2, total_pages + 1):
            if not should_continue:
                logger.info(f"已找到所有近一個月的新聞，停止抓取後續分頁")
                break

            page_offset = (page_num - 1) * 20  # 每頁偏移量為 20
            page_url = f"https://www2.nchu.edu.tw/news/page/{page_offset}/id/7"
            logger.info(f"正在抓取第 {page_num} 頁: {page_url}")

            page_html = self.fetch_page(page_url)
            if page_html:
                all_pages_html.append(page_html)

                # 檢查這一頁是否有近一個月的新聞
                if not self._has_recent_news(page_html, one_month_ago):
                    logger.info(f"第 {page_num} 頁沒有近一個月的新聞，停止抓取")
                    should_continue = False
                    break
            else:
                logger.warning(f"無法取得第 {page_num} 頁")

            time.sleep(0.3)  # 避免請求過快

        logger.info(f"總共抓取了 {len(all_pages_html)} 個頁面")
        return all_pages_html

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
                # 排除 "next", "last" 等特殊按鈕
                if 'class' in li.attrs and ('next' in li['class'] or 'last' in li['class']):
                    continue

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

    def _has_recent_news(self, html: str, cutoff_date: datetime) -> bool:
        """檢查頁面是否有近期新聞"""
        soup = BeautifulSoup(html, "html.parser")

        news_container = soup.select_one("div.item-group")
        if not news_container:
            return False

        items = news_container.select("li")

        for item in items:
            date_element = item.select_one("span.date")
            if not date_element:
                continue

            publication_date_str = date_element.get_text(strip=True)
            if not publication_date_str or publication_date_str == "No Date":
                continue

            try:
                # 解析日期
                publication_date = datetime.strptime(publication_date_str, '%Y-%m-%d')

                # 檢查是否在截止日期之後
                if publication_date >= cutoff_date:
                    return True
            except Exception:
                # 如果日期解析失敗，繼續檢查下一個
                continue

        return False

    def parse(self, raw_data: List[str]) -> List[Dict]:
        """
        解析所有分頁的新聞列表，並抓取每篇新聞的詳細內容（僅抓取近一個月內）
        """
        if not raw_data:
            return []

        all_news_list: List[Dict] = []
        one_month_ago = datetime.now() - timedelta(days=30)

        for page_idx, html in enumerate(raw_data, 1):
            if not html:
                continue

            logger.info(f"正在解析第 {page_idx} 頁...")
            soup = BeautifulSoup(html, "html.parser")

            news_container = soup.select_one("div.item-group")
            if not news_container:
                logger.warning(f"第 {page_idx} 頁找不到主要新聞容器 (div.item-group)")
                continue

            items = news_container.select("li")
            logger.info(f"第 {page_idx} 頁找到 {len(items)} 個新聞項目")

            page_news_count = 0

            for item in items:
                date_element = item.select_one("span.date")
                publication_date = date_element.get_text(strip=True) if date_element else "No Date"

                # 過濾近一個月的新聞
                if publication_date and publication_date != "No Date":
                    try:
                        pub_date = datetime.strptime(publication_date, '%Y-%m-%d')
                        if pub_date < one_month_ago:
                            # 跳過超過一個月的新聞
                            continue
                    except Exception:
                        pass  # 如果日期解析失敗，保留該新聞

                title_element = item.select_one("h2.title")
                title = title_element.get_text(strip=True) if title_element else "No Title"

                link_element = item.select_one("a")
                link = link_element["href"] if link_element and link_element.has_attr('href') else "No Link"

                if link != "No Link" and not link.startswith('http'):
                    link = urljoin(self.source_url, link)

                content = ""
                images = []
                if link != "No Link":
                    try:
                        article_html = self.fetch_page(link)
                        if article_html:
                            article_soup = BeautifulSoup(article_html, "html.parser")
                            content_element = article_soup.select_one("div.editor")
                            if content_element:
                                content = content_element.get_text(strip=True)
                                for img in content_element.select("img"):
                                    if img.has_attr('src'):
                                        image_url = img['src']
                                        if not image_url.startswith('http'):
                                            image_url = urljoin(link, image_url)
                                        images.append(image_url)

                        time.sleep(0.3)  # 避免請求過快
                    except Exception as e:
                        logger.warning(f"抓取文章內容失敗 {link}: {e}")

                # 提取活動日期和時間
                event_date, event_time = self._extract_event_dates(title, content, publication_date)

                # 提取活動地點
                location = self._extract_location(content)

                all_news_list.append({
                    "publication_date": publication_date,
                    "title": title,
                    "link": link,
                    "content": content,
                    "images": images,
                    "event_date": event_date,
                    "event_time": event_time,
                    "location": location
                })

                page_news_count += 1

            logger.info(f"第 {page_idx} 頁有 {page_news_count} 則近一個月內的新聞")

        logger.info(f"總共解析出 {len(all_news_list)} 則近一個月內的新聞")
        return all_news_list
