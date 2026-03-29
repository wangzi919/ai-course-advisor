#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides NCHU library e-learning courses functionality."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

from mcp.server.fastmcp import FastMCP


class LibraryElearningManager:
    """Manager for NCHU library e-learning courses."""

    def __init__(self):
        """
        Initialize the e-learning courses manager.
        """
        self.parent_dir = Path(__file__).parent.parent
        self.data_file_path = self.parent_dir / \
            "data/library/nchu_library_elearning_list.xlsx"
        self.courses_df: Optional[pd.DataFrame] = None
        self.load_data()

    def load_data(self) -> bool:
        """Load e-learning courses data from Excel file.

        Returns:
            bool: True if data loaded successfully, False otherwise.
        """
        try:
            if self.data_file_path.exists():
                self.courses_df = pd.read_excel(self.data_file_path)
                print(f"✓ Loaded {len(self.courses_df)} e-learning courses")
                return True
            else:
                print(f"✗ Data file not found: {self.data_file_path}")
                return False
        except Exception as e:
            print(f"✗ Failed to load data: {e}")
            return False

    def list_courses(
        self,
        limit: int = 20,
        search: Optional[str] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """List e-learning courses with optional filters.

        Args:
            limit (int): Maximum number of courses to return.
            search (str, optional): Search keyword in course titles.
            source (str, optional): Filter by source location name.

        Returns:
            Dict[str, Any]: Dictionary containing courses list and metadata.
        """
        if self.courses_df is None or self.courses_df.empty:
            return {
                "results": [],
                "total": 0,
                "message": "No courses available."
            }

        df = self.courses_df.copy()

        if search:
            df = df[df["標題"].str.contains(search, case=False, na=False)]

        if source:
            df = df[df["來源位置名稱"].str.contains(source, case=False, na=False)]

        total_results = len(df)
        df = df.head(limit)

        courses = []
        for _, row in df.iterrows():
            courses.append({
                "編號": int(row["編號"]) if pd.notna(row["編號"]) else None,
                "標題": row["標題"],
                "網址": row["網址"],
                "來源位置名稱": row["來源位置名稱"],
                "長度": row["長度"] if pd.notna(row["長度"]) else None,
                "觀看": int(row["觀看"]) if pd.notna(row["觀看"]) else 0,
                "建立時間": str(row["建立時間"]) if pd.notna(row["建立時間"]) else None
            })

        return {
            "results": courses,
            "total": total_results,
            "showing": len(courses),
            "search_params": {
                "search": search,
                "source": source
            }
        }

    def get_course_by_id(self, course_id: int) -> Dict[str, Any]:
        """Get specific course details by ID.

        Args:
            course_id (int): Course ID number.

        Returns:
            Dict[str, Any]: Course details or error message.
        """
        if self.courses_df is None or self.courses_df.empty:
            return {"error": "No courses available."}

        course = self.courses_df[self.courses_df["編號"] == course_id]

        if course.empty:
            return {"error": f"找不到編號 {course_id} 的課程"}

        row = course.iloc[0]
        return {
            "course": {
                "編號": int(row["編號"]),
                "標題": row["標題"],
                "網址": row["網址"],
                "來源位置": row["來源位置"],
                "來源位置名稱": row["來源位置名稱"],
                "建立時間": str(row["建立時間"]) if pd.notna(row["建立時間"]) else None,
                "容量": row["容量"] if pd.notna(row["容量"]) else None,
                "長度": row["長度"] if pd.notna(row["長度"]) else None,
                "觀看": int(row["觀看"]) if pd.notna(row["觀看"]) else 0,
                "上傳者": row["上傳者"],
                "上次修改": str(row["上次修改"]) if pd.notna(row["上次修改"]) else None
            }
        }

    def get_course_categories(self) -> Dict[str, Any]:
        """Get all course categories with course counts.

        Returns:
            Dict[str, Any]: Dictionary containing category statistics.
        """
        if self.courses_df is None or self.courses_df.empty:
            return {
                "total_categories": 0,
                "categories": [],
                "message": "No courses available."
            }

        categories = self.courses_df["來源位置名稱"].value_counts().to_dict()
        categories_list = [
            {"類別": category, "課程數量": count}
            for category, count in categories.items()
        ]

        return {
            "total_categories": len(categories_list),
            "categories": categories_list
        }

    def get_popular_courses(self, limit: int = 10) -> Dict[str, Any]:
        """Get most popular courses sorted by view count.

        Args:
            limit (int): Maximum number of courses to return.

        Returns:
            Dict[str, Any]: Dictionary containing popular courses.
        """
        if self.courses_df is None or self.courses_df.empty:
            return {
                "results": [],
                "total": 0,
                "message": "No courses available."
            }

        df = self.courses_df.sort_values("觀看", ascending=False).head(limit)

        courses = []
        for _, row in df.iterrows():
            courses.append({
                "編號": int(row["編號"]) if pd.notna(row["編號"]) else None,
                "標題": row["標題"],
                "網址": row["網址"],
                "來源位置名稱": row["來源位置名稱"],
                "觀看": int(row["觀看"]) if pd.notna(row["觀看"]) else 0,
                "長度": row["長度"] if pd.notna(row["長度"]) else None
            })

        return {
            "results": courses,
            "showing": len(courses)
        }

    def get_elearning_stats(self) -> Dict[str, Any]:
        """Get statistics of e-learning courses.

        Returns:
            Dict[str, Any]: Dictionary containing course statistics.
        """
        if self.courses_df is None or self.courses_df.empty:
            return {"total_courses": 0, "message": "No courses available."}

        stats = {
            "total_courses": len(self.courses_df),
            "total_categories": self.courses_df["來源位置名稱"].nunique(),
            "total_views": int(self.courses_df["觀看"].sum()),
            "top_category": self.courses_df["來源位置名稱"].value_counts().index[0] if len(self.courses_df) > 0 else None,
            "average_views": round(self.courses_df["觀看"].mean(), 2)
        }

        return stats


manager = LibraryElearningManager()
mcp = FastMCP("nchu_library_elearning")


@mcp.tool()
def library_elearning_list(limit: int = 20, search: str = "", source: str = "") -> str:
    """
    List e-learning courses with optional filters.

    Args:
        limit: Maximum number of courses to return (default: 20)
        search: Search keyword in course titles
        source: Filter by source location name
    """
    try:
        result = manager.list_courses(
            limit=limit,
            search=search if search else None,
            source=source if source else None
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "results": [], "total": 0}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_elearning_get_by_id(course_id: int) -> str:
    """
    Get specific course details by ID.

    Args:
        course_id: Course ID number
    """
    try:
        result = manager.get_course_by_id(course_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_elearning_categories() -> str:
    """Get all course categories with course counts."""
    try:
        result = manager.get_course_categories()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_elearning_popular(limit: int = 10) -> str:
    """
    Get most popular courses sorted by view count.

    Args:
        limit: Maximum number of courses to return (default: 10)
    """
    try:
        result = manager.get_popular_courses(limit=limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "results": []}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_elearning_stats() -> str:
    """Get statistics of e-learning courses."""
    try:
        result = manager.get_elearning_stats()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
