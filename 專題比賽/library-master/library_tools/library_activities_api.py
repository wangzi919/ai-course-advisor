#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides library extracurricular activities functionality for NCHU library."""

import json
import logging
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from mcp.server.fastmcp import FastMCP

# Set up a module-level logger
logger = logging.getLogger(__name__)


class LibraryActivitiesScheduler:
    """Scheduler for NCHU library extracurricular activities."""

    def __init__(self, data_file_path="data/activities/library_activities.json", auto_init=True):
        """
        Initialize the library activities scheduler.

        Args:
            data_file_path (str): Relative JSON data file path from parent_dir.
            auto_init (bool): If True, automatically initialize data when missing.
        """
        self.parent_dir = Path(__file__).parent.parent
        self.data_file_path = self.parent_dir / data_file_path
        self.activities_data: List[Dict] = []
        self.metadata: Dict = {}
        self.base_url = "https://cal.lib.nchu.edu.tw/"

        data_loaded = self.load_data()

        if auto_init and not data_loaded:
            logger.info("Detected missing data file, auto-initializing...")
            try:
                result = self.update_activities()
                if result.get("success"):
                    logger.info(f"✓ Auto initialization succeeded: {result.get('message')}")
                else:
                    logger.warning(f"✗ Auto initialization failed: {result.get('message')}")
            except Exception as e:
                logger.error(f"✗ Error during auto-initialization: {e}", exc_info=True)

    def load_data(self) -> bool:
        """Load extracurricular activities data from JSON file.

        Returns:
            bool: True if data loaded successfully, False otherwise.
        """
        try:
            if self.data_file_path.exists():
                with open(self.data_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.activities_data = data.get("activities", [])
                self.metadata = data.get("metadata", {})

                if self.activities_data:
                    last_updated = self.metadata.get("last_updated", "未知")
                    logger.info(f"✓ Loaded {len(self.activities_data)} activities (last updated: {last_updated})")
                    return True
                else:
                    logger.warning("⚠ Data file exists but no activities found")
                    return False
            else:
                logger.warning(f"⚠ Data file not found: {self.data_file_path}")
                self.activities_data = []
                self.metadata = {
                    "last_updated": None,
                    "total_activities": 0,
                    "data_source": self.base_url,
                }
                return False
        except Exception as e:
            logger.error(f"✗ Failed to load data: {e}", exc_info=True)
            self.activities_data = []
            self.metadata = {}
            return False

    def save_data(self) -> bool:
        """Save activities data to JSON file.

        Returns:
            bool: True if save succeeded, False otherwise.
        """
        try:
            self.data_file_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_activities": len(self.activities_data),
                    "data_source": self.base_url,
                },
                "activities": self.activities_data,
            }
            with open(self.data_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.metadata = data["metadata"]
            return True
        except Exception as e:
            logger.error(f"Failed to save data: {e}", exc_info=True)
            return False

    def fetch_activities_from_website(self) -> List[Dict]:
        """Scrape activities data from NCHU library website.

        Returns:
            List[Dict]: A list of activities data.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(self.base_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            activities: List[Dict] = []

            table = soup.find("table")
            if not table:
                logger.warning("No activity table found on the website.")
                return activities

            rows = table.find_all("tr")[1:]  # Skip header
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 6:
                    try:
                        activity_data = {
                            "date": cells[0].get_text(strip=True),
                            "time": cells[1].get_text(strip=True),
                            "target_audience": cells[2].get_text(strip=True),
                            "activity_name": cells[3].get_text(strip=True),
                            "instructor": cells[4].get_text(strip=True),
                            "location": cells[5].get_text(strip=True),
                            "registration_info": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                        }
                        activities.append(self._clean_activity_data(activity_data))
                    except Exception as e:
                        logger.warning(f"Error parsing an activity row: {e}")
                        continue
            return activities
        except Exception as e:
            logger.error(f"Failed to fetch activities: {e}", exc_info=True)
            return []

    @staticmethod
    def _clean_activity_data(activity_data: Dict) -> Dict:
        """Clean and normalize activity data.

        Args:
            activity_data (Dict): Raw activity data from website.

        Returns:
            Dict: Cleaned activity data.
        """
        for key in ["activity_name", "instructor", "location"]:
            if key in activity_data:
                activity_data[key] = re.sub(r"\s+", " ", activity_data[key]).strip()
        return activity_data

    def update_activities(self) -> Dict[str, Any]:
        """Update activities data from the library website.

        Returns:
            Dict[str, Any]: Update result with success status, message, count, and timestamp.
        """
        try:
            logger.info("Fetching library activities...")
            new_activities = self.fetch_activities_from_website()
            if not new_activities:
                return {"success": False, "message": "No new activities fetched", "activities_count": len(self.activities_data)}

            self.activities_data = new_activities
            if self.save_data():
                return {
                    "success": True,
                    "message": f"Updated {len(new_activities)} activities",
                    "activities_count": len(new_activities),
                    "last_updated": self.metadata.get("last_updated")
                }
            else:
                return {"success": False, "message": "Failed to save activities", "activities_count": len(self.activities_data)}
        except Exception as e:
            # This error is caught and returned by the script, so we log it as a warning.
            logger.warning(f"Error during activity update process: {e}")
            return {"success": False, "message": f"Error updating activities: {e}", "activities_count": len(self.activities_data)}

    def search_activities(
        self,
        keyword: str = "",
        date_range: Optional[str] = None,
        instructor: str = "",
        location: str = "",
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search library extracurricular activities by various criteria.

        Args:
            keyword (str): Keyword to search in activity names.
            date_range (str, optional): Date range in format "YYYY-MM-DD,YYYY-MM-DD".
            instructor (str): Instructor name to filter.
            location (str): Location to filter.
            limit (int): Maximum number of results to return.

        Returns:
            Dict[str, Any]: Dictionary containing search results, metadata, total count, and applied filters.
        """
        if not self.activities_data:
            return {
                "results": [],
                "total": 0,
                "message": "No activities available. Please update data first."
            }

        matching_activities = []

        for activity in self.activities_data:
            is_match = True
            if keyword and keyword.strip():
                if keyword.lower() not in activity.get("activity_name", "").lower():
                    is_match = False
            if instructor and instructor.strip():
                if instructor.lower() not in activity.get("instructor", "").lower():
                    is_match = False
            if location and location.strip():
                if location.lower() not in activity.get("location", "").lower():
                    is_match = False
            if date_range and "," in date_range:
                try:
                    start_date, end_date = date_range.split(",")
                    start_date = datetime.strptime(start_date.strip(), "%Y-%m-%d")
                    end_date = datetime.strptime(end_date.strip(), "%Y-%m-%d")
                    activity_date_str = activity.get("date", "")
                    activity_date = self._parse_activity_date(activity_date_str)
                    if activity_date and not (start_date <= activity_date <= end_date):
                        is_match = False
                except Exception:
                    pass

            if is_match:
                matching_activities.append(activity)

        limited_results = matching_activities[:limit]

        return {
            "metadata": self.metadata,
            "results": limited_results,
            "total": len(matching_activities),
            "showing": len(limited_results),
            "search_params": {
                "keyword": keyword,
                "date_range": date_range,
                "instructor": instructor,
                "location": location
            }
        }

    def _parse_activity_date(self, date_str: str) -> Optional[datetime]:
        """Parse activity date string into datetime object.

        Args:
            date_str (str): Activity date string.

        Returns:
            Optional[datetime]: Parsed datetime object, or None if parsing fails.
        """
        try:
            date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%m/%d", "%m-%d"]
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str.strip(), fmt)
                    if fmt in ["%m/%d", "%m-%d"]:
                        parsed_date = parsed_date.replace(year=datetime.now().year)
                    return parsed_date
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def get_upcoming_activities(self, days: int = 30, limit: int = 20) -> Dict[str, Any]:
        """Get upcoming activities within the next specified days.

        Args:
            days (int): Number of days to look ahead.
            limit (int): Maximum number of results to return.

        Returns:
            Dict[str, Any]: Upcoming activities, metadata, total and showing count.
        """
        if not self.activities_data:
            return {"results": [], "total": 0, "message": "No activities available. Please update data first."}

        today = datetime.now()
        future_date = today + timedelta(days=days)
        upcoming_activities = [
            act for act in self.activities_data
            if (act_date := self._parse_activity_date(act.get("date", ""))) and today <= act_date <= future_date
        ]
        upcoming_activities.sort(key=lambda x: self._parse_activity_date(x.get("date", "")) or datetime.min)
        limited_results = upcoming_activities[:limit]

        return {
            "metadata": self.metadata,
            "results": limited_results,
            "total": len(upcoming_activities),
            "showing": len(limited_results),
            "date_range": f"{today.strftime('%Y-%m-%d')} 到 {future_date.strftime('%Y-%m-%d')}"
        }

    def get_activity_stats(self) -> Dict[str, Any]:
        """Get statistics of library extracurricular activities.

        Returns:
            Dict[str, Any]: Dictionary containing total activities, distribution of instructors, locations, and target audiences.
        """
        if not self.activities_data:
            return {"total_activities": 0, "message": "No activities available."}

        stats = {
            "metadata": self.metadata,
            "total_activities": len(self.activities_data),
            "instructors": {},
            "locations": {},
            "target_audiences": {},
        }

        for activity in self.activities_data:
            stats["instructors"][activity.get("instructor", "未知")] = \
                stats["instructors"].get(activity.get("instructor", "未知"), 0) + 1
            stats["locations"][activity.get("location", "未知")] = \
                stats["locations"].get(activity.get("location", "未知"), 0) + 1
            stats["target_audiences"][activity.get("target_audience", "未知")] = \
                stats["target_audiences"].get(activity.get("target_audience", "未知"), 0) + 1

        return stats


scheduler = LibraryActivitiesScheduler(auto_init=True)
mcp = FastMCP("nchu_library_activities")

@mcp.tool()
def library_activities_search(keyword: str = "", date_range: str = "", instructor: str = "",
                              location: str = "", limit: int = 20) -> str:
    try:
        results = scheduler.search_activities(keyword=keyword, date_range=date_range,
                                              instructor=instructor, location=location, limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)

@mcp.tool()
def library_activities_upcoming(days: int = 30, limit: int = 20) -> str:
    try:
        results = scheduler.get_upcoming_activities(days=days, limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)

@mcp.tool()
def library_activities_stats() -> str:
    try:
        stats = scheduler.get_activity_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    mcp.run(transport="stdio")