#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides course search functionality for NCHU courses across all semesters."""

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


class CourseSearcher:
    """課程搜尋器 - 支援多學期課程搜尋"""

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
    SYLLABUS_LIST_FIELDS = ['教學方法', '評量方法', '核心能力與配比', '課程教材']

    def __init__(self, data_dir: str = "data/courses/all_courses_syllabi"):
        """
        初始化課程搜尋器

        Args:
            data_dir: 課程資料目錄路徑
        """
        self.parent_dir = Path(__file__).parent.parent
        self.data_dir = self.parent_dir / data_dir

        # 學期管理
        self.available_semesters: List[str] = []
        self.current_semester: str = ""
        self.loaded_semesters: Dict[str, List[Dict]] = {}

        # 初始化
        self._scan_available_semesters()
        self._load_current_semester()

    def _scan_available_semesters(self):
        """掃描可用的學期"""
        if not self.data_dir.exists():
            raise RuntimeError(f"資料目錄不存在: {self.data_dir}")

        semesters = []
        for f in self.data_dir.glob("courses_*.json"):
            # 從 courses_1142.json 提取 1142
            semester = f.stem.replace("courses_", "")
            if len(semester) == 4 and semester.isdigit():
                semesters.append(semester)

        # 按學期排序（最新的在前）
        self.available_semesters = sorted(semesters, reverse=True)

        if self.available_semesters:
            self.current_semester = self.available_semesters[0]
        else:
            raise RuntimeError(f"資料目錄中沒有找到課程資料: {self.data_dir}")

    def _load_current_semester(self):
        """載入當前學期資料"""
        if self.current_semester:
            self.load_semester(self.current_semester)

    def load_semester(self, semester: str) -> List[Dict]:
        """
        載入指定學期的課程資料

        Args:
            semester: 學期代碼

        Returns:
            該學期的課程列表
        """
        if semester in self.loaded_semesters:
            return self.loaded_semesters[semester]

        if semester not in self.available_semesters:
            raise ValueError(
                f"學期 {semester} 不存在，可用學期: {', '.join(self.available_semesters[:5])}...")

        json_path = self.data_dir / f"courses_{semester}.json"

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # 支援兩種格式：
            # 1. {"metadata": {...}, "data": [...]}  (新格式)
            # 2. [...]                               (舊格式: 直接是 list)
            if isinstance(raw, dict) and 'data' in raw:
                courses = raw['data']
            elif isinstance(raw, list):
                courses = raw
            else:
                raise RuntimeError(f"JSON 格式不支援，應為 list 或含 'data' 欄位的 dict: {json_path}")
            self.loaded_semesters[semester] = courses
            return courses
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {json_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 格式錯誤: {e}")

    def get_courses(self, semester: Optional[str] = None) -> List[Dict]:
        """
        取得指定學期的課程列表

        Args:
            semester: 學期代碼，None 表示使用當前學期

        Returns:
            課程列表
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
        return {
            'semester': sem,
            'description': semester_to_description(sem)
        }

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
            "上課教師": course.get("上課教師", ""),
            "開課單位": course.get("開課單位", ""),
            "必選別": course.get("必選別", ""),
            "學分數": course.get("學分數", ""),
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
                "核心能力與配比": syllabus.get("核心能力與配比", []),
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
                        elif isinstance(item, dict):
                            # 處理「核心能力與配比」等對象陣列格式
                            for value in item.values():
                                if isinstance(value, str):
                                    compare_value = value if case_sensitive else value.lower()
                                    if search_term in compare_value:
                                        score += 1
                                        if f"課程大綱.{field}" not in matched_fields:
                                            matched_fields.append(f"課程大綱.{field}")
                                        break

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
        搜尋課程

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
        跨學期搜尋課程

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
        """按系所搜尋課程（搜尋該系所開設的課程）"""
        return self.search_courses(
            department,
            limit=limit,
            search_fields=['開課單位', '系所名稱'],
            semester=semester
        )

    # 學制代碼對照表
    CAREER_CODE_MAP = {
        'C': '學院',
        'U': '學士班',
        'B': '研究所(學院)',
        'G': '碩士班',
        'D': '博士班',
        'R': '產業碩士專班',
        'W': '碩士在職專班',
        'N': '進修學士班',
    }

    # 選課單位中的學制關鍵字對照
    CAREER_KEYWORD_MAP = {
        '學士班': 'U',
        '碩士班': 'G',
        '博士班': 'D',
        '碩專班': 'W',
        '進修學士班': 'N',
        '產業碩士專班': 'R',
    }

    # 學制可選範圍（該學制可以選修哪些學制的課程）
    # 學士班可選學士班和碩士班課程，碩士班不能選學士班課程
    CAREER_SELECTABLE_MAP = {
        'U': ['U', 'G'],        # 學士班可選：學士班、碩士班
        'G': ['G', 'D'],        # 碩士班可選：碩士班、博士班
        'D': ['D'],             # 博士班可選：博士班
        'W': ['W', 'G', 'D'],   # 碩士在職專班可選：碩專班、碩士班、博士班
        'N': ['N', 'U'],        # 進修學士班可選：進修學士班、學士班
        'R': ['R', 'G', 'D'],   # 產業碩士專班可選：產業碩專、碩士班、博士班
        'C': ['C', 'U', 'G', 'D'],  # 學院層級可選所有
        'B': ['B', 'G', 'D'],   # 研究所(學院)可選：研究所、碩士班、博士班
    }

    def _parse_enrollment_unit(self, enrollment_unit: str) -> Dict[str, str]:
        """
        解析選課單位字串

        Args:
            enrollment_unit: 選課單位字串，如 "資工系  / 學士班"

        Returns:
            包含 department（系所）和 career（學制）的字典
        """
        if not enrollment_unit:
            return {'department': '', 'career': '', 'career_code': ''}

        # 格式通常是 "系所名稱  / 學制"
        parts = enrollment_unit.split('/')
        department = parts[0].strip() if parts else ''
        career = parts[1].strip() if len(parts) > 1 else ''

        # 取得學制代碼
        career_code = ''
        for keyword, code in self.CAREER_KEYWORD_MAP.items():
            if keyword in career:
                career_code = code
                break

        return {
            'department': department,
            'career': career,
            'career_code': career_code
        }

    def _extract_dept_code_from_course(self, course: Dict) -> str:
        """
        從課程中提取系所編號（數字部分）

        Args:
            course: 課程資料

        Returns:
            系所編號字串，如 "56"
        """
        dept_code = course.get('系所代碼', '')
        if not dept_code:
            return ''

        # 系所代碼格式為 [學制代碼][數字]，提取數字部分
        import re
        match = re.search(r'[A-Z](\d+)', dept_code)
        return match.group(1) if match else ''

    def _extract_career_from_course(self, course: Dict) -> str:
        """
        從課程中提取學制代碼

        Args:
            course: 課程資料

        Returns:
            學制代碼，如 "U", "G", "D"
        """
        dept_code = course.get('系所代碼', '')
        if dept_code and dept_code[0] in self.CAREER_CODE_MAP:
            return dept_code[0]
        return ''

    def search_selectable_courses(
        self,
        department: str,
        career: str = '學士班',
        limit: int = 20,
        include_other_dept: bool = True,
        semester: Optional[str] = None
    ) -> Dict:
        """
        搜尋某系所某學制學生可選修的課程

        此方法會根據學制規則搜尋可選課程：
        - 學士班學生可選修學士班和碩士班課程
        - 碩士班學生可選修碩士班和博士班課程
        - 碩士班學生不能選修學士班課程

        Args:
            department: 系所名稱關鍵字（如 "資工"、"電機"）
            career: 學制（學士班、碩士班、博士班、碩專班、進修學士班）
            limit: 回傳結果數量限制
            include_other_dept: 是否包含其他系所開設但該系所可選的課程
            semester: 學期代碼

        Returns:
            可選課程搜尋結果
        """
        sem = semester or self.current_semester
        courses = self.get_courses(sem)

        # 取得學制代碼
        career_code = self.CAREER_KEYWORD_MAP.get(career, 'U')

        # 取得該學制可選的學制範圍
        selectable_careers = self.CAREER_SELECTABLE_MAP.get(career_code, [career_code])

        matching_courses = []
        same_dept_courses = []  # 本系開設的課程
        other_dept_courses = []  # 其他系開設但本系可選的課程

        for course in courses:
            syllabus = course.get('課程大綱', {})
            enrollment_unit = syllabus.get('選課單位', '')
            offering_dept = course.get('開課單位', '')

            # 解析選課單位
            parsed = self._parse_enrollment_unit(enrollment_unit)
            target_dept = parsed['department']
            target_career = parsed['career']
            target_career_code = parsed['career_code']

            # 檢查是否為目標系所可選的課程
            if department not in target_dept:
                continue

            # 檢查學制是否在可選範圍內
            if target_career_code and target_career_code not in selectable_careers:
                continue

            course_result = {
                'course': self._format_course_result(course, include_details=False),
                'relevance_score': 5,
                'matched_fields': ['選課單位'],
                'enrollment_info': {
                    '選課單位': enrollment_unit,
                    '開課單位': offering_dept,
                    '目標學制': target_career,
                    '是否本系開設': department in offering_dept
                }
            }

            # 區分本系開設和其他系開設
            if department in offering_dept:
                same_dept_courses.append(course_result)
            else:
                other_dept_courses.append(course_result)

        # 合併結果
        if include_other_dept:
            matching_courses = same_dept_courses + other_dept_courses
        else:
            matching_courses = same_dept_courses

        # 限制結果數量
        limited_results = matching_courses[:limit]

        return {
            'results': limited_results,
            'total': len(matching_courses),
            'showing': len(limited_results),
            'search_params': {
                'department': department,
                'career': career,
                'career_code': career_code,
                'selectable_careers': [self.CAREER_CODE_MAP.get(c, c) for c in selectable_careers],
                'include_other_dept': include_other_dept
            },
            'summary': {
                'same_dept_count': len(same_dept_courses),
                'other_dept_count': len(other_dept_courses),
                'total_count': len(matching_courses)
            },
            'metadata': self._get_metadata(sem)
        }

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
        """按授課教師搜尋課程"""
        return self.search_courses(
            teacher_name,
            limit=limit,
            search_fields=['上課教師'],
            semester=semester
        )

    def search_by_time(self, weekday: str, period: Optional[str] = None, limit: int = 20, semester: Optional[str] = None):
        """
        按上課時間搜尋課程

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
        獲取特定老師的所有課程

        Args:
            teacher_name: 教師姓名
            exact_match: 是否精確匹配（完全相同）
            limit: 回傳結果數量限制
            semester: 學期代碼

        Returns:
            該教師的課程列表
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
        獲取教師的歷年開課紀錄

        Args:
            teacher_name: 教師姓名
            limit_per_semester: 每學期最多顯示的課程數

        Returns:
            教師的歷年開課紀錄
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

    def get_course_detail(self, course_id: str, include_syllabus: bool = True, semester: Optional[str] = None):
        """
        取得課程詳細資訊

        Args:
            course_id: 選課號碼
            include_syllabus: 是否包含課程大綱（預設為 True）
            semester: 學期代碼

        Returns:
            課程詳細資訊
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
            'message': f'找不到選課號碼為 {course_id} 的課程',
            'metadata': self._get_metadata(sem)
        }

    def get_stats(self, semester: Optional[str] = None):
        """獲取統計資訊"""
        sem = semester or self.current_semester
        courses = self.get_courses(sem)

        if not courses:
            return {'message': '課程資料未載入'}

        stats = {
            '總課程數': len(courses),
            '開課單位統計': {},
            '必選別統計': {},
            '授課語言統計': {},
            '學分數統計': {},
            '教師統計': {},
            'metadata': self._get_metadata(sem)
        }

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
            credits = course.get('學分數', '未知')
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
searcher = CourseSearcher()

mcp = FastMCP("nchu_course_search")


@mcp.tool()
def nchu_course_search_by_keyword(
    keyword: str,
    limit: int = 10,
    search_fields: str | None = None,
    case_sensitive: bool = False,
    include_syllabus_search: bool = False,
    include_syllabus_in_result: bool = False,
    semester: str | None = None
) -> str:
    """Search for courses in NCHU course database.

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
            if isinstance(search_fields, list):
                fields = [str(f).strip() for f in search_fields]
            else:
                fields = [field.strip() for field in str(search_fields).split(',')]

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
            'error': f'搜尋課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_search_across_semesters(
    keyword: str,
    limit_per_semester: int = 10,
    search_fields: str | None = None,
    semesters: str | None = None
) -> str:
    """Search for courses across multiple semesters. Useful for finding historical course offerings.

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
            if isinstance(search_fields, list):
                fields = [str(f).strip() for f in search_fields]
            else:
                fields = [field.strip() for field in str(search_fields).split(',')]

        sem_list = None
        if semesters:
            if isinstance(semesters, list):
                sem_list = [str(s).strip() for s in semesters]
            else:
                sem_list = [s.strip() for s in str(semesters).split(',')]

        results = searcher.search_across_semesters(
            keyword=keyword,
            limit=limit_per_semester,
            search_fields=fields,
            semesters=sem_list
        )

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'跨學期搜尋時發生錯誤: {str(e)}',
            'results': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_get_available_semesters() -> str:
    """Get all available semesters in the course database.

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
def nchu_course_search_by_department(department: str, limit: int = 20, semester: str | None = None) -> str:
    """Search courses OFFERED by a specific department.

    This searches for courses where the department is the offering unit (開課單位).
    Use nchu_course_search_selectable_courses to find courses a department's students CAN ENROLL in.

    Args:
        department: Department name to search for (e.g., 資工系, 文學院, 管理學院)
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
            'error': f'按系所搜尋課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_search_selectable_courses(
    department: str,
    career: str = '學士班',
    limit: int = 20,
    include_other_dept: bool = True,
    semester: str | None = None
) -> str:
    """Search courses that students of a specific department and academic level CAN ENROLL in.

    This is different from nchu_course_search_by_department which only finds courses OFFERED by a department.
    This tool finds all courses that a department's students are eligible to enroll in, including:
    - Courses offered by the same department
    - Courses offered by OTHER departments but designated for this department's students

    Academic level rules:
    - 學士班 (Undergraduate): Can enroll in 學士班 + 碩士班 courses
    - 碩士班 (Master): Can enroll in 碩士班 + 博士班 courses (NOT undergraduate courses)
    - 博士班 (PhD): Can enroll in 博士班 courses only
    - 碩專班 (Executive Master): Can enroll in 碩專班 + 碩士班 + 博士班 courses

    Args:
        department: Department name keyword (e.g., "資工", "電機", "中文")
        career: Academic level - 學士班, 碩士班, 博士班, 碩專班, 進修學士班 (default: 學士班)
        limit: Maximum number of results to return (default: 20)
        include_other_dept: Include courses offered by other departments but selectable by this department (default: True)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing:
        - results: List of selectable courses with enrollment info
        - summary: Count of same-dept vs other-dept courses
        - search_params: Parameters used for the search including selectable career levels
    """
    try:
        results = searcher.search_selectable_courses(
            department=department,
            career=career,
            limit=limit,
            include_other_dept=include_other_dept,
            semester=semester
        )
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'搜尋可選課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_search_by_type(course_type: str, limit: int = 20, semester: str | None = None) -> str:
    """Search courses by course type (required/elective).

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
            'error': f'按課程類別搜尋時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_search_by_teacher(teacher_name: str, limit: int = 20, semester: str | None = None) -> str:
    """Search courses by teacher name.

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
            'error': f'按授課教師搜尋課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_search_by_time(weekday: str, period: str | None = None, limit: int = 20, semester: str | None = None) -> str:
    """Search courses by class time.

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
            'error': f'搜尋上課時間時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_get_stats(semester: str | None = None) -> str:
    """Get statistics about the course database.

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
def nchu_course_get_detail(course_id: str, include_syllabus: bool = True, semester: str | None = None) -> str:
    """Get detailed information about a specific course, including full syllabus.

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
            'error': f'獲取課程詳細資訊時發生錯誤: {str(e)}',
            'message': '無法獲取課程詳細資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_get_teacher_courses(teacher_name: str, exact_match: bool = False, limit: int = 50, semester: str | None = None) -> str:
    """Get all courses taught by a specific teacher.

    Args:
        teacher_name: Teacher name
        exact_match: Whether to use exact match (default: False)
        limit: Maximum number of results to return (default: 50)
        semester: Semester code. If not specified, uses the latest semester.

    Returns:
        JSON string containing teacher's courses
    """
    try:
        results = searcher.get_teacher_courses(
            teacher_name, exact_match, limit, semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取教師課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_get_teacher_history(teacher_name: str, limit_per_semester: int = 10) -> str:
    """Get a teacher's course history across all semesters.

    This searches all available semesters to find courses taught by the specified teacher.
    Note: This may be slow as it loads data from all semesters.

    Args:
        teacher_name: Teacher name to search for
        limit_per_semester: Maximum number of courses to show per semester (default: 10)

    Returns:
        JSON string containing teacher's course history grouped by semester
    """
    try:
        results = searcher.get_teacher_history(
            teacher_name, limit_per_semester)
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取教師歷年課程時發生錯誤: {str(e)}',
            'results': {},
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_get_all_teachers(semester: str | None = None) -> str:
    """Get all teachers and their course statistics.

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
def nchu_course_get_all_departments(semester: str | None = None) -> str:
    """Get all departments and their course counts.

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
def nchu_course_time_format_help() -> str:
    """Get help information about class time format codes.

    Returns:
        JSON string containing time format explanation
    """
    help_text = {
        "說明": "上課時間代碼格式為「星期+節次」，例如 334 = 星期三第3、4節",
        "星期對照": CourseSearcher.WEEKDAY_MAP,
        "節次對照": CourseSearcher.TIME_SLOTS,
        "範例": {
            "334": "星期三 第3節(10:10-11:00), 第4節(11:10-12:00)",
            "156": "星期一 第5節(13:10-14:00), 第6節(14:10-15:00)",
            "2AB": "星期二 第A節(18:30-19:20), 第B節(19:25-20:15)"
        }
    }
    return json.dumps(help_text, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_search_syllabus(
    keyword: str,
    limit: int = 10,
    include_syllabus_in_result: bool = False,
    semester: str | None = None
) -> str:
    """Search courses by syllabus content.

    This tool specifically searches within course syllabus fields including:
    - 課程簡述 (Course description)
    - 課程目標 (Course objectives)
    - 教學方法 (Teaching methods)
    - 評量方法 (Assessment methods)
    - 每週授課內容 (Weekly course content)
    - 教科書與參考書目 (Textbooks and references)
    - 核心能力與配比 (Core competencies and weightings)
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
            'error': f'搜尋課程大綱時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_course_search_by_teaching_method(method: str, limit: int = 20, semester: str | None = None) -> str:
    """Search courses by teaching method.

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
def nchu_course_search_by_assessment_method(method: str, limit: int = 20, semester: str | None = None) -> str:
    """Search courses by assessment/evaluation method.

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
def nchu_course_search_by_sdg(sdg_keyword: str, limit: int = 20, semester: str | None = None) -> str:
    """Search courses by UN Sustainable Development Goals (SDGs).

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
def nchu_course_get_weekly_content(course_id: str, semester: str | None = None) -> str:
    """Get weekly course content for a specific course.

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
            'message': f'找不到選課號碼為 {course_id} 的課程',
            'metadata': searcher._get_metadata(sem)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'error': f'獲取每週授課內容時發生錯誤: {str(e)}',
            'message': '無法獲取每週授課內容'
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
