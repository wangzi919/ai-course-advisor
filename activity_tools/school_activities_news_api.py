#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides NCHU news scraping functionality."""

import json
import logging
import re
import requests
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

# Set up a module-level logger
logger = logging.getLogger(__name__)


class SchoolActivitiesScheduler:
    """Scraper for NCHU news."""

    def __init__(self, data_file_path="data/activities/school_activities_news.json", auto_init=True):
        """Initialize the NCHU news scraper."""
        self.base_url = "https://www2.nchu.edu.tw/news/id/7"
        self.parent_dir = Path(__file__).parent.parent
        self.data_file_path = self.parent_dir / data_file_path
        self.news_data: List[Dict] = []
        self.metadata: Dict = {}

        data_loaded = self.load_data()

        if auto_init and not data_loaded:
            logger.info("Detected missing data file, auto-initializing...")
            try:
                result = self.update_news()
                if result.get("success"):
                    logger.info(f"✓ Auto initialization succeeded: {result.get('message')}")
                else:
                    logger.warning(f"✗ Auto initialization failed: {result.get('message')}")
            except Exception as e:
                logger.error(f"✗ Error during auto-initialization: {e}", exc_info=True)

    def load_data(self) -> bool:
        """Load news data from JSON file."""
        try:
            if self.data_file_path.exists():
                with open(self.data_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.news_data = data.get("news", [])
                self.metadata = data.get("metadata", {})

                if self.news_data:
                    last_updated = self.metadata.get("last_updated", "未知")
                    logger.info(f"✓ Loaded {len(self.news_data)} news articles (last updated: {last_updated})")
                    return True
                else:
                    logger.warning("⚠ Data file exists but no news found")
                    return False
            else:
                logger.warning(f"⚠ Data file not found: {self.data_file_path}")
                self.news_data = []
                self.metadata = {
                    "last_updated": None,
                    "total_articles": 0,
                    "data_source": self.base_url,
                }
                return False
        except Exception as e:
            logger.error(f"✗ Failed to load data: {e}", exc_info=True)
            self.news_data = []
            self.metadata = {}
            return False

    def save_data(self) -> bool:
        """Save news data to JSON file."""
        try:
            self.data_file_path.parent.mkdir(parents=True, exist_ok=True)
            data_to_save = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_articles": len(self.news_data),
                    "data_source": self.base_url,
                },
                "news": self.news_data,
            }
            with open(self.data_file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            self.metadata = data_to_save["metadata"]
            logger.info(f"Successfully saved data to {self.data_file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save data: {e}", exc_info=True)
            return False

    def fetch_news(self) -> List[Dict]:
        """Scrape news data from NCHU news website."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(self.base_url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, "html.parser")
            news_list: List[Dict] = []

            news_container = soup.select_one("div.item-group")
            if news_container:
                for item in news_container.select("li"):
                    date_element = item.select_one("span.date")
                    publication_date = date_element.get_text(strip=True) if date_element else "No Date"
                    title_element = item.select_one("h2.title")
                    title = title_element.get_text(strip=True) if title_element else "No Title"
                    link_element = item.select_one("a")
                    link = link_element["href"] if link_element and link_element.has_attr('href') else "No Link"

                    content = ""
                    images = []
                    if link != "No Link":
                        try:
                            article_response = requests.get(link, headers=headers, timeout=30)
                            article_response.raise_for_status()
                            article_response.encoding = 'utf-8'
                            article_soup = BeautifulSoup(article_response.text, "html.parser")
                            content_element = article_soup.select_one("div.editor")
                            if content_element:
                                content = content_element.get_text(strip=True)
                                for img in content_element.select("img"):
                                    if img.has_attr('src'):
                                        image_url = img['src']
                                        if not image_url.startswith('http'):
                                            image_url = "https://www2.nchu.edu.tw" + image_url
                                        images.append(image_url)
                        except Exception as e:
                            logger.warning(f"Failed to fetch article content for {link}: {e}")

                    news_list.append({
                        "publication_date": publication_date,
                        "title": title,
                        "link": link,
                        "content": content,
                        "images": images
                    })
            return news_list
        except Exception as e:
            logger.error(f"Failed to fetch news list: {e}", exc_info=True)
            return []

    def update_news(self) -> Dict[str, Any]:
        """Update news data from the school website."""
        try:
            logger.info("Fetching school news...")
            new_news = self.fetch_news()
            if not new_news:
                return {"success": False, "message": "No new news fetched", "news_count": len(self.news_data)}

            self.news_data = new_news
            if self.save_data():
                return {
                    "success": True,
                    "message": f"Updated {len(new_news)} news articles",
                    "news_count": len(new_news),
                    "last_updated": self.metadata.get("last_updated")
                }
            else:
                return {"success": False, "message": "Failed to save news", "news_count": len(self.news_data)}
        except Exception as e:
            logger.warning(f"Error during news update process: {e}")
            return {"success": False, "message": f"Error updating news: {e}", "news_count": len(self.news_data)}

    def _find_dates_in_text(self, text: str) -> List[datetime]:
        """Finds dates in various formats (YYYY/MM/DD or MM/DD) within a string."""
        date_pattern = r'(?:(\d{4})[./年-])?(\d{1,2})[./月-](\d{1,2})[日]?'
        matches = re.findall(date_pattern, text)
        
        found_dates = []
        current_year = datetime.now().year

        for match in matches:
            try:
                year_str, month_str, day_str = match
                year = int(year_str) if year_str else current_year
                month = int(month_str)
                day = int(day_str)
                
                if not year_str and datetime(year, month, day) < datetime.now() - timedelta(days=90):
                    year += 1

                found_dates.append(datetime(year, month, day))
            except (ValueError, TypeError):
                continue
        
        return list(set(found_dates))

    def search_news(
        self,
        keyword: str = "",
        date_range: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search school news by keyword and event date range found in the news content."""
        if not self.news_data:
            return {"results": [], "total": 0, "message": "No news available. Please update data first."}

        matching_news = []
        for news_item in self.news_data:
            keyword_match = True
            if keyword and keyword.strip():
                text_to_search_keyword = news_item.get("title", "") + " " + news_item.get("content", "")
                if keyword.lower() not in text_to_search_keyword.lower():
                    keyword_match = False

            date_range_match = True
            if date_range and "," in date_range:
                date_range_match = False
                try:
                    start_date_str, end_date_str = date_range.split(",")
                    start_date = datetime.strptime(start_date_str.strip(), "%Y-%m-%d")
                    end_date = datetime.strptime(end_date_str.strip(), "%Y-%m-%d")
                    
                    text_to_search_date = news_item.get("title", "") + " " + news_item.get("content", "")
                    event_dates = self._find_dates_in_text(text_to_search_date)
                    
                    for event_date in event_dates:
                        if start_date <= event_date <= end_date:
                            date_range_match = True
                            break
                except Exception:
                    date_range_match = False

            if keyword_match and date_range_match:
                matching_news.append(news_item)

        limited_results = matching_news[:limit]

        return {
            "metadata": self.metadata,
            "results": limited_results,
            "total": len(matching_news),
            "showing": len(limited_results),
            "search_params": {"keyword": keyword, "date_range": date_range}
        }

    def get_upcoming_news(self, days: int = 7, limit: int = 20) -> Dict[str, Any]:
        """Get school news containing upcoming events within a specified number of days."""
        if not self.news_data:
            return {"results": [], "total": 0, "message": "No news available. Please update data first."}

        today = datetime.now()
        future_date = today + timedelta(days=days)
        upcoming_events_with_dates = []

        for news_item in self.news_data:
            text_to_search = news_item.get("title", "") + " " + news_item.get("content", "")
            event_dates = self._find_dates_in_text(text_to_search)
            
            upcoming_dates_in_item = []
            for event_date in event_dates:
                if today <= event_date <= future_date:
                    upcoming_dates_in_item.append(event_date)
            
            if upcoming_dates_in_item:
                news_item_copy = news_item.copy()
                news_item_copy['matched_event_dates'] = sorted([d.strftime('%Y-%m-%d') for d in upcoming_dates_in_item])
                upcoming_events_with_dates.append((news_item_copy, min(upcoming_dates_in_item)))

        upcoming_events_with_dates.sort(key=lambda x: x[1])
        limited_results = [item for item, date in upcoming_events_with_dates[:limit]]
        
        return {
            "metadata": self.metadata,
            "results": limited_results,
            "total": len(upcoming_events_with_dates),
            "showing": len(limited_results),
            "date_range": f"{today.strftime('%Y-%m-%d')} to {future_date.strftime('%Y-%m-%d')}"
        }

    def get_news_stats(self) -> Dict[str, Any]:
        """Get statistics of school news."""
        if not self.news_data:
            return {"total_articles": 0, "message": "No news available."}

        return {
            "metadata": self.metadata,
            "total_articles": len(self.news_data),
        }


scraper = SchoolActivitiesScheduler()
mcp = FastMCP("nchu_school_activities_news")

@mcp.tool()
def school_activities_news_search(keyword: str = "", date_range: str = "", limit: int = 20) -> str:
    """Search for school news by keyword and event date range found in the news content."""
    try:
        results = scraper.search_news(keyword=keyword, date_range=date_range, limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)

@mcp.tool()
def school_activities_news_upcoming(days: int = 7, limit: int = 20) -> str:
    """Get school news containing upcoming events within a specified number of days."""
    try:
        results = scraper.get_upcoming_news(days=days, limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)

@mcp.tool()
def school_activities_news_stats() -> str:
    """Get statistics about the school news."""
    try:
        stats = scraper.get_news_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
