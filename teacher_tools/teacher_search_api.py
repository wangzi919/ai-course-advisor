#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中興大學教師查詢 MCP Tool API

提供教師資料查詢功能，支援：
- 按姓名搜尋
- 按系所搜尋
- 按學院搜尋
- 按研究專長搜尋
- 綜合搜尋
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP 伺服器
mcp = FastMCP("nchu_teacher_search")

# 資料檔案路徑
DATA_FILE = Path(__file__).parent.parent / "data" / "teachers" / "teachers_all.json"


class TeacherSearcher:
    """教師搜尋器"""

    def __init__(self, data_file: Path = DATA_FILE):
        """初始化搜尋器

        Args:
            data_file: 教師資料檔案路徑
        """
        self.data_file = data_file
        self.teachers: List[Dict[str, Any]] = []
        self.indexes: Dict[str, Any] = {}
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
        self.indexes = data.get("indexes", {})
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
        limit: int = 20
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
        title: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """按系所搜尋教師

        Args:
            department: 系所名稱（支援部分匹配）
            title: 職稱篩選（可選）
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        results = []

        for teacher in self.teachers:
            dept = teacher.get("department", "")

            # 系所匹配
            if department not in dept:
                continue

            # 職稱篩選
            if title:
                teacher_title = teacher.get("title", "")
                if title not in teacher_title:
                    continue

            results.append(self._format_teacher(teacher))

            if len(results) >= limit:
                break

        return {
            "results": results,
            "total": len(results),
            "query": {
                "department": department,
                "title": title,
            },
            "metadata": self._get_query_metadata(),
        }

    def search_by_college(
        self,
        college: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """按學院搜尋教師

        Args:
            college: 學院名稱（支援部分匹配）
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        results = []

        for teacher in self.teachers:
            teacher_college = teacher.get("college", "")

            if college in teacher_college:
                results.append(self._format_teacher(teacher))

            if len(results) >= limit:
                break

        return {
            "results": results,
            "total": len(results),
            "query": {
                "college": college,
            },
            "metadata": self._get_query_metadata(),
        }

    def search_by_research_area(
        self,
        keywords: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """按研究專長搜尋教師

        Args:
            keywords: 研究專長關鍵字（空格分隔多個）
            limit: 結果數量限制

        Returns:
            Dict: 搜尋結果
        """
        self._ensure_loaded()

        keyword_list = keywords.lower().split()
        results = []
        scored_results = []

        for teacher in self.teachers:
            research_areas = teacher.get("research_areas", [])
            if not research_areas:
                continue

            # 計算匹配分數
            score = 0
            matched_areas = []

            areas_text = " ".join(research_areas).lower()

            for keyword in keyword_list:
                if keyword in areas_text:
                    score += 1
                    # 找出匹配的專長
                    for area in research_areas:
                        if keyword in area.lower():
                            matched_areas.append(area)

            if score > 0:
                scored_results.append({
                    "teacher": teacher,
                    "score": score,
                    "matched_areas": list(set(matched_areas)),
                })

        # 按分數排序
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # 格式化結果
        for item in scored_results[:limit]:
            result = self._format_teacher(item["teacher"])
            result["matched_research_areas"] = item["matched_areas"]
            result["relevance_score"] = item["score"]
            results.append(result)

        return {
            "results": results,
            "total": len(scored_results),
            "showing": len(results),
            "query": {
                "keywords": keywords,
            },
            "metadata": self._get_query_metadata(),
        }

    def search(
        self,
        keywords: str,
        department: Optional[str] = None,
        college: Optional[str] = None,
        limit: int = 30
    ) -> Dict[str, Any]:
        """綜合搜尋教師

        在姓名、系所、研究專長中搜尋

        Args:
            keywords: 搜尋關鍵字
            department: 系所篩選（可選）
            college: 學院篩選（可選）
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
                if department not in teacher.get("department", ""):
                    continue

            # 學院篩選
            if college:
                if college not in teacher.get("college", ""):
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
            dept = teacher.get("department", "").lower()
            for keyword in keyword_list:
                if keyword in dept:
                    score += 2
                    matched_fields.append("department")
                    break

            # 搜尋研究專長
            research_text = " ".join(teacher.get("research_areas", [])).lower()
            for keyword in keyword_list:
                if keyword in research_text:
                    score += 1
                    matched_fields.append("research_areas")
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
                "college": college,
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

    def list_departments(self) -> Dict[str, Any]:
        """列出所有系所

        Returns:
            Dict: 系所列表
        """
        self._ensure_loaded()

        departments = self.indexes.get("departments", [])
        by_department = self.indexes.get("by_department", {})

        dept_list = []
        for dept in departments:
            count = len(by_department.get(dept, []))
            dept_list.append({
                "name": dept,
                "teacher_count": count,
            })

        # 按教師數量排序
        dept_list.sort(key=lambda x: x["teacher_count"], reverse=True)

        return {
            "departments": dept_list,
            "total": len(dept_list),
            "metadata": self._get_query_metadata(),
        }

    def list_colleges(self) -> Dict[str, Any]:
        """列出所有學院

        Returns:
            Dict: 學院列表
        """
        self._ensure_loaded()

        colleges = self.indexes.get("colleges", [])
        by_college = self.indexes.get("by_college", {})

        college_list = []
        for college in colleges:
            count = len(by_college.get(college, []))
            college_list.append({
                "name": college,
                "teacher_count": count,
            })

        # 按教師數量排序
        college_list.sort(key=lambda x: x["teacher_count"], reverse=True)

        return {
            "colleges": college_list,
            "total": len(college_list),
            "metadata": self._get_query_metadata(),
        }

    def list_research_areas(self, limit: int = 100) -> Dict[str, Any]:
        """列出所有研究專長

        Args:
            limit: 結果數量限制

        Returns:
            Dict: 研究專長列表
        """
        self._ensure_loaded()

        research_areas = self.indexes.get("research_areas", [])
        by_area = self.indexes.get("by_research_area", {})

        area_list = []
        for area in research_areas:
            count = len(by_area.get(area, []))
            area_list.append({
                "name": area,
                "teacher_count": count,
            })

        # 按教師數量排序
        area_list.sort(key=lambda x: x["teacher_count"], reverse=True)

        return {
            "research_areas": area_list[:limit],
            "total": len(area_list),
            "showing": min(limit, len(area_list)),
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
            "college": teacher.get("college", ""),
            "research_areas": teacher.get("research_areas", []),
            "email": teacher.get("email", ""),
            "phone": teacher.get("phone", ""),
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
            "college": teacher.get("college", ""),
            "research_areas": teacher.get("research_areas", []),
            "email": teacher.get("email", ""),
            "phone": teacher.get("phone", ""),
            "office": teacher.get("office", ""),
            "personal_url": teacher.get("personal_url", ""),
            "photo_url": teacher.get("photo_url", ""),
            "education": teacher.get("education", []),
            "experience": teacher.get("experience", []),
            "courses": teacher.get("courses", [])[:10],  # 只顯示最近 10 門課
            "course_count": teacher.get("course_count", 0),
        }

    def _get_query_metadata(self) -> Dict[str, Any]:
        """取得查詢元資訊

        Returns:
            Dict: 查詢元資訊
        """
        return {
            "data_updated": self.metadata.get("unified_at", ""),
            "total_teachers": self.metadata.get("total_teachers", 0),
        }


# 初始化全域搜尋器
searcher = TeacherSearcher()


@mcp.tool()
def nchu_teacher_search_by_name(
    name: str,
    exact_match: bool = False,
    limit: int = 20
) -> str:
    """Search for NCHU teachers by name.

    Args:
        name: Teacher name to search for (Chinese or English)
        exact_match: Whether to use exact match (default: False)
        limit: Maximum number of results to return (default: 20)

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
def nchu_teacher_search_by_department(
    department: str,
    title: str | None = None,
    limit: int = 50
) -> str:
    """Search for NCHU teachers by department.

    Args:
        department: Department name to search for (supports partial match)
        title: Optional title filter (e.g., "教授", "副教授", "助理教授")
        limit: Maximum number of results to return (default: 50)

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_department(department, title, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_teacher_search_by_college(
    college: str,
    limit: int = 100
) -> str:
    """Search for NCHU teachers by college.

    Available colleges:
    - 文學院
    - 農業暨自然資源學院
    - 理學院
    - 工學院
    - 生命科學院
    - 獸醫學院
    - 管理學院
    - 法政學院
    - 電機資訊學院
    - 醫學院
    - 循環經濟研究學院
    - 共同教育委員會

    Args:
        college: College name to search for (supports partial match)
        limit: Maximum number of results to return (default: 100)

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_college(college, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_teacher_search_by_research_area(
    keywords: str,
    limit: int = 30
) -> str:
    """Search for NCHU teachers by research area/expertise.

    This tool searches in teachers' research areas and specialties.
    Multiple keywords can be provided separated by spaces.

    Args:
        keywords: Research area keywords to search for (space-separated)
        limit: Maximum number of results to return (default: 30)

    Returns:
        JSON string containing search results sorted by relevance
    """
    try:
        results = searcher.search_by_research_area(keywords, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_teacher_search(
    keywords: str,
    department: str | None = None,
    college: str | None = None,
    limit: int = 30
) -> str:
    """General search for NCHU teachers.

    This tool searches across multiple fields: name, department, and research areas.
    Results are sorted by relevance.

    Args:
        keywords: Search keywords (space-separated)
        department: Optional department filter
        college: Optional college filter
        limit: Maximum number of results to return (default: 30)

    Returns:
        JSON string containing search results sorted by relevance
    """
    try:
        results = searcher.search(keywords, department, college, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"搜尋教師時發生錯誤: {str(e)}",
            "results": [],
            "total": 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_teacher_get_detail(teacher_id: str) -> str:
    """Get detailed information about a specific NCHU teacher.

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
def nchu_teacher_list_departments() -> str:
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
def nchu_teacher_list_colleges() -> str:
    """List all colleges with teacher counts.

    Returns:
        JSON string containing college list
    """
    try:
        results = searcher.list_colleges()
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"取得學院列表時發生錯誤: {str(e)}",
            "colleges": []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_teacher_list_research_areas(limit: int = 100) -> str:
    """List research areas with teacher counts.

    Args:
        limit: Maximum number of results to return (default: 100)

    Returns:
        JSON string containing research area list sorted by teacher count
    """
    try:
        results = searcher.list_research_areas(limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"取得研究專長列表時發生錯誤: {str(e)}",
            "research_areas": []
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
