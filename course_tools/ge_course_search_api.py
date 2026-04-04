#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides general education (GE) course search functionality for NCHU courses across all semesters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


from mcp.server.fastmcp import FastMCP


def semester_to_description(semester: str) -> str:
    """將學期代碼轉換為人類可讀格式

    Args:
        semester: 學期代碼，如 "1142"

    Returns:
        人類可讀格式，如 "113學年度第2學期"
    """
    if not semester or len(semester) != 4:
        return semester

    year = semester[:3]
    term = semester[3]
    term_str = "第1學期" if term == "1" else "第2學期"
    return f"{year}學年度{term_str}"


class GECourseSearcher:
    """通識課程搜尋器 - 支援多學期通識課程搜尋"""

    # 上課時間對照表
    TIME_SLOTS = {
        '1': '08:10-09:00',
        '2': '09:10-10:00',
        '3': '10:10-11:00',
        '4': '11:10-12:00',
        '5': '13:10-14:00',
        '6': '14:10-15:00',
        '7': '15:10-16:00',
        '8': '16:10-17:00',
        '9': '17:10-18:00',
        'A': '18:20-19:10',
        'B': '19:15-20:05',
        'C': '20:10-21:00',
        'D': '21:05-21:55',
    }

    WEEKDAY_MAP = {
        '1': '星期一',
        '2': '星期二',
        '3': '星期三',
        '4': '星期四',
        '5': '星期五',
        '6': '星期六',
        '7': '星期日',
    }

    # 課程大綱內可搜尋的文字欄位
    SYLLABUS_TEXT_FIELDS = [
        '課程名稱_中', '課程名稱_英', '課程簡述', '課程目標',
        '自主學習內容', '學習評量方式', '教科書與參考書目', '課程輔導時間'
    ]

    # 課程大綱內可搜尋的列表欄位
    SYLLABUS_LIST_FIELDS = ['教學方法', '評量方法', '核心能力', '課程教材']

    def __init__(self, data_dir: str = "data/courses/all_ge_courses_syllabi"):
        """
        初始化通識課程搜尋器

        Args:
            data_dir: 通識課程資料目錄路徑
        """
        self.parent_dir = Path(__file__).parent.parent
        self.data_dir = self.parent_dir / data_dir

        # 學期管理
        self.available_semesters: List[str] = []
        self.current_semester: str = ""
        self.loaded_semesters: Dict[str, List[Dict]] = {}
        self.semester_metadata: Dict[str, Dict] = {}  # 各學期的 metadata

        # 初始化
        self._scan_available_semesters()
        self._load_current_semester()

    def _scan_available_semesters(self):
        """掃描可用的學期"""
        if not self.data_dir.exists():
            raise RuntimeError(f"資料目錄不存在: {self.data_dir}")

        semesters = []
        for f in self.data_dir.glob("ge_courses_*.json"):
            # 從 ge_courses_1142.json 提取 1142
            semester = f.stem.replace("ge_courses_", "")
            if len(semester) == 4 and semester.isdigit():
                semesters.append(semester)

        # 按學期排序（最新的在前）
        self.available_semesters = sorted(semesters, reverse=True)

        if self.available_semesters:
            self.current_semester = self.available_semesters[0]
        else:
            raise RuntimeError(f"資料目錄中沒有找到通識課程資料: {self.data_dir}")

    def _load_current_semester(self):
        """載入當前學期資料"""
        if self.current_semester:
            self.load_semester(self.current_semester)

    def load_semester(self, semester: str) -> List[Dict]:
        """
        載入指定學期的通識課程資料

        Args:
            semester: 學期代碼

        Returns:
            該學期的通識課程列表
        """
        if semester in self.loaded_semesters:
            return self.loaded_semesters[semester]

        if semester not in self.available_semesters:
            raise ValueError(
                f"學期 {semester} 不存在，可用學期: {', '.join(self.available_semesters[:5])}...")

        json_path = self.data_dir / f"ge_courses_{semester}.json"

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # 支援新格式 {metadata, data} 與舊格式 (純 list)
            if isinstance(raw, dict) and 'data' in raw:
                courses = raw['data']
                if 'metadata' in raw:
                    self.semester_metadata[semester] = raw['metadata']
            else:
                courses = raw
            self.loaded_semesters[semester] = courses
            return courses
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {json_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 格式錯誤: {e}")

    def get_courses(self, semester: Optional[str] = None) -> List[Dict]:
        """
        取得指定學期的通識課程列表

        Args:
            semester: 學期代碼，None 表示使用當前學期

        Returns:
            通識課程列表
        """
        sem = semester or self.current_semester
        return self.load_semester(sem)

    def get_available_semesters(self) -> Dict[str, Any]:
        """
        取得所有可用學期列表

        Returns:
            包含學期列表及說明的字典
        """
        semester_info = []
        for sem in self.available_semesters:
            semester_info.append({
                'code': sem,
                'description': semester_to_description(sem),
                'loaded': sem in self.loaded_semesters
            })

        return {
            'total': len(self.available_semesters),
            'current_semester': self.current_semester,
            'current_semester_description': semester_to_description(self.current_semester),
            'semesters': semester_info
        }

    def _get_metadata(self, semester: Optional[str] = None) -> Dict[str, str]:
        """取得搜尋結果的 metadata"""
        sem = semester or self.current_semester
        meta = {
            'semester': sem,
            'description': semester_to_description(sem),
            'course_type': '通識課程'
        }
        # 附加資料檔案中的 metadata（如 last_updated, data_source 等）
        if sem in self.semester_metadata:
            file_meta = self.semester_metadata[sem]
            if 'last_updated' in file_meta:
                meta['last_updated'] = file_meta['last_updated']
            if 'data_source' in file_meta:
                meta['data_source'] = file_meta['data_source']
                description = file_meta.get('description', '可至上方網址進行更詳細的查詢')
                meta['data_source_note'] = f"🔗 {description}：{file_meta['data_source']}"
        return meta

    def _parse_class_time(self, time_code):
        """
        解析上課時間代碼

        Args:
            time_code: 上課時間代碼 (例如 "334" = 星期三第3、4節)

        Returns:
            人類可讀的上課時間字串
        """
        if not time_code or not time_code.strip():
            return "未指定"

        time_code = time_code.strip()
        if len(time_code) < 2:
            return time_code

        weekday = time_code[0]
        periods = time_code[1:]

        weekday_str = self.WEEKDAY_MAP.get(weekday, f"星期{weekday}")

        period_strs = []
        for p in periods:
            if p in self.TIME_SLOTS:
                period_strs.append(f"第{p}節({self.TIME_SLOTS[p]})")
            else:
                period_strs.append(f"第{p}節")

        return f"{weekday_str} {', '.join(period_strs)}"

    def _format_course_result(self, course, include_details=False, include_syllabus=False, semester: Optional[str] = None):
        """格式化課程結果

        Args:
            course: 課程資料
            include_details: 是否包含詳細選課資訊
            include_syllabus: 是否包含課程大綱資訊
            semester: 課程所屬學期
        """
        result = {
            "選課號碼": course.get("選課號碼", ""),
            "科目名稱": course.get("科目名稱", ""),
            "領域": course.get("領域", ""),
            "學群": course.get("學群", ""),
            "上課教師": course.get("上課教師", ""),
            "開課單位": course.get("開課單位", ""),
            "必選別": course.get("必選別", ""),
            "學分數": course.get("學分數", course.get("學分", "")),
            "上課時間": course.get("上課時間", ""),
            "上課時間說明": self._parse_class_time(course.get("上課時間", "")),
            "上課教室": course.get("上課教室", ""),
            "授課語言": course.get("授課語言", ""),
            "課程大綱URL": course.get("課程大綱URL", ""),
        }

        if semester:
            result["學期"] = semester
            result["學期說明"] = semester_to_description(semester)

        if include_details:
            result.update({
                "系所名稱": course.get("系所名稱", ""),
                "系所代碼": course.get("系所代碼", ""),
                "先修科目": course.get("先修科目", ""),
                "全半年": course.get("全半年", ""),
                "上課時數": course.get("上課時數", ""),
                "實習時數": course.get("實習時數", ""),
                "實習時間": course.get("實習時間", ""),
                "實習時間說明": self._parse_class_time(course.get("實習時間", "")) if course.get("實習時間") else "",
                "實習教室": course.get("實習教室", ""),
                "實習教師": course.get("實習教師", ""),
                "開課人數": course.get("開課人數", ""),
                "外系人數": course.get("外系人數", ""),
                "備註": course.get("備註", ""),
                "上課教室URL": course.get("上課教室URL", ""),
            })

        if include_syllabus:
            syllabus = course.get("課程大綱", {})
            result["課程大綱"] = {
                "課程名稱_中": syllabus.get("課程名稱_中", ""),
                "課程名稱_英": syllabus.get("課程名稱_英", ""),
                "選課單位": syllabus.get("選課單位", ""),
                "英文/EMI": syllabus.get("英文/EMI", ""),
                "開課學期": syllabus.get("開課學期", ""),
                "課程簡述": syllabus.get("課程簡述", ""),
                "先修課程名稱": syllabus.get("先修課程名稱", ""),
                "課程目標": syllabus.get("課程目標", ""),
                "核心能力": syllabus.get("核心能力", []),
                "配比": syllabus.get("配比", []),
                "教學方法": syllabus.get("教學方法", []),
                "評量方法": syllabus.get("評量方法", []),
                "每週授課內容": syllabus.get("每週授課內容", {}),
                "自主學習內容": syllabus.get("自主學習內容", ""),
                "學習評量方式": syllabus.get("學習評量方式", ""),
                "教科書與參考書目": syllabus.get("教科書與參考書目", ""),
                "課程教材": syllabus.get("課程教材", []),
                "課程輔導時間": syllabus.get("課程輔導時間", ""),
                "聯合國全球永續發展目標": syllabus.get("聯合國全球永續發展目標", ""),
                "提供體驗課程": syllabus.get("提供體驗課程", ""),
            }

        return result

    def _search_in_course(self, course, search_term, search_fields, case_sensitive, include_syllabus_search=False):
        """在單一課程中搜尋

        Args:
            course: 課程資料
            search_term: 搜尋關鍵字
            search_fields: 要搜尋的頂層欄位
            case_sensitive: 是否區分大小寫
            include_syllabus_search: 是否搜尋課程大綱內容
        """
        score = 0
        matched_fields = []

        # 搜尋頂層欄位
        for field in search_fields:
            value = course.get(field, "")
            if not value:
                continue

            compare_value = value if case_sensitive else value.lower()

            if search_term in compare_value:
                # 科目名稱和教師權重較高
                if field == "科目名稱":
                    score += 3
                elif field == "上課教師":
                    score += 2.5
                elif field == "開課單位":
                    score += 2
                else:
                    score += 1
                matched_fields.append(field)

        # 搜尋課程大綱內容
        if include_syllabus_search:
            syllabus = course.get("課程大綱", {})
            if syllabus:
                # 搜尋文字欄位
                for field in self.SYLLABUS_TEXT_FIELDS:
                    value = syllabus.get(field, "")
                    if not value:
                        continue
                    compare_value = value if case_sensitive else value.lower()
                    if search_term in compare_value:
                        if field in ['課程名稱_中', '課程名稱_英']:
                            score += 3
                        elif field in ['課程簡述', '課程目標']:
                            score += 2
                        else:
                            score += 1
                        matched_fields.append(f"課程大綱.{field}")

                # 搜尋列表欄位
                for field in self.SYLLABUS_LIST_FIELDS:
                    values = syllabus.get(field, [])
                    if not values:
                        continue
                    for item in values:
                        if isinstance(item, str):
                            compare_value = item if case_sensitive else item.lower()
                            if search_term in compare_value:
                                score += 1
                                if f"課程大綱.{field}" not in matched_fields:
                                    matched_fields.append(f"課程大綱.{field}")

                # 搜尋每週授課內容
                weekly_content = syllabus.get("每週授課內容", {})
                if weekly_content:
                    for content in weekly_content.values():
                        if content:
                            compare_value = content if case_sensitive else content.lower()
                            if search_term in compare_value:
                                score += 0.5
                                if "課程大綱.每週授課內容" not in matched_fields:
                                    matched_fields.append("課程大綱.每週授課內容")

        return {
            'is_match': score > 0,
            'score': score,
            'matched_fields': matched_fields
        }

    def search_courses(self,
                       keyword: str,
                       limit: int = 10,
                       search_fields: Optional[List[str]] = None,
                       case_sensitive: bool = False,
                       include_syllabus_search: bool = False,
                       include_syllabus_in_result: bool = False,
                       semester: Optional[str] = None):
        """
        搜尋通識課程

        Args:
            keyword: 搜尋關鍵字
            limit: 回傳結果數量限制
            search_fields: 要搜尋的欄位列表
            case_sensitive: 是否區分大小寫
            include_syllabus_search: 是否同時搜尋課程大綱內容
            include_syllabus_in_result: 是否在結果中包含課程大綱
            semester: 學期代碼，None 表示使用最新學期

        Returns:
            搜尋結果字典
        """
        if search_fields is None:
            search_fields = ['科目名稱', '上課教師', '開課單位', '系所名稱', '備註']

        if not keyword.strip():
            return {
                'results': [],
                'total': 0,
                'message': '請提供搜尋關鍵字'
            }

        sem = semester or self.current_semester
        courses = self.get_courses(sem)

        search_term = keyword if case_sensitive else keyword.lower()
        matching_courses = []

        for course in courses:
            match_info = self._search_in_course(
                course, search_term, search_fields, case_sensitive,
                include_syllabus_search=include_syllabus_search
            )

            if match_info['is_match']:
                matching_courses.append({
                    'course': self._format_course_result(
                        course,
                        include_syllabus=include_syllabus_in_result
                    ),
                    'relevance_score': match_info['score'],
                    'matched_fields': match_info['matched_fields']
                })

        # 按相關度排序
        matching_courses.sort(key=lambda x: x['relevance_score'], reverse=True)

        # 限制結果數量
        limited_results = matching_courses[:limit]

        return {
            'results': limited_results,
            'total': len(matching_courses),
            'keyword': keyword,
            'search_fields': search_fields,
            'include_syllabus_search': include_syllabus_search,
            'showing': len(limited_results),
            'metadata': self._get_metadata(sem)
        }

    def search_across_semesters(self,
                                keyword: str,
                                limit: int = 20,
                                search_fields: Optional[List[str]] = None,
                                semesters: Optional[List[str]] = None):
        """
        跨學期搜尋通識課程

        Args:
            keyword: 搜尋關鍵字
            limit: 每個學期的回傳結果數量限制
            search_fields: 要搜尋的欄位列表
            semesters: 要搜尋的學期列表，None 表示搜尋所有學期

        Returns:
            按學期分組的搜尋結果
        """
        if search_fields is None:
            search_fields = ['科目名稱', '上課教師', '開課單位']

        if not keyword.strip():
            return {
                'results': {},
                'total': 0,
                'message': '請提供搜尋關鍵字'
            }

        target_semesters = semesters or self.available_semesters
        search_term = keyword.lower()

        all_results = {}
        total_count = 0

        for sem in target_semesters:
            try:
                courses = self.get_courses(sem)
            except Exception:
                continue

            matching_courses = []
            for course in courses:
                match_info = self._search_in_course(
                    course, search_term, search_fields,
                    case_sensitive=False,
                    include_syllabus_search=False
                )

                if match_info['is_match']:
                    matching_courses.append({
                        'course': self._format_course_result(course, semester=sem),
                        'relevance_score': match_info['score'],
                        'matched_fields': match_info['matched_fields']
                    })

            if matching_courses:
                matching_courses.sort(
                    key=lambda x: x['relevance_score'], reverse=True)
                all_results[sem] = {
                    'semester_description': semester_to_description(sem),
                    'count': len(matching_courses),
                    'results': matching_courses[:limit]
                }
                total_count += len(matching_courses)

        return {
            'results': all_results,
            'total': total_count,
            'keyword': keyword,
            'semesters_searched': len(target_semesters),
            'semesters_with_results': len(all_results)
        }

    def search_by_department(self, department: str, limit: int = 20, semester: Optional[str] = None):
        """按系所搜尋通識課程（搜尋該系所開設的通識課程）"""
        return self.search_courses(
            department,
            limit=limit,
            search_fields=['開課單位', '系所名稱'],
            semester=semester
        )

    def search_by_type(self, course_type: str, limit: int = 20, semester: Optional[str] = None):
        """按課程類別搜尋（必修/選修）"""
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        matching_courses = []

        for course in courses:
            course_category = course.get('必選別', '')

            if course_type in course_category:
                matching_courses.append({
                    'course': self._format_course_result(course),
                    'relevance_score': 5,
                    'matched_fields': ['必選別'],
                    'matched_content': {'必選別': course_category}
                })

        return {
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'keyword': course_type,
            'metadata': self._get_metadata(sem)
        }

    def search_by_teacher(self, teacher_name: str, limit: int = 20, semester: Optional[str] = None):
        """按授課教師搜尋通識課程"""
        return self.search_courses(
            teacher_name,
            limit=limit,
            search_fields=['上課教師'],
            semester=semester
        )

    def search_by_time(self, weekday: str, period: Optional[str] = None, limit: int = 20, semester: Optional[str] = None):
        """
        按上課時間搜尋通識課程

        Args:
            weekday: 星期幾 (1-7)
            period: 節次 (1-9, A-D)，可選
            limit: 回傳結果數量限制
            semester: 學期代碼

        Returns:
            搜尋結果
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        matching_courses = []

        for course in courses:
            class_time = course.get("上課時間", "")
            if not class_time:
                continue

            # 檢查星期
            if class_time.startswith(weekday):
                # 如果有指定節次，進一步檢查
                if period:
                    if period in class_time[1:]:
                        matching_courses.append({
                            'course': self._format_course_result(course),
                            'matched_time': class_time
                        })
                else:
                    matching_courses.append({
                        'course': self._format_course_result(course),
                        'matched_time': class_time
                    })

        weekday_str = self.WEEKDAY_MAP.get(weekday, f"星期{weekday}")
        time_desc = weekday_str
        if period:
            time_desc += f" 第{period}節"

        return {
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'showing': min(limit, len(matching_courses)),
            'search_time': time_desc,
            'metadata': self._get_metadata(sem)
        }

    def get_teacher_courses(self, teacher_name: str, exact_match: bool = False, limit: int = 50, semester: Optional[str] = None):
        """
        獲取特定老師的所有通識課程

        Args:
            teacher_name: 教師姓名
            exact_match: 是否精確匹配（完全相同）
            limit: 回傳結果數量限制
            semester: 學期代碼

        Returns:
            該教師的通識課程列表
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        matching_courses = []

        for course in courses:
            teacher = course.get('上課教師', '')

            is_match = False
            if exact_match:
                is_match = teacher == teacher_name
            else:
                is_match = teacher_name in teacher

            if is_match:
                matching_courses.append({
                    'course': self._format_course_result(course),
                    'relevance_score': 10 if exact_match else 8,
                    'matched_fields': ['上課教師'],
                    'matched_content': {'上課教師': teacher}
                })

        return {
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'teacher': teacher_name,
            'exact_match': exact_match,
            'metadata': self._get_metadata(sem)
        }

    def get_teacher_history(self, teacher_name: str, limit_per_semester: int = 10):
        """
        獲取教師的歷年通識課程開課紀錄

        Args:
            teacher_name: 教師姓名
            limit_per_semester: 每學期最多顯示的課程數

        Returns:
            教師的歷年通識課程開課紀錄
        """
        return self.search_across_semesters(
            keyword=teacher_name,
            limit=limit_per_semester,
            search_fields=['上課教師']
        )

    def get_all_teachers(self, semester: Optional[str] = None):
        """
        獲取所有授課教師列表及其開課數量

        Returns:
            教師統計資訊
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        teacher_stats = {}
        teacher_courses = {}

        for course in courses:
            teacher = course.get('上課教師', '').strip()

            if teacher and teacher != '':
                if teacher not in teacher_stats:
                    teacher_stats[teacher] = 0
                    teacher_courses[teacher] = []

                teacher_stats[teacher] += 1
                teacher_courses[teacher].append({
                    '科目名稱': course.get('科目名稱', ''),
                    '開課單位': course.get('開課單位', ''),
                    '必選別': course.get('必選別', ''),
                    '課程大綱URL': course.get('課程大綱URL', '')
                })

        # 按開課數量排序
        sorted_teachers = sorted(
            teacher_stats.items(), key=lambda x: x[1], reverse=True)

        return {
            'total_teachers': len(teacher_stats),
            'teacher_stats': dict(sorted_teachers),
            'teacher_courses': teacher_courses,
            'metadata': self._get_metadata(sem)
        }

    def get_all_departments(self, semester: Optional[str] = None):
        """取得所有開課單位列表"""
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        departments = {}

        for course in courses:
            dept = course.get('開課單位', '')
            dept_code = course.get('系所代碼', '')
            if dept:
                if dept not in departments:
                    departments[dept] = {
                        'code': dept_code,
                        'count': 0
                    }
                departments[dept]['count'] += 1

        # 按課程數排序
        sorted_depts = dict(
            sorted(departments.items(), key=lambda x: x[1]['count'], reverse=True))

        return {
            'departments': sorted_depts,
            'total': len(departments),
            'metadata': self._get_metadata(sem)
        }

    def search_by_domain(self, domain: str, limit: int = 50, semester: Optional[str] = None):
        """
        按領域搜尋通識課程

        Args:
            domain: 領域名稱（如：人文、社會、自然、統合、核心素養、通識資訊素養、敘事表達/大學國文、外國語文(110學年後)）
            limit: 回傳結果數量限制
            semester: 學期代碼

        Returns:
            搜尋結果
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        matching_courses = []

        for course in courses:
            course_domain = course.get('領域', '')
            if domain in course_domain:
                matching_courses.append({
                    'course': self._format_course_result(course),
                    'domain': course_domain,
                    'group': course.get('學群', '')
                })

        return {
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'showing': min(limit, len(matching_courses)),
            'search_domain': domain,
            'metadata': self._get_metadata(sem)
        }

    def search_by_group(self, group: str, limit: int = 50, semester: Optional[str] = None):
        """
        按學群搜尋通識課程

        Args:
            group: 學群名稱（如：歷史、文化、藝術、生命科學、環境科學等）
            limit: 回傳結果數量限制
            semester: 學期代碼

        Returns:
            搜尋結果
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        matching_courses = []

        for course in courses:
            course_group = course.get('學群', '')
            if group in course_group:
                matching_courses.append({
                    'course': self._format_course_result(course),
                    'domain': course.get('領域', ''),
                    'group': course_group
                })

        return {
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'showing': min(limit, len(matching_courses)),
            'search_group': group,
            'metadata': self._get_metadata(sem)
        }

    def get_all_domains(self, semester: Optional[str] = None):
        """
        取得所有領域列表及課程數量

        Args:
            semester: 學期代碼

        Returns:
            領域統計資訊
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        domains = {}

        for course in courses:
            domain = course.get('領域', '')
            if domain:
                if domain not in domains:
                    domains[domain] = {
                        'count': 0,
                        'groups': set()
                    }
                domains[domain]['count'] += 1
                group = course.get('學群', '')
                if group:
                    domains[domain]['groups'].add(group)

        # 轉換 set 為 list 並排序
        result = {}
        for domain, info in sorted(domains.items(), key=lambda x: -x[1]['count']):
            result[domain] = {
                'count': info['count'],
                'groups': sorted(list(info['groups']))
            }

        return {
            'domains': result,
            'total': len(domains),
            'metadata': self._get_metadata(sem)
        }

    def get_all_groups(self, semester: Optional[str] = None):
        """
        取得所有學群列表及課程數量

        Args:
            semester: 學期代碼

        Returns:
            學群統計資訊
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)
        groups = {}

        for course in courses:
            group = course.get('學群', '')
            domain = course.get('領域', '')
            if group:
                if group not in groups:
                    groups[group] = {
                        'count': 0,
                        'domain': domain
                    }
                groups[group]['count'] += 1

        # 按課程數排序
        sorted_groups = dict(
            sorted(groups.items(), key=lambda x: -x[1]['count']))

        return {
            'groups': sorted_groups,
            'total': len(groups),
            'metadata': self._get_metadata(sem)
        }

    def get_course_detail(self, course_id: str, include_syllabus: bool = True, semester: Optional[str] = None):
        """
        取得通識課程詳細資訊

        Args:
            course_id: 選課號碼
            include_syllabus: 是否包含課程大綱（預設為 True）
            semester: 學期代碼

        Returns:
            通識課程詳細資訊
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)

        for course in courses:
            if course.get("選課號碼") == course_id:
                return {
                    'course': self._format_course_result(
                        course,
                        include_details=True,
                        include_syllabus=include_syllabus
                    ),
                    'found': True,
                    'metadata': self._get_metadata(sem)
                }

        return {
            'found': False,
            'message': f'找不到選課號碼為 {course_id} 的通識課程',
            'metadata': self._get_metadata(sem)
        }

    def get_stats(self, semester: Optional[str] = None):
        """獲取統計資訊"""
        sem = semester or self.current_semester
        courses = self.get_courses(sem)

        if not courses:
            return {'message': '通識課程資料未載入'}

        stats = {
            '總課程數': len(courses),
            '領域統計': {},
            '學群統計': {},
            '開課單位統計': {},
            '必選別統計': {},
            '授課語言統計': {},
            '學分數統計': {},
            '教師統計': {},
            'metadata': self._get_metadata(sem)
        }

        # 統計領域分布
        for course in courses:
            domain = course.get('領域', '未知')
            stats['領域統計'][domain] = stats['領域統計'].get(domain, 0) + 1

        # 統計學群分布
        for course in courses:
            group = course.get('學群', '未知')
            stats['學群統計'][group] = stats['學群統計'].get(group, 0) + 1

        # 統計開課單位分布
        for course in courses:
            dept = course.get('開課單位', '未知')
            stats['開課單位統計'][dept] = stats['開課單位統計'].get(dept, 0) + 1

        # 統計必選別分布
        for course in courses:
            course_type = course.get('必選別', '未知')
            stats['必選別統計'][course_type] = stats['必選別統計'].get(
                course_type, 0) + 1

        # 統計授課語言分布
        for course in courses:
            lang = course.get('授課語言', '未知')
            stats['授課語言統計'][lang] = stats['授課語言統計'].get(lang, 0) + 1

        # 統計學分數分布
        for course in courses:
            credits = course.get('學分數', course.get('學分', '未知'))
            stats['學分數統計'][credits] = stats['學分數統計'].get(credits, 0) + 1

        # 統計教師分布
        for course in courses:
            teacher = course.get('上課教師', course.get('授課教師', '未知')).strip()
            if teacher and teacher != '':
                stats['教師統計'][teacher] = stats['教師統計'].get(teacher, 0) + 1

        # 取前10名開課最多的教師
        top_teachers = sorted(stats['教師統計'].items(),
                              key=lambda x: x[1], reverse=True)[:10]
        stats['開課最多教師前10名'] = dict(top_teachers)

        return stats


# 初始化全域搜尋器
searcher = GECourseSearcher()

mcp = FastMCP("nchu_ge_course_search")


@mcp.tool()
def nchu_ge_course_search_by_keyword(
    keyword: str,
    limit: int = 10,
    search_fields: str | None = None,
    case_sensitive: bool = False,
    include_syllabus_search: bool = False,
    include_syllabus_in_result: bool = False,
    semester: str | None = None
) -> str:
    """Search for general education (GE) courses in NCHU course database.

    Args:
        keyword: Search keyword
        limit: Maximum number of results to return (default: 10)
        search_fields: Comma-separated fields to search in (default: 科目名稱,上課教師,開課單位,系所名稱,備註)
        case_sensitive: Whether search is case sensitive (default: False)
        include_syllabus_search: Also search in syllabus content (課程簡述, 課程目標, 每週授課內容, etc.) (default: False)
        include_syllabus_in_result: Include full syllabus in results (default: False)
        semester: Semester code (e.g., "1142" for 113-2). If not specified, uses the latest semester.

    Returns:
        JSON string containing search results
    """
    try:
        fields = None
        if search_fields:
            fields = [field.strip() for field in search_fields.split(',')]

        results = searcher.search_courses(
            keyword=keyword,
            limit=limit,
            search_fields=fields,
            case_sensitive=case_sensitive,
            include_syllabus_search=include_syllabus_search,
            include_syllabus_in_result=include_syllabus_in_result,
            semester=semester
        )

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋通識課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_across_semesters(
    keyword: str,
    limit_per_semester: int = 10,
    search_fields: str | None = None,
    semesters: str | None = None
) -> str:
    """Search for general education courses across multiple semesters. Useful for finding historical course offerings.

    Note: This may be slow if searching all semesters as it loads data on demand.

    Args:
        keyword: Search keyword (course name, teacher name, etc.)
        limit_per_semester: Maximum number of results per semester (default: 10)
        search_fields: Comma-separated fields to search in (default: 科目名稱,上課教師,開課單位)
        semesters: Comma-separated semester codes to search (e.g., "1142,1141,1132"). If not specified, searches all available semesters.

    Returns:
        JSON string containing search results grouped by semester
    """
    try:
        fields = None
        if search_fields:
            fields = [field.strip() for field in search_fields.split(',')]

        sem_list = None
        if semesters:
            sem_list = [s.strip() for s in semesters.split(',')]

        results = searcher.search_across_semesters(
            keyword=keyword,
            limit=limit_per_semester,
            search_fields=fields,
            semesters=sem_list
        )

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'跨學期搜尋通識課程時發生錯誤: {str(e)}',
            'results': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_available_semesters() -> str:
    """Get all available semesters in the general education course database.

    Returns:
        JSON string containing list of available semesters with descriptions
    """
    try:
        results = searcher.get_available_semesters()
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'取得學期列表時發生錯誤: {str(e)}',
            'semesters': []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_department(department: str, limit: int = 20, semester: str | None = None) -> str:
    """Search general education courses OFFERED by a specific department.

    Args:
        department: Department name to search for (e.g., 通識教育中心, 文學院, 管理學院)
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_department(department, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按系所搜尋通識課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_type(course_type: str, limit: int = 20, semester: str | None = None) -> str:
    """Search general education courses by course type (required/elective).

    Args:
        course_type: Course type to search for (e.g., 必修, 選修)
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_type(course_type, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按課程類別搜尋通識課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_teacher(teacher_name: str, limit: int = 20, semester: str | None = None) -> str:
    """Search general education courses by teacher name.

    Args:
        teacher_name: Teacher name to search for
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_teacher(teacher_name, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按授課教師搜尋通識課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_time(weekday: str, period: str | None = None, limit: int = 20, semester: str | None = None) -> str:
    """Search general education courses by class time.

    Args:
        weekday: Day of week (1=Monday, 2=Tuesday, ..., 7=Sunday)
        period: Class period (1-9 for day classes, A-D for evening classes), optional
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_time(weekday, period, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋通識課程上課時間時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_stats(semester: str | None = None) -> str:
    """Get statistics about the general education course database.

    Args:
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing database statistics
    """
    try:
        stats = searcher.get_stats(semester)
        return json.dumps(stats, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取統計資訊時發生錯誤: {str(e)}',
            'message': '無法獲取統計資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_detail(course_id: str, include_syllabus: bool = True, semester: str | None = None) -> str:
    """Get detailed information about a specific general education course, including full syllabus.

    Args:
        course_id: Course ID (選課號碼)
        include_syllabus: Include full syllabus content (課程簡述, 課程目標, 每週授課內容, 教學方法, 評量方法, etc.) (default: True)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing detailed course information with syllabus
    """
    try:
        result = searcher.get_course_detail(
            course_id, include_syllabus=include_syllabus, semester=semester)
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取通識課程詳細資訊時發生錯誤: {str(e)}',
            'message': '無法獲取通識課程詳細資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_teacher_courses(teacher_name: str, exact_match: bool = False, limit: int = 50, semester: str | None = None) -> str:
    """Get all general education courses taught by a specific teacher.

    Args:
        teacher_name: Teacher name
        exact_match: Whether to use exact match (default: False)
        limit: Maximum number of results to return (default: 50)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing teacher's general education courses
    """
    try:
        results = searcher.get_teacher_courses(
            teacher_name, exact_match, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取教師通識課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_teacher_history(teacher_name: str, limit_per_semester: int = 10) -> str:
    """Get a teacher's general education course history across all semesters.

    This searches all available semesters to find general education courses taught by the specified teacher.
    Note: This may be slow as it loads data from all semesters.

    Args:
        teacher_name: Teacher name to search for
        limit_per_semester: Maximum number of courses to show per semester (default: 10)

    Returns:
        JSON string containing teacher's general education course history grouped by semester
    """
    try:
        results = searcher.get_teacher_history(
            teacher_name, limit_per_semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取教師歷年通識課程時發生錯誤: {str(e)}',
            'results': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_all_teachers(semester: str | None = None) -> str:
    """Get all teachers and their general education course statistics.

    Args:
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing all teachers and their course counts
    """
    try:
        results = searcher.get_all_teachers(semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取教師列表時發生錯誤: {str(e)}',
            'message': '無法獲取教師列表'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_all_departments(semester: str | None = None) -> str:
    """Get all departments and their general education course counts.

    Args:
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing all departments and their course counts
    """
    try:
        results = searcher.get_all_departments(semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取開課單位列表時發生錯誤: {str(e)}',
            'message': '無法獲取開課單位列表'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_time_format_help() -> str:
    """Get help information about class time format codes.

    Returns:
        JSON string containing time format explanation
    """
    help_text = {
        "說明": "上課時間代碼格式為「星期+節次」，例如 334 = 星期三第3、4節",
        "星期對照": GECourseSearcher.WEEKDAY_MAP,
        "節次對照": GECourseSearcher.TIME_SLOTS,
        "範例": {
            "334": "星期三 第3節(10:10-11:00), 第4節(11:10-12:00)",
            "156": "星期一 第5節(13:10-14:00), 第6節(14:10-15:00)",
            "2AB": "星期二 第A節(18:30-19:20), 第B節(19:25-20:15)"
        }
    }
    return json.dumps(help_text, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_syllabus(
    keyword: str,
    limit: int = 10,
    include_syllabus_in_result: bool = False,
    semester: str | None = None
) -> str:
    """Search general education courses by syllabus content.

    This tool specifically searches within course syllabus fields including:
    - 課程簡述 (Course description)
    - 課程目標 (Course objectives)
    - 教學方法 (Teaching methods)
    - 評量方法 (Assessment methods)
    - 每週授課內容 (Weekly course content)
    - 教科書與參考書目 (Textbooks and references)
    - 核心能力 (Core competencies)
    - 課程教材 (Course materials)

    Args:
        keyword: Search keyword to find in syllabus content
        limit: Maximum number of results to return (default: 10)
        include_syllabus_in_result: Include full syllabus in results (default: False)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing courses with matching syllabus content
    """
    try:
        results = searcher.search_courses(
            keyword=keyword,
            limit=limit,
            search_fields=[],  # 不搜尋頂層欄位
            include_syllabus_search=True,
            include_syllabus_in_result=include_syllabus_in_result,
            semester=semester
        )

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋通識課程大綱時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_teaching_method(method: str, limit: int = 20, semester: str | None = None) -> str:
    """Search general education courses by teaching method.

    Common teaching methods: 講授, 討論, 習作, 實習, 實驗, 專題, 報告, 演講, etc.

    Args:
        method: Teaching method to search for (e.g., 實習, 討論, 專題)
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing courses using the specified teaching method
    """
    try:
        sem = semester or searcher.current_semester
        courses = searcher.get_courses(sem)
        matching_courses = []

        for course in courses:
            syllabus = course.get("課程大綱", {})
            teaching_methods = syllabus.get("教學方法", [])

            for tm in teaching_methods:
                if method in tm:
                    matching_courses.append({
                        'course': searcher._format_course_result(course, include_syllabus=False),
                        'matched_teaching_methods': teaching_methods
                    })
                    break

        return json.dumps({
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'showing': min(limit, len(matching_courses)),
            'search_method': method,
            'metadata': searcher._get_metadata(sem)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋教學方法時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_assessment_method(method: str, limit: int = 20, semester: str | None = None) -> str:
    """Search general education courses by assessment/evaluation method.

    Common assessment methods: 期中考, 期末考, 作業, 報告, 實作, 出席, 小考, 作品, etc.

    Args:
        method: Assessment method to search for (e.g., 實作, 報告, 期末考)
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing courses using the specified assessment method
    """
    try:
        sem = semester or searcher.current_semester
        courses = searcher.get_courses(sem)
        matching_courses = []

        for course in courses:
            syllabus = course.get("課程大綱", {})
            assessment_methods = syllabus.get("評量方法", [])

            for am in assessment_methods:
                if method in am:
                    matching_courses.append({
                        'course': searcher._format_course_result(course, include_syllabus=False),
                        'matched_assessment_methods': assessment_methods
                    })
                    break

        return json.dumps({
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'showing': min(limit, len(matching_courses)),
            'search_method': method,
            'metadata': searcher._get_metadata(sem)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋評量方法時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_sdg(sdg_keyword: str, limit: int = 20, semester: str | None = None) -> str:
    """Search general education courses by UN Sustainable Development Goals (SDGs).

    Args:
        sdg_keyword: SDG keyword to search for (e.g., 氣候, 永續, 健康, 教育)
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing courses related to the specified SDG
    """
    try:
        sem = semester or searcher.current_semester
        courses = searcher.get_courses(sem)
        matching_courses = []

        for course in courses:
            syllabus = course.get("課程大綱", {})
            sdg = syllabus.get("聯合國全球永續發展目標", "")

            if sdg and sdg_keyword.lower() in sdg.lower():
                matching_courses.append({
                    'course': searcher._format_course_result(course, include_syllabus=False),
                    'matched_sdg': sdg
                })

        return json.dumps({
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'showing': min(limit, len(matching_courses)),
            'search_sdg': sdg_keyword,
            'metadata': searcher._get_metadata(sem)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋永續發展目標時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_weekly_content(course_id: str, semester: str | None = None) -> str:
    """Get weekly course content for a specific general education course.

    Args:
        course_id: Course ID (選課號碼)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing weekly course content (每週授課內容)
    """
    try:
        sem = semester or searcher.current_semester
        courses = searcher.get_courses(sem)

        for course in courses:
            if course.get("選課號碼") == course_id:
                syllabus = course.get("課程大綱", {})
                return json.dumps({
                    'found': True,
                    'course_id': course_id,
                    'course_name': course.get("科目名稱", ""),
                    'teacher': course.get("上課教師", ""),
                    '每週授課內容': syllabus.get("每週授課內容", {}),
                    'metadata': searcher._get_metadata(sem)
                }, ensure_ascii=False, indent=2)

        return json.dumps({
            'found': False,
            'message': f'找不到選課號碼為 {course_id} 的通識課程',
            'metadata': searcher._get_metadata(sem)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取每週授課內容時發生錯誤: {str(e)}',
            'message': '無法獲取每週授課內容'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_domain(domain: str, limit: int = 50, semester: str | None = None) -> str:
    """Search general education courses by domain (領域).

    Available domains: 人文, 社會, 自然, 統合, 核心素養, 通識資訊素養, 敘事表達/大學國文, 外國語文(110學年後)

    Args:
        domain: Domain name to search for (e.g., 人文, 社會, 自然, 統合, 核心素養, 通識資訊素養, 敘事表達/大學國文, 外國語文(110學年後))
        limit: Maximum number of results to return (default: 50)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing courses in the specified domain
    """
    try:
        results = searcher.search_by_domain(domain, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按領域搜尋通識課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_search_by_group(group: str, limit: int = 50, semester: str | None = None) -> str:
    """Search general education courses by group (學群).

    Common groups include: 歷史, 文化, 藝術, 哲學, 文學, 法律與政治, 心理與教育,
    公民與社會, 商業與管理, 生命科學, 環境科學, 物質科學, 工程科技, 數學統計,
    資訊與傳播, 專業實作, 在地關懷, 全球思維, 自我表達, 審美求真, 反思創新, etc.

    Args:
        group: Group name to search for (e.g., 歷史, 藝術, 生命科學, 專業實作)
        limit: Maximum number of results to return (default: 50)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing courses in the specified group
    """
    try:
        results = searcher.search_by_group(group, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按學群搜尋通識課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_all_domains(semester: str | None = None) -> str:
    """Get all available domains (領域) and their course counts.

    This returns the list of all domains in the general education curriculum,
    along with the number of courses in each domain and the groups under each domain.

    Args:
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing all domains with course counts and associated groups
    """
    try:
        results = searcher.get_all_domains(semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取領域列表時發生錯誤: {str(e)}',
            'domains': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_ge_course_get_all_groups(semester: str | None = None) -> str:
    """Get all available groups (學群) and their course counts.

    This returns the list of all groups in the general education curriculum,
    along with the number of courses in each group and the domain it belongs to.

    Args:
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing all groups with course counts and their domains
    """
    try:
        results = searcher.get_all_groups(semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取學群列表時發生錯誤: {str(e)}',
            'groups': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
