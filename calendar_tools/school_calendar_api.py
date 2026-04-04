#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastMCP tool for searching and retrieving NCHU school calendar events.
Provides student-oriented query tools for school calendar.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SchoolCalendar:
    """
    Provides functionality to search and query the school calendar data.
    """
    def __init__(self, data_file_path="data/calendar/school_calendar.json"):
        self.parent_dir = Path(__file__).parent.parent
        self.data_file_path = self.parent_dir / data_file_path
        self.calendar_data: List[Dict] = []
        self.metadata: Dict = {}
        self.timezone = ZoneInfo("Asia/Taipei")
        self.load_data()

    def load_data(self) -> bool:
        """Loads the school calendar data from the JSON file."""
        try:
            if self.data_file_path.exists():
                with open(self.data_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.calendar_data = data.get("data", [])
                self.metadata = data.get("metadata", {})
                if self.calendar_data:
                    logger.info(f"✓ Loaded {len(self.calendar_data)} calendar events.")
                    return True
            logger.warning(f"⚠ Calendar data file not found or empty: {self.data_file_path}")
            return False
        except Exception as e:
            logger.error(f"✗ Failed to load calendar data: {e}", exc_info=True)
            return False

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into timezone-aware datetime object."""
        if not date_str:
            return None
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            parsed_date = parsed_date.replace(tzinfo=self.timezone)
            return parsed_date
        except ValueError:
            return None

    def _get_date_parts(self, start_date_str: str) -> dict:
        """Extract year, month, day from date string."""
        if not start_date_str:
            return {"year": None, "month": None, "day": None}
        try:
            date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
            return {
                "year": date_obj.year,
                "month": date_obj.month,
                "day": date_obj.day
            }
        except ValueError:
            return {"year": None, "month": None, "day": None}

    def _is_date_in_range(self, target_date: datetime, event: dict) -> bool:
        """Check if a target date falls within an event's date range."""
        start_date = self._parse_date(event.get("start_date"))
        if not start_date:
            return False

        end_date_str = event.get("end_date")
        if end_date_str:
            end_date = self._parse_date(end_date_str)
            if end_date:
                return start_date <= target_date <= end_date

        # 如果沒有結束日期，只比較開始日期
        return start_date.date() == target_date.date()

    def search_events(
        self,
        keyword: str = "",
        date_range: Optional[str] = None,
        category: str = "",
        month: Optional[int] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search calendar events by keyword, date range, category, or month.

        Args:
            keyword: Search keyword for event text
            date_range: Date range in format "YYYY-MM-DD,YYYY-MM-DD"
            category: Filter by category (開學, 放假, 考試, 選課, 註冊, 畢業, 活動, 行政, 其他)
            month: Filter by month (1-12)
            limit: Maximum number of results
        """
        if not self.calendar_data:
            return {"results": [], "total": 0, "message": "沒有行事曆資料可供查詢"}

        matching_events = []
        for event in self.calendar_data:
            # Keyword search
            if keyword:
                event_text = event.get("event", "") or ""
                if keyword.strip().lower() not in event_text.lower():
                    continue

            # Category filtering
            if category:
                event_category = event.get("category", "")
                if category.strip() != event_category:
                    continue

            # Month filtering
            if month:
                date_parts = self._get_date_parts(event.get("start_date", ""))
                if month != date_parts["month"]:
                    continue

            # Date range filtering
            if date_range and "," in date_range:
                try:
                    start_date_str, end_date_str = date_range.split(",")
                    query_start = datetime.strptime(start_date_str.strip(), "%Y-%m-%d")
                    query_end = datetime.strptime(end_date_str.strip(), "%Y-%m-%d")

                    event_start = self._parse_date(event.get("start_date", ""))
                    event_end_str = event.get("end_date")
                    event_end = self._parse_date(event_end_str) if event_end_str else event_start

                    # 檢查兩個日期區間是否有重疊
                    if not (event_start and event_end):
                        continue
                    if event_end < query_start or event_start > query_end:
                        continue
                except (ValueError, TypeError):
                    continue

            matching_events.append(event)

        # 智能過濾：優先顯示未來或進行中的事件
        today = datetime.now(self.timezone)
        future_events = []
        past_events = []

        for event in matching_events:
            event_start = self._parse_date(event.get("start_date", ""))
            event_end_str = event.get("end_date")
            event_end = self._parse_date(event_end_str) if event_end_str else event_start

            if not event_end:
                continue

            # 如果事件尚未結束（結束日期 >= 今天），視為未來或進行中的事件
            if event_end >= today:
                future_events.append(event)
            else:
                past_events.append(event)

        # 如果有未來事件，優先回傳未來事件；否則回傳過去事件（可能是用戶刻意查詢歷史）
        final_results = future_events if future_events else past_events

        # 按日期排序
        final_results.sort(key=lambda x: x.get("start_date", ""))

        return {
            "metadata": self.metadata,
            "results": final_results[:limit],
            "total": len(final_results),
            "showing": len(final_results[:limit]),
            "future_events_count": len(future_events),
            "past_events_count": len(past_events),
            "filtered_strategy": "prioritize_future" if future_events else "show_past_only"
        }

    def get_upcoming_events(self, days: int = 30, limit: int = 20) -> Dict[str, Any]:
        """
        Get upcoming events within the next specified days.

        Args:
            days: Number of days to look ahead
            limit: Maximum number of results
        """
        if not self.calendar_data:
            return {"results": [], "total": 0, "message": "沒有行事曆資料可供查詢"}

        today = datetime.now(self.timezone)
        logger.info(f"系統當前日期 (台灣時區 UTC+8): {today.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        future_date = today + timedelta(days=days)

        upcoming_events = []
        for event in self.calendar_data:
            event_start = self._parse_date(event.get("start_date", ""))
            if not event_start:
                continue

            # 檢查事件的開始日期或結束日期是否在查詢範圍內
            event_end_str = event.get("end_date")
            event_end = self._parse_date(event_end_str) if event_end_str else event_start

            # 如果事件在查詢範圍內（事件開始在範圍內，或事件結束在範圍內，或事件跨越整個範圍）
            if event_end >= today and event_start <= future_date:
                upcoming_events.append(event)

        upcoming_events.sort(key=lambda x: x.get("start_date", ""))

        return {
            "metadata": self.metadata,
            "system_date": today.strftime('%Y-%m-%d %H:%M:%S %Z (UTC+8)'),
            "timezone": "Asia/Taipei (台灣標準時間)",
            "results": upcoming_events[:limit],
            "total": len(upcoming_events),
            "showing": len(upcoming_events[:limit]),
            "date_range": f"{today.strftime('%Y-%m-%d')} 到 {future_date.strftime('%Y-%m-%d')}"
        }

    def get_events_by_category(self, category: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get events filtered by category.

        Args:
            category: Event category (開學, 放假, 考試, 選課, 註冊, 畢業, 活動, 行政, 其他)
            limit: Maximum number of results
        """
        if not self.calendar_data:
            return {"results": [], "total": 0, "message": "沒有行事曆資料可供查詢"}

        matching_events = [e for e in self.calendar_data if e.get("category") == category]

        # 智能過濾：優先顯示未來或進行中的事件
        today = datetime.now(self.timezone)
        future_events = []
        past_events = []

        for event in matching_events:
            event_start = self._parse_date(event.get("start_date", ""))
            event_end_str = event.get("end_date")
            event_end = self._parse_date(event_end_str) if event_end_str else event_start

            if not event_end:
                continue

            # 如果事件尚未結束（結束日期 >= 今天），視為未來或進行中的事件
            if event_end >= today:
                future_events.append(event)
            else:
                past_events.append(event)

        # 如果有未來事件，優先回傳未來事件；否則回傳過去事件
        final_results = future_events if future_events else past_events
        final_results.sort(key=lambda x: x.get("start_date", ""))

        return {
            "metadata": self.metadata,
            "results": final_results[:limit],
            "total": len(final_results),
            "showing": len(final_results[:limit]),
            "category": category,
            "future_events_count": len(future_events),
            "past_events_count": len(past_events),
            "filtered_strategy": "prioritize_future" if future_events else "show_past_only"
        }

    def get_events_by_month(self, year: int, month: int) -> Dict[str, Any]:
        """
        Get all events in a specific month.

        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
        """
        if not self.calendar_data:
            return {"results": [], "total": 0, "message": "沒有行事曆資料可供查詢"}

        matching_events = []
        for e in self.calendar_data:
            date_parts = self._get_date_parts(e.get("start_date", ""))
            if date_parts["year"] == year and date_parts["month"] == month:
                matching_events.append(e)

        matching_events.sort(key=lambda x: x.get("start_date", ""))

        return {
            "metadata": self.metadata,
            "results": matching_events,
            "total": len(matching_events),
            "showing": len(matching_events),
            "year": year,
            "month": month
        }

    def get_holidays(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get all holidays and vacation events.

        Args:
            limit: Maximum number of results
        """
        return self.get_events_by_category("放假", limit)

    def get_exam_dates(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get all exam-related events.

        Args:
            limit: Maximum number of results
        """
        return self.get_events_by_category("考試", limit)

    def get_registration_dates(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get all registration and course selection events.

        Args:
            limit: Maximum number of results
        """
        if not self.calendar_data:
            return {"results": [], "total": 0, "message": "沒有行事曆資料可供查詢"}

        # Include both "選課" and "註冊" categories
        matching_events = [
            e for e in self.calendar_data
            if e.get("category") in ["選課", "註冊"]
        ]

        # 智能過濾：優先顯示未來或進行中的事件
        today = datetime.now(self.timezone)
        future_events = []
        past_events = []

        for event in matching_events:
            event_start = self._parse_date(event.get("start_date", ""))
            event_end_str = event.get("end_date")
            event_end = self._parse_date(event_end_str) if event_end_str else event_start

            if not event_end:
                continue

            # 如果事件尚未結束（結束日期 >= 今天），視為未來或進行中的事件
            if event_end >= today:
                future_events.append(event)
            else:
                past_events.append(event)

        # 如果有未來事件，優先回傳未來事件；否則回傳過去事件
        final_results = future_events if future_events else past_events
        final_results.sort(key=lambda x: x.get("start_date", ""))

        return {
            "metadata": self.metadata,
            "results": final_results[:limit],
            "total": len(final_results),
            "showing": len(final_results[:limit]),
            "future_events_count": len(future_events),
            "past_events_count": len(past_events),
            "filtered_strategy": "prioritize_future" if future_events else "show_past_only"
        }

    def get_today_events(self) -> Dict[str, Any]:
        """Get events happening today."""
        if not self.calendar_data:
            return {"results": [], "total": 0, "message": "沒有行事曆資料可供查詢"}

        today = datetime.now(self.timezone)
        logger.info(f"系統當前日期 (台灣時區 UTC+8): {today.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        today_events = []
        for event in self.calendar_data:
            if self._is_date_in_range(today, event):
                today_events.append(event)

        return {
            "metadata": self.metadata,
            "system_date": today.strftime('%Y-%m-%d %H:%M:%S %Z (UTC+8)'),
            "timezone": "Asia/Taipei (台灣標準時間)",
            "results": today_events,
            "total": len(today_events),
            "showing": len(today_events)
        }


# Initialize the tool
school_calendar_service = SchoolCalendar()
mcp = FastMCP("nchu_school_calendar")


@mcp.tool()
def school_calendar_search(
    keyword: str = "",
    date_range: str = "",
    category: str = "",
    month: int = 0,
    limit: int = 50
) -> str:
    """
    搜尋中興大學行事曆事件

    Args:
        keyword: 搜尋關鍵字（在事件名稱中搜尋）
        date_range: 日期範圍，格式為 "YYYY-MM-DD,YYYY-MM-DD"
        category: 事件類別（開學、放假、考試、選課、註冊、畢業、活動、行政、其他）
        month: 月份篩選（1-12，0表示不篩選）
        limit: 最多回傳幾筆結果（預設50）

    Returns:
        JSON格式的事件清單，每個事件包含：semester(學年度-學期，如114-1)、start_date(開始日期)、end_date(結束日期)、event(事件內容)、category(類別)等資訊
    """
    try:
        month_filter = month if month > 0 else None
        results = school_calendar_service.search_events(
            keyword=keyword,
            date_range=date_range,
            category=category,
            month=month_filter,
            limit=limit
        )
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_search: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def school_calendar_get_upcoming(days: int = 30, limit: int = 20) -> str:
    """
    取得即將到來的行事曆事件（未來N天內）

    Args:
        days: 往後查詢幾天（預設30天）
        limit: 最多回傳幾筆結果（預設20）

    Returns:
        JSON格式的即將到來事件清單，每個事件包含：date(日期或日期區間)、event(事件內容)、category(類別)等資訊
    """
    try:
        results = school_calendar_service.get_upcoming_events(days=days, limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_get_upcoming: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def school_calendar_get_by_category(category: str, limit: int = 50) -> str:
    """
    依類別篩選行事曆事件

    Args:
        category: 事件類別（開學、放假、考試、選課、註冊、畢業、活動、行政、其他）
        limit: 最多回傳幾筆結果（預設50）

    Returns:
        JSON格式的事件清單，每個事件包含：semester(學年度-學期，如114-1)、start_date(開始日期)、end_date(結束日期)、event(事件內容)、category(類別)等資訊
    """
    try:
        results = school_calendar_service.get_events_by_category(category=category, limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_get_by_category: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def school_calendar_get_month(year: int, month: int) -> str:
    """
    取得特定月份的所有行事曆事件

    Args:
        year: 年份（例如：2025）
        month: 月份（1-12）

    Returns:
        JSON格式的該月份所有事件清單，每個事件包含：date(日期或日期區間)、event(事件內容)、category(類別)等資訊
    """
    try:
        results = school_calendar_service.get_events_by_month(year=year, month=month)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_get_month: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def school_calendar_get_holidays(limit: int = 50) -> str:
    """
    取得所有放假日

    Args:
        limit: 最多回傳幾筆結果（預設50）

    Returns:
        JSON格式的放假日清單，每個事件包含：date(日期或日期區間)、event(事件內容)、category(類別)等資訊
    """
    try:
        results = school_calendar_service.get_holidays(limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_get_holidays: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def school_calendar_get_exams(limit: int = 50) -> str:
    """
    取得所有考試相關日期

    Args:
        limit: 最多回傳幾筆結果（預設50）

    Returns:
        JSON格式的考試日期清單，每個事件包含：date(日期或日期區間)、event(事件內容)、category(類別)等資訊
    """
    try:
        results = school_calendar_service.get_exam_dates(limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_get_exams: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def school_calendar_get_registration(limit: int = 50) -> str:
    """
    取得所有選課和註冊相關日期

    Args:
        limit: 最多回傳幾筆結果（預設50）

    Returns:
        JSON格式的選課和註冊日期清單，每個事件包含：date(日期或日期區間)、event(事件內容)、category(類別)等資訊
    """
    try:
        results = school_calendar_service.get_registration_dates(limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_get_registration: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def school_calendar_get_today() -> str:
    """
    取得今天的行事曆事件

    Returns:
        JSON格式的今天事件清單，每個事件包含：date(日期或日期區間)、event(事件內容)、category(類別)等資訊
    """
    try:
        results = school_calendar_service.get_today_events()
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error in school_calendar_get_today: {e}", exc_info=True)
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
