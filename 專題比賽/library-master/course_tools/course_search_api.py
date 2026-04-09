#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides course search functionality for NCHU courses."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Any

from mcp.server.fastmcp import FastMCP


from pathlib import Path
import json

class CourseSearcher:
    def __init__(self, json_file_path="data/courses/all-courses-syllabi-complete.json"):
        """
        初始化課程搜尋器
        
        Args:
            json_file_path: JSON 檔案路徑
        """
        self.json_file_path = json_file_path
        self.courses_data = None
        self.courses = []
        self.metadata = {}
        self.load_data()
    
    def load_data(self):
        """載入課程資料"""
        try:
            # 使用 parent_dir，讀取上一層資料夾底下的 data
            parent_dir = Path(__file__).parent.parent
            json_path = parent_dir / self.json_file_path
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.courses_data = data
            self.courses = data.get('courses', [])
            self.metadata = {
                'timestamp': data.get('timestamp'),
                'semester': data.get('semester'),
                'description': data.get('description'),
                'stats': data.get('stats')
            }
            
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {json_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 格式錯誤: {e}")
        except Exception as e:
            raise RuntimeError(f"載入資料失敗: {e}")
    
    def search_courses(self, 
                      keyword, 
                      limit=10,
                      search_fields=None,
                      case_sensitive=False):
        """
        搜尋課程
        
        Args:
            keyword: 搜尋關鍵字
            limit: 回傳結果數量限制
            search_fields: 要搜尋的欄位列表
            case_sensitive: 是否區分大小寫
        
        Returns:
            搜尋結果字典
        """
        if search_fields is None:
            search_fields = ['課程名稱', '課程簡述', '每週授課內容', '開課系所', '授課教師']
        
        if not keyword.strip():
            return {
                'results': [],
                'total': 0,
                'message': '請提供搜尋關鍵字'
            }
        
        search_term = keyword if case_sensitive else keyword.lower()
        matching_courses = []
        
        for course in self.courses:
            match_info = self._search_in_course(
                course, search_term, search_fields, case_sensitive
            )
            
            if match_info['is_match']:
                matching_courses.append({
                    'course': self._format_course_result(course),
                    'relevance_score': match_info['score'],
                    'matched_fields': match_info['matched_fields'],
                    'matched_content': match_info['matched_content']
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
            'showing': len(limited_results),
            'metadata': {
                'semester': self.metadata.get('semester'),
                'timestamp': self.metadata.get('timestamp')
            }
        }
    
    def _search_in_course(self, course, search_term, 
                         search_fields, case_sensitive):
        """在單一課程中搜尋"""
        score = 0
        matched_fields = []
        matched_content = {}
        
        # 搜尋課程基本資訊
        basic_info = course.get('課程基本資訊', {})
        
        if '課程名稱' in search_fields:
            course_name = basic_info.get('課程名稱', '')
            match = self._check_match(course_name, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 3  # 課程名稱權重較高
                matched_fields.append('課程名稱')
                matched_content['課程名稱'] = course_name
        
        if '開課系所' in search_fields:
            department = basic_info.get('開課系所', '')
            match = self._check_match(department, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 2
                matched_fields.append('開課系所')
                matched_content['開課系所'] = department
        
        if '授課教師' in search_fields:
            teacher = basic_info.get('授課教師', '')
            match = self._check_match(teacher, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 2.5  # 授課教師權重較高
                matched_fields.append('授課教師')
                matched_content['授課教師'] = teacher
        
        # 搜尋課程大綱
        outline = course.get('課程大綱', {})
        
        if '課程簡述' in search_fields:
            description = outline.get('課程簡述', '')
            match = self._check_match(description, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 2
                matched_fields.append('課程簡述')
                matched_content['課程簡述'] = self._highlight_matches(
                    description, search_term, case_sensitive
                )
        
        # 搜尋每週授課內容
        if '每週授課內容' in search_fields:
            weekly_content = outline.get('每週授課內容', {})
            weekly_matches = 0
            max_weekly_matches = 3  # 限制最多顯示3週的內容
            
            for week, content in weekly_content.items():
                if weekly_matches >= max_weekly_matches:
                    break
                    
                match = self._check_match(content, search_term, case_sensitive)
                if match['is_match']:
                    score += match['score']
                    if '每週授課內容' not in matched_fields:
                        matched_fields.append('每週授課內容')
                        matched_content['每週授課內容'] = {}
                    matched_content['每週授課內容'][week] = self._highlight_matches(
                        content, search_term, case_sensitive
                    )
                    weekly_matches += 1
        
        return {
            'is_match': score > 0,
            'score': score,
            'matched_fields': matched_fields,
            'matched_content': matched_content
        }
    
    def _check_match(self, text, search_term, case_sensitive):
        """檢查文字匹配"""
        if not text or not search_term:
            return {'is_match': False, 'score': 0}
        
        text_to_search = text if case_sensitive else text.lower()
        
        if search_term in text_to_search:
            # 計算相關度分數
            match_ratio = len(search_term) / len(text_to_search)
            score = min(match_ratio * 10, 5) + 1
            return {'is_match': True, 'score': score}
        
        return {'is_match': False, 'score': 0}
    
    def _highlight_matches(self, text, search_term, case_sensitive, max_length=200):
        """高亮匹配內容"""
        if not text or not search_term:
            return text
        
        # 限制文字長度
        if len(text) > max_length:
            # 找到搜尋詞的位置
            search_pos = text.lower().find(search_term.lower()) if not case_sensitive else text.find(search_term)
            if search_pos != -1:
                # 以搜尋詞為中心截取文字
                start = max(0, search_pos - max_length // 3)
                end = min(len(text), start + max_length)
                text = text[start:end]
                if start > 0:
                    text = "..." + text
                if end < len(text):
                    text = text + "..."
        
        if case_sensitive:
            return text.replace(search_term, f"**{search_term}**")
        else:
            # 不區分大小寫的替換
            pattern = re.compile(re.escape(search_term), re.IGNORECASE)
            return pattern.sub(f"**{search_term}**", text)
    
    def _format_course_result(self, course, include_details=False):
        """格式化課程結果"""
        basic_info = course.get('課程基本資訊', {})
        outline = course.get('課程大綱', {})
        
        # 基本資訊（精簡版）
        result = {
            '網址': course.get('網址', ''),
            '課程名稱': basic_info.get('課程名稱', ''),
            '授課教師': basic_info.get('授課教師', ''),
            '開課系所': basic_info.get('開課系所', ''),
            '課程類別': basic_info.get('課程類別', '')
        }
        
        # 如果需要詳細資訊才包含更多欄位
        if include_details:
            result.update({
                '流水號': course.get('流水號'),
                '選課單位': basic_info.get('選課單位', ''),
                '課程簡述': outline.get('課程簡述', ''),
                '序號': course.get('序號'),
                '更新時間': course.get('更新時間', '')
            })
        
        return result
    
    def search_by_department(self, department, limit=20):
        """按系所搜尋課程"""
        return self.search_courses(
            department, 
            limit=limit, 
            search_fields=['開課系所']
        )
    
    def search_by_course_type(self, course_type, limit=20):
        """按課程類別搜尋（必修/選修）"""
        matching_courses = []
        
        for course in self.courses:
            basic_info = course.get('課程基本資訊', {})
            course_category = basic_info.get('課程類別', '')
            
            if course_type in course_category:
                matching_courses.append({
                    'course': self._format_course_result(course),
                    'relevance_score': 5,
                    'matched_fields': ['課程類別'],
                    'matched_content': {'課程類別': course_category}
                })
        
        return {
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'keyword': course_type,
            'metadata': self.metadata
        }
    
    def search_by_teacher(self, teacher_name, limit=20):
        """按授課教師搜尋課程"""
        return self.search_courses(
            teacher_name,
            limit=limit,
            search_fields=['授課教師']
        )
    
    def get_teacher_courses(self, teacher_name, exact_match=False, limit=50):
        """
        獲取特定老師的所有課程
        
        Args:
            teacher_name: 教師姓名
            exact_match: 是否精確匹配（完全相同）
            limit: 回傳結果數量限制
        
        Returns:
            該教師的課程列表
        """
        matching_courses = []
        
        for course in self.courses:
            basic_info = course.get('課程基本資訊', {})
            teacher = basic_info.get('授課教師', '')
            
            is_match = False
            if exact_match:
                is_match = teacher == teacher_name
            else:
                is_match = teacher_name in teacher
            
            if is_match:
                matching_courses.append({
                    'course': self._format_course_result(course),
                    'relevance_score': 10 if exact_match else 8,
                    'matched_fields': ['授課教師'],
                    'matched_content': {'授課教師': teacher}
                })
        
        return {
            'results': matching_courses[:limit],
            'total': len(matching_courses),
            'teacher': teacher_name,
            'exact_match': exact_match,
            'metadata': self.metadata
        }
    
    def get_all_teachers(self):
        """
        獲取所有授課教師列表及其開課數量
        
        Returns:
            教師統計資訊
        """
        teacher_stats = {}
        teacher_courses = {}
        
        for course in self.courses:
            basic_info = course.get('課程基本資訊', {})
            teacher = basic_info.get('授課教師', '').strip()
            
            if teacher and teacher != '':
                if teacher not in teacher_stats:
                    teacher_stats[teacher] = 0
                    teacher_courses[teacher] = []
                
                teacher_stats[teacher] += 1
                teacher_courses[teacher].append({
                    '課程名稱': basic_info.get('課程名稱', ''),
                    '開課系所': basic_info.get('開課系所', ''),
                    '課程類別': basic_info.get('課程類別', ''),
                    '網址': course.get('網址', '')
                })
        
        # 按開課數量排序
        sorted_teachers = sorted(teacher_stats.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_teachers': len(teacher_stats),
            'teacher_stats': dict(sorted_teachers),
            'teacher_courses': teacher_courses,
            'metadata': self.metadata
        }
    
    def get_stats(self):
        """獲取統計資訊"""
        if not self.courses:
            return {'message': '課程資料未載入'}
        
        stats = {
            '總課程數': len(self.courses),
            '系所統計': {},
            '課程類別統計': {},
            '教師統計': {},
            'metadata': self.metadata
        }
        
        # 統計系所分布
        for course in self.courses:
            dept = course.get('課程基本資訊', {}).get('開課系所', '未知')
            stats['系所統計'][dept] = stats['系所統計'].get(dept, 0) + 1
        
        # 統計課程類別分布
        for course in self.courses:
            course_type = course.get('課程基本資訊', {}).get('課程類別', '未知')
            stats['課程類別統計'][course_type] = stats['課程類別統計'].get(course_type, 0) + 1
        
        # 統計教師分布
        for course in self.courses:
            teacher = course.get('課程基本資訊', {}).get('授課教師', '未知').strip()
            if teacher and teacher != '':
                stats['教師統計'][teacher] = stats['教師統計'].get(teacher, 0) + 1
        
        # 取前10名開課最多的教師
        top_teachers = sorted(stats['教師統計'].items(), key=lambda x: x[1], reverse=True)[:10]
        stats['開課最多教師前10名'] = dict(top_teachers)
        
        return stats


# 初始化全域搜尋器
searcher = CourseSearcher()

mcp = FastMCP("nchu_course_search")


@mcp.tool()
def course_search_by_keyword(keyword: str, limit: int = 10, search_fields: str | None = None, case_sensitive: bool = False, include_details: bool = False) -> str:
    """Search for courses in NCHU course database.
    
    Args:
        keyword: Search keyword
        limit: Maximum number of results to return (default: 10)
        search_fields: Comma-separated fields to search in (default: 課程名稱,課程簡述,每週授課內容,開課系所,授課教師)
        case_sensitive: Whether search is case sensitive (default: False)
        include_details: Whether to include detailed course information (default: False)
    
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
            case_sensitive=case_sensitive
        )
        
        # 如果不需要詳細資訊，簡化結果
        if not include_details and 'results' in results:
            for result in results['results']:
                if 'course' in result:
                    result['course'] = searcher._format_course_result(
                        {'課程基本資訊': result['course'], '課程大綱': {}}, 
                        include_details=False
                    )
                # 簡化匹配內容
                if 'matched_content' in result:
                    simplified_content = {}
                    for field, content in result['matched_content'].items():
                        if field == '每週授課內容' and isinstance(content, dict):
                            # 只保留前2週的內容
                            simplified_content[field] = dict(list(content.items())[:2])
                        else:
                            simplified_content[field] = content
                    result['matched_content'] = simplified_content
        
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'搜尋課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def course_search_by_department(department: str, limit: int = 20) -> str:
    """Search courses by department.
    
    Args:
        department: Department name to search for
        limit: Maximum number of results to return (default: 20)
    
    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_department(department, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'按系所搜尋課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def course_search_by_type(course_type: str, limit: int = 20) -> str:
    """Search courses by course type (required/elective).
    
    Args:
        course_type: Course type to search for (e.g., 必修, 選修)
        limit: Maximum number of results to return (default: 20)
    
    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_course_type(course_type, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'按課程類別搜尋時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def course_get_stats() -> str:
    """Get statistics about the course database.
    
    Returns:
        JSON string containing database statistics
    """
    try:
        stats = searcher.get_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取統計資訊時發生錯誤: {str(e)}',
            'message': '無法獲取統計資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def course_get_detail(course_id: str) -> str:
    """Get detailed information about a specific course.
    
    Args:
        course_id: Course ID (序號 or 流水號)
    
    Returns:
        JSON string containing detailed course information
    """
    try:
        for course in searcher.courses:
            if course.get('序號') == course_id or course.get('流水號') == course_id:
                return json.dumps(course, ensure_ascii=False, indent=2)
        
        return json.dumps({
            'error': f'找不到課程ID: {course_id}',
            'message': '請確認課程ID是否正確'
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取課程詳細資訊時發生錯誤: {str(e)}',
            'message': '無法獲取課程詳細資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def course_search_by_teacher(teacher_name: str, limit: int = 20) -> str:
    """Search courses by teacher name.
    
    Args:
        teacher_name: Teacher name to search for
        limit: Maximum number of results to return (default: 20)
    
    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_teacher(teacher_name, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'按授課教師搜尋課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def course_get_teacher_courses(teacher_name: str, exact_match: bool = False, limit: int = 50) -> str:
    """Get all courses taught by a specific teacher.
    
    Args:
        teacher_name: Teacher name
        exact_match: Whether to use exact match (default: False)
        limit: Maximum number of results to return (default: 50)
    
    Returns:
        JSON string containing teacher's courses
    """
    try:
        results = searcher.get_teacher_courses(teacher_name, exact_match, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取教師課程時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def course_get_all_teachers() -> str:
    """Get all teachers and their course statistics.
    
    Returns:
        JSON string containing all teachers and their course counts
    """
    try:
        results = searcher.get_all_teachers()
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取教師列表時發生錯誤: {str(e)}',
            'message': '無法獲取教師列表'
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
