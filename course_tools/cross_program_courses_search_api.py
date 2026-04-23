#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides cross-program (學分學程) course search functionality for NCHU courses across all semesters."""

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


# 學制類型對照表
DEGREE_TYPES = {
    'U': '大學部',
    'G': '研究所',
}


class CrossProgramCourseSearcher:
    """學分學程課程搜尋器 - 支援多學期學分學程課程搜尋"""

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
    SYLLABUS_LIST_FIELDS = ['教學方法', '評量方法', '課程教材']

    def __init__(self, data_dir: str = "data/courses/all_cross_program_courses_syllabi"):
        """
        初始化學分學程課程搜尋器

        Args:
            data_dir: 學分學程課程資料目錄路徑
        """
        self.parent_dir = Path(__file__).parent.parent
        self.data_dir = self.parent_dir / data_dir

        # 學期管理 - 按學制類型分類
        self.available_semesters: Dict[str, List[str]] = {'U': [], 'G': []}
        self.all_semesters: List[str] = []
        self.current_semester: str = ""
        self.loaded_data: Dict[str, List[Dict]] = {}  # key: "{semester}_{type}"

        # 初始化
        self._scan_available_semesters()
        self._load_current_semester()

    def _scan_available_semesters(self):
        """掃描可用的學期與學制"""
        if not self.data_dir.exists():
            raise RuntimeError(f"資料目錄不存在: {self.data_dir}")

        semesters_set = set()
        for f in self.data_dir.glob("cross_*.json"):
            # 從 cross_1142_U.json 提取 1142 和 U
            parts = f.stem.replace("cross_", "").split("_")
            if len(parts) == 2:
                semester, degree_type = parts
                if len(semester) == 4 and semester.isdigit() and degree_type in DEGREE_TYPES:
                    self.available_semesters[degree_type].append(semester)
                    semesters_set.add(semester)

        # 排序各學制的學期（最新的在前）
        for degree_type in self.available_semesters:
            self.available_semesters[degree_type] = sorted(
                self.available_semesters[degree_type], reverse=True)

        # 所有學期排序
        self.all_semesters = sorted(list(semesters_set), reverse=True)

        if self.all_semesters:
            self.current_semester = self.all_semesters[0]
        else:
            raise RuntimeError(f"資料目錄中沒有找到學分學程課程資料: {self.data_dir}")

    def _load_current_semester(self):
        """載入當前學期所有學制資料"""
        if self.current_semester:
            for degree_type in DEGREE_TYPES:
                try:
                    self.load_semester(self.current_semester, degree_type)
                except (ValueError, RuntimeError):
                    pass  # 某些學制可能沒有該學期資料

    def load_semester(self, semester: str, degree_type: str = 'U') -> List[Dict]:
        """
        載入指定學期的學分學程課程資料

        Args:
            semester: 學期代碼
            degree_type: 學制類型 (U/G)

        Returns:
            該學期的學分學程課程列表
        """
        cache_key = f"{semester}_{degree_type}"
        if cache_key in self.loaded_data:
            return self.loaded_data[cache_key]

        if semester not in self.available_semesters.get(degree_type, []):
            available = self.available_semesters.get(degree_type, [])[:5]
            raise ValueError(
                f"學期 {semester} ({DEGREE_TYPES.get(degree_type, degree_type)}) 不存在，可用學期: {', '.join(available)}...")

        json_path = self.data_dir / f"cross_{semester}_{degree_type}.json"

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # 支援帶 metadata 的新格式 {"metadata": {...}, "data": [...]}
            # 也相容舊格式（直接是 list）
            if isinstance(raw, dict):
                courses = raw.get('data', [])
            else:
                courses = raw
            self.loaded_data[cache_key] = courses
            return courses
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {json_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 格式錯誤: {e}")

    def get_courses(self, semester: Optional[str] = None, degree_type: str = 'U') -> List[Dict]:
        """
        取得指定學期的學分學程課程列表

        Args:
            semester: 學期代碼，None 表示使用當前學期
            degree_type: 學制類型 (U/G)

        Returns:
            學分學程課程列表
        """
        sem = semester or self.current_semester
        return self.load_semester(sem, degree_type)

    def get_all_courses(self, semester: Optional[str] = None) -> List[Dict]:
        """
        取得指定學期所有學制的學分學程課程

        Args:
            semester: 學期代碼，None 表示使用當前學期

        Returns:
            所有學制的學分學程課程列表
        """
        sem = semester or self.current_semester
        all_courses = []
        for degree_type in DEGREE_TYPES:
            try:
                courses = self.get_courses(sem, degree_type)
                # 加入學制標記
                for course in courses:
                    course['_degree_type'] = degree_type
                    course['_degree_type_name'] = DEGREE_TYPES[degree_type]
                all_courses.extend(courses)
            except (ValueError, RuntimeError):
                pass
        return all_courses

    def get_available_semesters(self) -> Dict[str, Any]:
        """
        取得所有可用學期列表

        Returns:
            包含學期列表及說明的字典
        """
        semester_info = {}

        for degree_type, semesters in self.available_semesters.items():
            semester_info[degree_type] = {
                'degree_type_name': DEGREE_TYPES[degree_type],
                'total': len(semesters),
                'semesters': [
                    {
                        'code': sem,
                        'description': semester_to_description(sem),
                        'loaded': f"{sem}_{degree_type}" in self.loaded_data
                    }
                    for sem in semesters
                ]
            }

        return {
            'current_semester': self.current_semester,
            'current_semester_description': semester_to_description(self.current_semester),
            'all_semesters': self.all_semesters,
            'by_degree_type': semester_info
        }

    def _get_metadata(self, semester: Optional[str] = None, degree_type: Optional[str] = None) -> Dict[str, str]:
        """取得搜尋結果的 metadata"""
        sem = semester or self.current_semester
        metadata = {
            'semester': sem,
            'description': semester_to_description(sem),
            'course_type': '學分學程課程'
        }
        if degree_type:
            metadata['degree_type'] = degree_type
            metadata['degree_type_name'] = DEGREE_TYPES.get(degree_type, degree_type)
        return metadata

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
            "學程代碼": course.get("學程代碼", ""),
            "學程名稱": course.get("學程名稱", ""),
            "上課教師": course.get("上課教師", ""),
            "開課單位": course.get("開課單位", ""),
            "必選別": course.get("必選別", ""),
            "學分數": course.get("學分數", course.get("學分", "")),
            "上課時間": course.get("上課時間", ""),
            "上課時間說明": self._parse_class_time(course.get("上課時間", "")),
            "上課教室": course.get("上課教室", ""),
            "授課語言": course.get("授課語言(註2,3)", course.get("授課語言", "")),
            "課程大綱URL": course.get("課程大綱URL", ""),
        }

        # 如果有學制標記
        if "_degree_type" in course:
            result["學制"] = course.get("_degree_type_name", "")

        if semester:
            result["學期"] = semester
            result["學期說明"] = semester_to_description(semester)

        if include_details:
            result.update({
                "先修科目": course.get("先修科目", ""),
                "全半年": course.get("全/半年", course.get("全半年", "")),
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
            core_abilities = syllabus.get("核心能力與配比", [])
            result["課程大綱"] = {
                "課程名稱_中": syllabus.get("課程名稱_中", ""),
                "課程名稱_英": syllabus.get("課程名稱_英", ""),
                "開課單位": syllabus.get("開課單位", ""),
                "課程類別": syllabus.get("課程類別", ""),
                "英文/EMI": syllabus.get("英文/EMI", ""),
                "開課學期": syllabus.get("開課學期", ""),
                "課程簡述": syllabus.get("課程簡述", ""),
                "先修課程名稱": syllabus.get("先修課程名稱", ""),
                "課程目標": syllabus.get("課程目標", ""),
                "核心能力與配比": core_abilities,
                "教學方法": syllabus.get("教學方法", []),
                "評量方法": syllabus.get("評量方法", []),
                "每週授課內容": syllabus.get("每週授課內容", {}),
                "自主學習內容": syllabus.get("自主學習內容", ""),
                "學習評量方式": syllabus.get("學習評量方式", ""),
                "教科書與參考書目": syllabus.get("教科書與參考書目", ""),
                "課程教材": syllabus.get("課程教材", []),
                "課程輔導時間": syllabus.get("課程輔導時間", ""),
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
                # 科目名稱、學程名稱和教師權重較高
                if field == "科目名稱":
                    score += 3
                elif field == "學程名稱":
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
                       semester: Optional[str] = None,
                       degree_type: Optional[str] = None):
        """
        搜尋學分學程課程

        Args:
            keyword: 搜尋關鍵字
            limit: 回傳結果數量限制
            search_fields: 要搜尋的欄位列表
            case_sensitive: 是否區分大小寫
            include_syllabus_search: 是否同時搜尋課程大綱內容
            include_syllabus_in_result: 是否在結果中包含課程大綱
            semester: 學期代碼，None 表示使用最新學期
            degree_type: 學制類型 (U/G)，None 表示搜尋所有學制

        Returns:
            搜尋結果字典
        """
        if search_fields is None:
            search_fields = ['科目名稱', '學程名稱', '上課教師', '開課單位', '備註']

        if not keyword.strip():
            return {
                'results': [],
                'total': 0,
                'message': '請提供搜尋關鍵字'
            }

        sem = semester or self.current_semester

        # 取得課程列表
        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

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
            'metadata': self._get_metadata(sem, degree_type)
        }

    def search_across_semesters(self,
                                keyword: str,
                                limit: int = 20,
                                search_fields: Optional[List[str]] = None,
                                semesters: Optional[List[str]] = None,
                                degree_type: Optional[str] = None):
        """
        跨學期搜尋學分學程課程

        Args:
            keyword: 搜尋關鍵字
            limit: 每個學期的回傳結果數量限制
            search_fields: 要搜尋的欄位列表
            semesters: 要搜尋的學期列表，None 表示搜尋所有學期
            degree_type: 學制類型 (U/G)，None 表示搜尋所有學制

        Returns:
            按學期分組的搜尋結果
        """
        if search_fields is None:
            search_fields = ['科目名稱', '學程名稱', '上課教師', '開課單位']

        if not keyword.strip():
            return {
                'results': {},
                'total': 0,
                'message': '請提供搜尋關鍵字'
            }

        target_semesters = semesters or self.all_semesters
        search_term = keyword.lower()

        all_results = {}
        total_count = 0

        degree_types_to_search = [degree_type] if degree_type else list(DEGREE_TYPES.keys())

        for sem in target_semesters:
            semester_results = []

            for dt in degree_types_to_search:
                try:
                    courses = self.get_courses(sem, dt)
                except Exception:
                    continue

                for course in courses:
                    match_info = self._search_in_course(
                        course, search_term, search_fields,
                        case_sensitive=False,
                        include_syllabus_search=False
                    )

                    if match_info['is_match']:
                        course_result = self._format_course_result(course, semester=sem)
                        course_result['學制'] = DEGREE_TYPES.get(dt, dt)
                        semester_results.append({
                            'course': course_result,
                            'relevance_score': match_info['score'],
                            'matched_fields': match_info['matched_fields']
                        })

            if semester_results:
                semester_results.sort(key=lambda x: x['relevance_score'], reverse=True)
                all_results[sem] = {
                    'semester_description': semester_to_description(sem),
                    'count': len(semester_results),
                    'results': semester_results[:limit]
                }
                total_count += len(semester_results)

        return {
            'results': all_results,
            'total': total_count,
            'keyword': keyword,
            'semesters_searched': len(target_semesters),
            'semesters_with_results': len(all_results)
        }

    def search_by_program(self, program_name: str, limit: int = 50, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """按學程名稱搜尋課程"""
        return self.search_courses(
            program_name,
            limit=limit,
            search_fields=['學程名稱'],
            semester=semester,
            degree_type=degree_type
        )

    def search_by_department(self, department: str, limit: int = 20, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """按系所搜尋學分學程課程（搜尋該系所開設的課程）"""
        return self.search_courses(
            department,
            limit=limit,
            search_fields=['開課單位'],
            semester=semester,
            degree_type=degree_type
        )

    def search_by_teacher(self, teacher_name: str, limit: int = 20, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """按授課教師搜尋學分學程課程"""
        return self.search_courses(
            teacher_name,
            limit=limit,
            search_fields=['上課教師'],
            semester=semester,
            degree_type=degree_type
        )

    def search_by_time(self, weekday: str, period: Optional[str] = None, limit: int = 20, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """
        按上課時間搜尋學分學程課程

        Args:
            weekday: 星期幾 (1-7)
            period: 節次 (1-9, A-D)，可選
            limit: 回傳結果數量限制
            semester: 學期代碼
            degree_type: 學制類型

        Returns:
            搜尋結果
        """
        sem = semester or self.current_semester

        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

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
            'metadata': self._get_metadata(sem, degree_type)
        }

    def get_all_programs(self, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """
        取得所有學程列表及課程數量

        Args:
            semester: 學期代碼
            degree_type: 學制類型

        Returns:
            學程統計資訊
        """
        sem = semester or self.current_semester

        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

        programs = {}

        for course in courses:
            program_name = course.get('學程名稱', '')
            program_code = course.get('學程代碼', '')
            if program_name:
                if program_name not in programs:
                    programs[program_name] = {
                        'code': program_code,
                        'count': 0,
                        'courses': []
                    }
                programs[program_name]['count'] += 1
                programs[program_name]['courses'].append({
                    '科目名稱': course.get('科目名稱', ''),
                    '上課教師': course.get('上課教師', ''),
                    '必選別': course.get('必選別', ''),
                    '學分數': course.get('學分數', ''),
                })

        # 按課程數排序
        sorted_programs = dict(
            sorted(programs.items(), key=lambda x: x[1]['count'], reverse=True))

        return {
            'programs': sorted_programs,
            'total': len(programs),
            'metadata': self._get_metadata(sem, degree_type)
        }

    def get_program_courses(self, program_name: str, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """
        取得特定學程的所有課程

        Args:
            program_name: 學程名稱
            semester: 學期代碼
            degree_type: 學制類型

        Returns:
            該學程的課程列表
        """
        sem = semester or self.current_semester

        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

        matching_courses = []

        for course in courses:
            if program_name in course.get('學程名稱', ''):
                matching_courses.append({
                    'course': self._format_course_result(course, include_details=True),
                    'program_name': course.get('學程名稱', ''),
                    'program_code': course.get('學程代碼', ''),
                })

        return {
            'results': matching_courses,
            'total': len(matching_courses),
            'program_name': program_name,
            'metadata': self._get_metadata(sem, degree_type)
        }

    def get_all_teachers(self, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """
        獲取所有授課教師列表及其開課數量

        Returns:
            教師統計資訊
        """
        sem = semester or self.current_semester

        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

        teacher_stats = {}

        for course in courses:
            teacher = course.get('上課教師', '').strip()

            if teacher and teacher != '':
                if teacher not in teacher_stats:
                    teacher_stats[teacher] = 0
                teacher_stats[teacher] += 1

        # 按開課數量排序
        sorted_teachers = sorted(
            teacher_stats.items(), key=lambda x: x[1], reverse=True)

        return {
            'total_teachers': len(teacher_stats),
            'teacher_stats': dict(sorted_teachers),
            'metadata': self._get_metadata(sem, degree_type)
        }

    def get_all_departments(self, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """取得所有開課單位列表"""
        sem = semester or self.current_semester

        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

        departments = {}

        for course in courses:
            dept = course.get('開課單位', '')
            if dept:
                if dept not in departments:
                    departments[dept] = {'count': 0}
                departments[dept]['count'] += 1

        # 按課程數排序
        sorted_depts = dict(
            sorted(departments.items(), key=lambda x: x[1]['count'], reverse=True))

        return {
            'departments': sorted_depts,
            'total': len(departments),
            'metadata': self._get_metadata(sem, degree_type)
        }

    def get_course_detail(self, course_id: str, include_syllabus: bool = True, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """
        取得課程詳細資訊

        Args:
            course_id: 選課號碼
            include_syllabus: 是否包含課程大綱（預設為 True）
            semester: 學期代碼
            degree_type: 學制類型

        Returns:
            課程詳細資訊
        """
        sem = semester or self.current_semester

        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

        for course in courses:
            if course.get("選課號碼") == course_id:
                return {
                    'course': self._format_course_result(
                        course,
                        include_details=True,
                        include_syllabus=include_syllabus
                    ),
                    'found': True,
                    'metadata': self._get_metadata(sem, degree_type)
                }

        return {
            'found': False,
            'message': f'找不到選課號碼為 {course_id} 的學分學程課程',
            'metadata': self._get_metadata(sem, degree_type)
        }

    def get_stats(self, semester: Optional[str] = None, degree_type: Optional[str] = None):
        """獲取統計資訊"""
        sem = semester or self.current_semester

        if degree_type:
            courses = self.get_courses(sem, degree_type)
        else:
            courses = self.get_all_courses(sem)

        if not courses:
            return {'message': '學分學程課程資料未載入'}

        stats = {
            '總課程數': len(courses),
            '學程統計': {},
            '開課單位統計': {},
            '必選別統計': {},
            '授課語言統計': {},
            '學分數統計': {},
            '教師統計': {},
            'metadata': self._get_metadata(sem, degree_type)
        }

        # 統計學程分布
        for course in courses:
            program = course.get('學程名稱', '未知')
            stats['學程統計'][program] = stats['學程統計'].get(program, 0) + 1

        # 統計開課單位分布
        for course in courses:
            dept = course.get('開課單位', '未知')
            stats['開課單位統計'][dept] = stats['開課單位統計'].get(dept, 0) + 1

        # 統計必選別分布
        for course in courses:
            course_type = course.get('必選別', '未知')
            stats['必選別統計'][course_type] = stats['必選別統計'].get(course_type, 0) + 1

        # 統計授課語言分布
        for course in courses:
            lang = course.get('授課語言(註2,3)', course.get('授課語言', '未知'))
            stats['授課語言統計'][lang] = stats['授課語言統計'].get(lang, 0) + 1

        # 統計學分數分布
        for course in courses:
            credits = course.get('學分數', course.get('學分', '未知'))
            stats['學分數統計'][credits] = stats['學分數統計'].get(credits, 0) + 1

        # 統計教師分布
        for course in courses:
            teacher = course.get('上課教師', '未知').strip()
            if teacher and teacher != '':
                stats['教師統計'][teacher] = stats['教師統計'].get(teacher, 0) + 1

        # 取前10名開課最多的教師
        top_teachers = sorted(stats['教師統計'].items(),
                              key=lambda x: x[1], reverse=True)[:10]
        stats['開課最多教師前10名'] = dict(top_teachers)

        return stats


# 初始化全域搜尋器
searcher = CrossProgramCourseSearcher()

mcp = FastMCP("nchu_cross_program_course_search")


@mcp.tool()
def nchu_cross_program_search_by_keyword(
    keyword: str,
    limit: int = 10,
    search_fields: str | None = None,
    case_sensitive: bool = False,
    include_syllabus_search: bool = False,
    include_syllabus_in_result: bool = False,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Search for cross-program (學分學程) courses in NCHU course database.

    Args:
        keyword: Search keyword
        limit: Maximum number of results to return (default: 10)
        search_fields: Comma-separated fields to search in (default: 科目名稱,學程名稱,上課教師,開課單位,備註)
        case_sensitive: Whether search is case sensitive (default: False)
        include_syllabus_search: Also search in syllabus content (課程簡述, 課程目標, 每週授課內容, etc.) (default: False)
        include_syllabus_in_result: Include full syllabus in results (default: False)
        semester: Semester code (e.g., "1142" for 113-2). If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate/大學部), G (graduate/研究所). If not specified, searches all types.

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
            semester=semester,
            degree_type=degree_type
        )

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋學分學程課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_search_across_semesters(
    keyword: str,
    limit_per_semester: int = 10,
    search_fields: str | None = None,
    semesters: str | None = None,
    degree_type: str | None = None
) -> str:
    """Search for cross-program courses across multiple semesters. Useful for finding historical course offerings.

    Note: This may be slow if searching all semesters as it loads data on demand.

    Args:
        keyword: Search keyword (course name, teacher name, program name, etc.)
        limit_per_semester: Maximum number of results per semester (default: 10)
        search_fields: Comma-separated fields to search in (default: 科目名稱,學程名稱,上課教師,開課單位)
        semesters: Comma-separated semester codes to search (e.g., "1142,1141,1132"). If not specified, searches all available semesters.
        degree_type: Degree type filter - U (undergraduate), G (graduate). If not specified, searches all types.

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
            semesters=sem_list,
            degree_type=degree_type
        )

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'跨學期搜尋學分學程課程時發生錯誤: {str(e)}',
            'results': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_available_semesters() -> str:
    """Get all available semesters in the cross-program course database, organized by degree type.

    Returns:
        JSON string containing list of available semesters with descriptions, organized by degree type (U/G)
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
def nchu_cross_program_search_by_program(
    program_name: str,
    limit: int = 50,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Search cross-program courses by program name (學程名稱).

    Args:
        program_name: Program name to search for (e.g., 永續環境學分學程, 人工智慧學分學程)
        limit: Maximum number of results to return (default: 50)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_program(program_name, limit, semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按學程搜尋課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_all_programs(semester: str | None = None, degree_type: str | None = None) -> str:
    """Get all available programs (學程) and their course counts.

    Args:
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing all programs with course counts and course lists
    """
    try:
        results = searcher.get_all_programs(semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取學程列表時發生錯誤: {str(e)}',
            'programs': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_program_courses(
    program_name: str,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Get all courses in a specific program (學程).

    Args:
        program_name: Program name (e.g., 永續環境學分學程)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing all courses in the specified program
    """
    try:
        results = searcher.get_program_courses(program_name, semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取學程課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_search_by_department(
    department: str,
    limit: int = 20,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Search cross-program courses OFFERED by a specific department.

    Args:
        department: Department name to search for (e.g., 資訊工程學系, 電機工程學系)
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_department(department, limit, semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按系所搜尋學分學程課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_search_by_teacher(
    teacher_name: str,
    limit: int = 20,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Search cross-program courses by teacher name.

    Args:
        teacher_name: Teacher name to search for
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_teacher(teacher_name, limit, semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'按授課教師搜尋學分學程課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_search_by_time(
    weekday: str,
    period: str | None = None,
    limit: int = 20,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Search cross-program courses by class time.

    Args:
        weekday: Day of week (1=Monday, 2=Tuesday, ..., 7=Sunday)
        period: Class period (1-9 for day classes, A-D for evening classes), optional
        limit: Maximum number of results to return (default: 20)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_time(weekday, period, limit, semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋學分學程課程上課時間時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_stats(semester: str | None = None, degree_type: str | None = None) -> str:
    """Get statistics about the cross-program course database.

    Args:
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing database statistics
    """
    try:
        stats = searcher.get_stats(semester, degree_type)
        return json.dumps(stats, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取統計資訊時發生錯誤: {str(e)}',
            'message': '無法獲取統計資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_detail(
    course_id: str,
    include_syllabus: bool = True,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Get detailed information about a specific cross-program course, including full syllabus.

    Args:
        course_id: Course ID (選課號碼)
        include_syllabus: Include full syllabus content (課程簡述, 課程目標, 每週授課內容, 教學方法, 評量方法, etc.) (default: True)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing detailed course information with syllabus
    """
    try:
        result = searcher.get_course_detail(
            course_id, include_syllabus=include_syllabus, semester=semester, degree_type=degree_type)
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取學分學程課程詳細資訊時發生錯誤: {str(e)}',
            'message': '無法獲取學分學程課程詳細資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_all_teachers(semester: str | None = None, degree_type: str | None = None) -> str:
    """Get all teachers and their cross-program course statistics.

    Args:
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing all teachers and their course counts
    """
    try:
        results = searcher.get_all_teachers(semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取教師列表時發生錯誤: {str(e)}',
            'message': '無法獲取教師列表'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_all_departments(semester: str | None = None, degree_type: str | None = None) -> str:
    """Get all departments and their cross-program course counts.

    Args:
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing all departments and their course counts
    """
    try:
        results = searcher.get_all_departments(semester, degree_type)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取開課單位列表時發生錯誤: {str(e)}',
            'message': '無法獲取開課單位列表'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_time_format_help() -> str:
    """Get help information about class time format codes.

    Returns:
        JSON string containing time format explanation
    """
    help_text = {
        "說明": "上課時間代碼格式為「星期+節次」，例如 334 = 星期三第3、4節",
        "星期對照": CrossProgramCourseSearcher.WEEKDAY_MAP,
        "節次對照": CrossProgramCourseSearcher.TIME_SLOTS,
        "範例": {
            "334": "星期三 第3節(10:10-11:00), 第4節(11:10-12:00)",
            "156": "星期一 第5節(13:10-14:00), 第6節(14:10-15:00)",
            "2AB": "星期二 第A節(18:30-19:20), 第B節(19:25-20:15)"
        },
        "學制類型": DEGREE_TYPES
    }
    return json.dumps(help_text, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_search_syllabus(
    keyword: str,
    limit: int = 10,
    include_syllabus_in_result: bool = False,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Search cross-program courses by syllabus content.

    This tool specifically searches within course syllabus fields including:
    - 課程簡述 (Course description)
    - 課程目標 (Course objectives)
    - 教學方法 (Teaching methods)
    - 評量方法 (Assessment methods)
    - 每週授課內容 (Weekly course content)
    - 教科書與參考書目 (Textbooks and references)
    - 課程教材 (Course materials)

    Args:
        keyword: Search keyword to find in syllabus content
        limit: Maximum number of results to return (default: 10)
        include_syllabus_in_result: Include full syllabus in results (default: False)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

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
            semester=semester,
            degree_type=degree_type
        )

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋學分學程課程大綱時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_cross_program_get_weekly_content(
    course_id: str,
    semester: str | None = None,
    degree_type: str | None = None
) -> str:
    """Get weekly course content for a specific cross-program course.

    Args:
        course_id: Course ID (選課號碼)
        semester: Semester code. If not specified, uses the latest semester.
        degree_type: Degree type filter - U (undergraduate), G (graduate).

    Returns:
        JSON string containing weekly course content (每週授課內容)
    """
    try:
        sem = semester or searcher.current_semester

        if degree_type:
            courses = searcher.get_courses(sem, degree_type)
        else:
            courses = searcher.get_all_courses(sem)

        for course in courses:
            if course.get("選課號碼") == course_id:
                syllabus = course.get("課程大綱", {})
                return json.dumps({
                    'found': True,
                    'course_id': course_id,
                    'course_name': course.get("科目名稱", ""),
                    'program_name': course.get("學程名稱", ""),
                    'teacher': course.get("上課教師", ""),
                    '每週授課內容': syllabus.get("每週授課內容", {}),
                    'metadata': searcher._get_metadata(sem, degree_type)
                }, ensure_ascii=False, indent=2)

        return json.dumps({
            'found': False,
            'message': f'找不到選課號碼為 {course_id} 的學分學程課程',
            'metadata': searcher._get_metadata(sem, degree_type)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取每週授課內容時發生錯誤: {str(e)}',
            'message': '無法獲取每週授課內容'
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
