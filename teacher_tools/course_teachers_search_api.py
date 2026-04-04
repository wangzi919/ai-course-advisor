#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中興大學課程教師資料查詢 MCP Tool API

提供從課程系統擷取的教師資料查詢功能，支援：
- 按姓名搜尋
- 按系所搜尋
- 按開課記錄搜尋
- 按學期搜尋
- 綜合搜尋

此資料來源提供教師詳細的開課記錄。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP 伺服器
mcp = FastMCP("nchu_course_teachers_search")

# 資料檔案路徑
DATA_FILE = Path(__file__).parent.parent / "data" / "teachers" / "teachers_from_courses.json"


class CourseTeacherSearcher:
    """課程教師搜尋器"""

    def __init__(self, data_file: Path = DATA_FILE):
        """初始化搜尋器

        Args:
            data_file: 資料檔案路徑
        """
        self.data_file = data_file
        self.teachers: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self._loaded = False

    def _ensure_loaded(self):
        """確保資料已載入"""
        if self._loaded:
            return

        if not self.data_file.exists():
            raise RuntimeError(f"資料檔案不存在: {self.data_file}")

        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.teachers = data.get("teachers", [])
        self.metadata = data.get("metadata", {})
        self._loaded = True

        # 建立 ID 索引
        self._id_index: Dict[str, Dict] = {}
        for teacher in self.teachers:
            tid = teacher.get("id", "")
            if tid:
                self._id_index[tid] = teacher

    def reload(self):
        """重新載入資料"""
        self._loaded = False
        self._ensure_loaded()

    def get_metadata(self) -> Dict[str, Any]:
        """取得資料元資訊

        Returns:
            Dict: 資料元資訊
        """
        self._ensure_loaded()
        return self.metadata

    def search_by_name(
        self,
        name: str,
        exact_match: bool = False,
        limit: int = 30
    ) -> Dict[str, Any]:
        """按姓名搜尋教師

        Args:
            name: 教師姓名
            exact_match: 是否精確匹配
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        results = []
        name_lower = name.lower()

        for teacher in self.teachers:
            teacher_name = teacher.get("name", "")
            teacher_name_en = teacher.get("name_en", "").lower()

            if exact_match:
                if teacher_name == name or teacher_name_en == name_lower:
                    results.append(self._format_teacher(teacher))
            else:
                if name in teacher_name or name_lower in teacher_name_en:
                    results.append(self._format_teacher(teacher))

            if len(results) >= limit:
                break

        return {
            "results": results,
            "total": len(results),
            "query": {
                "name": name,
                "exact_match": exact_match,
            },
            "metadata": self._get_query_metadata(),
        }

    def search_by_department(
        self,
        department: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """按系所搜尋教師

        Args:
            department: 系所名稱（支援部分匹配）
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        results = []

        for teacher in self.teachers:
            # 檢查主要系所
            dept = teacher.get("department", "")
            # 檢查所有開課系所
            departments = teacher.get("departments", [])

            if department in dept or any(department in d for d in departments):
                results.append(self._format_teacher(teacher))

            if len(results) >= limit:
                break

        return {
            "results": results,
            "total": len(results),
            "query": {
                "department": department,
            },
            "metadata": self._get_query_metadata(),
        }

    def search_by_course(
        self,
        course_name: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """按課程名稱搜尋教師

        Args:
            course_name: 課程名稱（支援部分匹配）
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        results = []
        course_lower = course_name.lower()

        for teacher in self.teachers:
            courses = teacher.get("courses", [])
            matched_courses = []

            for course in courses:
                name = course.get("course_name", "").lower()
                if course_lower in name:
                    matched_courses.append(course)

            if matched_courses:
                result = self._format_teacher(teacher)
                result["matched_courses"] = matched_courses[:10]  # 只顯示前 10 門
                result["matched_course_count"] = len(matched_courses)
                results.append(result)

            if len(results) >= limit:
                break

        return {
            "results": results,
            "total": len(results),
            "query": {
                "course_name": course_name,
            },
            "metadata": self._get_query_metadata(),
        }

    def search_by_semester(
        self,
        semester: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """按學期搜尋教師

        Args:
            semester: 學期代碼（如：1131 代表 113 學年度第 1 學期）
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        results = []

        for teacher in self.teachers:
            semesters = teacher.get("semesters", [])

            if semester in semesters:
                # 找出該學期的課程
                courses = teacher.get("courses", [])
                semester_courses = [
                    c for c in courses
                    if c.get("semester", "") == semester
                ]

                result = self._format_teacher(teacher)
                result["semester_courses"] = semester_courses[:10]
                result["semester_course_count"] = len(semester_courses)
                results.append(result)

            if len(results) >= limit:
                break

        return {
            "results": results,
            "total": len(results),
            "query": {
                "semester": semester,
            },
            "metadata": self._get_query_metadata(),
        }

    def search(
        self,
        keywords: str,
        department: Optional[str] = None,
        limit: int = 30
    ) -> Dict[str, Any]:
        """綜合搜尋教師

        在姓名、系所、課程名稱中搜尋

        Args:
            keywords: 搜尋關鍵字
            department: 系所篩選（可選）
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        keyword_list = keywords.lower().split()
        scored_results = []

        for teacher in self.teachers:
            # 系所篩選
            if department:
                dept = teacher.get("department", "")
                departments = teacher.get("departments", [])
                if department not in dept and not any(department in d for d in departments):
                    continue

            # 計算匹配分數
            score = 0
            matched_fields = []

            # 搜尋姓名
            name = teacher.get("name", "").lower()
            name_en = teacher.get("name_en", "").lower()
            for keyword in keyword_list:
                if keyword in name or keyword in name_en:
                    score += 3
                    matched_fields.append("name")
                    break

            # 搜尋系所
            dept_text = teacher.get("department", "").lower()
            for keyword in keyword_list:
                if keyword in dept_text:
                    score += 2
                    matched_fields.append("department")
                    break

            # 搜尋課程
            courses_text = " ".join([
                c.get("course_name", "") for c in teacher.get("courses", [])
            ]).lower()
            for keyword in keyword_list:
                if keyword in courses_text:
                    score += 1
                    matched_fields.append("courses")
                    break

            if score > 0:
                scored_results.append({
                    "teacher": teacher,
                    "score": score,
                    "matched_fields": list(set(matched_fields)),
                })

        # 按分數排序
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # 格式化結果
        results = []
        for item in scored_results[:limit]:
            result = self._format_teacher(item["teacher"])
            result["matched_fields"] = item["matched_fields"]
            result["relevance_score"] = item["score"]
            results.append(result)

        return {
            "results": results,
            "total": len(scored_results),
            "showing": len(results),
            "query": {
                "keywords": keywords,
                "department": department,
            },
            "metadata": self._get_query_metadata(),
        }

    def get_teacher_detail(self, teacher_id: str) -> Dict[str, Any]:
        """取得教師詳細資訊

        Args:
            teacher_id: 教師 ID

        Returns:
            Dict: 教師詳細資訊
        """
        self._ensure_loaded()

        teacher = self._id_index.get(teacher_id)

        if teacher:
            return {
                "found": True,
                "teacher": self._format_teacher_detail(teacher),
                "metadata": self._get_query_metadata(),
            }
        else:
            return {
                "found": False,
                "message": f"找不到教師: {teacher_id}",
                "metadata": self._get_query_metadata(),
            }

    def get_teacher_courses(
        self,
        teacher_id: str,
        semester: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """取得教師開課記錄

        Args:
            teacher_id: 教師 ID
            semester: 學期篩選（可選）
            limit: 結果數量限制

        Returns:
            Dict: 教師開課記錄
        """
        self._ensure_loaded()

        teacher = self._id_index.get(teacher_id)

        if not teacher:
            return {
                "found": False,
                "message": f"找不到教師: {teacher_id}",
                "metadata": self._get_query_metadata(),
            }

        courses = teacher.get("courses", [])

        if semester:
            courses = [c for c in courses if c.get("semester", "") == semester]

        return {
            "found": True,
            "teacher_name": teacher.get("name", ""),
            "courses": courses[:limit],
            "total_courses": len(courses),
            "showing": min(limit, len(courses)),
            "metadata": self._get_query_metadata(),
        }

    def list_departments(self) -> Dict[str, Any]:
        """列出所有系所

        Returns:
            Dict: 系所列表
        """
        self._ensure_loaded()

        dept_counts: Dict[str, int] = {}

        for teacher in self.teachers:
            # 主要系所
            dept = teacher.get("department", "")
            if dept:
                dept_counts[dept] = dept_counts.get(dept, 0) + 1

        dept_list = [
            {"name": dept, "teacher_count": count}
            for dept, count in dept_counts.items()
        ]
        dept_list.sort(key=lambda x: x["teacher_count"], reverse=True)

        return {
            "departments": dept_list,
            "total": len(dept_list),
            "metadata": self._get_query_metadata(),
        }

    def list_semesters(self) -> Dict[str, Any]:
        """列出所有學期

        Returns:
            Dict: 學期列表
        """
        self._ensure_loaded()

        semester_counts: Dict[str, int] = {}

        for teacher in self.teachers:
            for semester in teacher.get("semesters", []):
                semester_counts[semester] = semester_counts.get(semester, 0) + 1

        semester_list = [
            {"semester": sem, "teacher_count": count}
            for sem, count in semester_counts.items()
        ]
        semester_list.sort(key=lambda x: x["semester"], reverse=True)

        return {
            "semesters": semester_list,
            "total": len(semester_list),
            "metadata": self._get_query_metadata(),
        }

    def _format_teacher(self, teacher: Dict[str, Any]) -> Dict[str, Any]:
        """格式化教師資料（簡略版）

        Args:
            teacher: 教師原始資料

        Returns:
            Dict: 格式化後的教師資料
        """
        return {
            "id": teacher.get("id", ""),
            "name": teacher.get("name", ""),
            "name_en": teacher.get("name_en", ""),
            "title": teacher.get("title", ""),
            "department": teacher.get("department", ""),
            "departments": teacher.get("departments", [])[:10],  # 限制顯示
            "semesters": teacher.get("semesters", []),
            "semesters_count": teacher.get("semesters_count", 0),
            "course_count": teacher.get("course_count", 0),
        }

    def _format_teacher_detail(self, teacher: Dict[str, Any]) -> Dict[str, Any]:
        """格式化教師資料（完整版）

        Args:
            teacher: 教師原始資料

        Returns:
            Dict: 格式化後的教師資料
        """
        return {
            "id": teacher.get("id", ""),
            "name": teacher.get("name", ""),
            "name_en": teacher.get("name_en", ""),
            "title": teacher.get("title", ""),
            "department": teacher.get("department", ""),
            "departments": teacher.get("departments", []),
            "college": teacher.get("college", ""),
            "research_areas": teacher.get("research_areas", []),
            "email": teacher.get("email", ""),
            "phone": teacher.get("phone", ""),
            "semesters": teacher.get("semesters", []),
            "semesters_count": teacher.get("semesters_count", 0),
            "course_count": teacher.get("course_count", 0),
            "recent_courses": teacher.get("courses", [])[:20],  # 只顯示最近 20 門
        }

    def _get_query_metadata(self) -> Dict[str, Any]:
        """取得查詢元資訊

        Returns:
            Dict: 查詢元資訊
        """
        return {
            "source": self.metadata.get("source", ""),
            "data_updated": self.metadata.get("extracted_at", ""),
            "total_teachers": self.metadata.get("total_teachers", 0),
            "total_courses": self.metadata.get("total_courses", 0),
            "semesters_processed": self.metadata.get("semesters_processed", 0),
        }


# 初始化全域搜尋器
searcher = CourseTeacherSearcher()


@mcp.tool()
def nchu_course_teachers_search_by_name(
    name: str,
    exact_match: bool = False,
    limit: int = 30
) -> str:
    """Search NCHU teachers from course data by name.

    This data source provides detailed course teaching records.

    Args:
        name: Teacher name to search for (Chinese or English)
        exact_match: Whether to use exact match (default: False)
        limit: Maximum number of results to return (default: 30)

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_name(name, exact_match, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_search_by_department(
    department: str,
    limit: int = 50
) -> str:
    """Search NCHU teachers by department from course data.

    Args:
        department: Department name (supports partial match)
        limit: Maximum number of results to return (default: 50)

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_department(department, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_search_by_course(
    course_name: str,
    limit: int = 30
) -> str:
    """Search NCHU teachers by course name they teach.

    Args:
        course_name: Course name to search for (supports partial match)
        limit: Maximum number of results to return (default: 30)

    Returns:
        JSON string containing teachers and their matching courses
    """
    try:
        results = searcher.search_by_course(course_name, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_search_by_semester(
    semester: str,
    limit: int = 100
) -> str:
    """Search NCHU teachers who taught in a specific semester.

    Args:
        semester: Semester code (e.g., "1131" for 113學年度第1學期)
        limit: Maximum number of results to return (default: 100)

    Returns:
        JSON string containing teachers and their courses for that semester
    """
    try:
        results = searcher.search_by_semester(semester, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_search(
    keywords: str,
    department: str | None = None,
    limit: int = 30
) -> str:
    """General search for NCHU teachers in course data.

    This tool searches across teacher names, departments, and course names.
    Results are sorted by relevance.

    Args:
        keywords: Search keywords (space-separated)
        department: Optional department filter
        limit: Maximum number of results to return (default: 30)

    Returns:
        JSON string containing search results sorted by relevance
    """
    try:
        results = searcher.search(keywords, department, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_get_detail(teacher_id: str) -> str:
    """Get detailed information about a specific teacher.

    Args:
        teacher_id: Teacher ID (from search results)

    Returns:
        JSON string containing detailed teacher information
    """
    try:
        results = searcher.get_teacher_detail(teacher_id)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"取得教師資訊時發生錯誤: {str(e)}",
            "found": False
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_get_courses(
    teacher_id: str,
    semester: str | None = None,
    limit: int = 50
) -> str:
    """Get course teaching records for a specific teacher.

    Args:
        teacher_id: Teacher ID (from search results)
        semester: Optional semester filter (e.g., "1131")
        limit: Maximum number of courses to return (default: 50)

    Returns:
        JSON string containing teacher's course records
    """
    try:
        results = searcher.get_teacher_courses(teacher_id, semester, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"取得開課記錄時發生錯誤: {str(e)}",
            "found": False
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_list_departments() -> str:
    """List all departments with teacher counts.

    Returns:
        JSON string containing department list
    """
    try:
        results = searcher.list_departments()
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"取得系所列表時發生錯誤: {str(e)}",
            "departments": []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_list_semesters() -> str:
    """List all semesters with teacher counts.

    Returns:
        JSON string containing semester list
    """
    try:
        results = searcher.list_semesters()
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"取得學期列表時發生錯誤: {str(e)}",
            "semesters": []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_teachers_get_stats() -> str:
    """Get course teachers database statistics.

    Returns:
        JSON string containing database statistics
    """
    try:
        metadata = searcher.get_metadata()
        return json.dumps({
            "statistics": {
                "source": metadata.get("source", ""),
                "total_teachers": metadata.get("total_teachers", 0),
                "total_courses": metadata.get("total_courses", 0),
                "total_departments": metadata.get("total_departments", 0),
                "semesters_processed": metadata.get("semesters_processed", 0),
                "data_updated": metadata.get("extracted_at", ""),
            }
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"取得統計資訊時發生錯誤: {str(e)}"
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
