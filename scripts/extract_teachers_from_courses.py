#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從課程資料中提取教師資訊

從現有的課程資料（data/courses/all_courses_syllabi/）中提取教師資訊，
作為系所網頁爬蟲的補充資料來源。

提取的資訊包括：
- 教師姓名
- 開課系所
- 授課科目
- 學期資訊
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# 將 project root 加入 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 路徑設定
COURSES_DIR = PROJECT_ROOT / "data" / "courses" / "all_courses_syllabi"
OUTPUT_FILE = PROJECT_ROOT / "data" / "teachers" / "teachers_from_courses.json"


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


def extract_teachers_from_courses(courses: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """從課程資料中提取教師資訊
    
    Args:
        courses: 課程資料列表
        
    Returns:
        Dict: 以教師姓名為 key 的教師資料字典
    """
    teachers: Dict[str, Dict[str, Any]] = {}
    
    for course in courses:
        basic_info = course.get("課程基本資訊", {})
        teacher_name = basic_info.get("授課教師", "").strip()
        
        if not teacher_name or teacher_name in ["", "未定", "待聘"]:
            continue
            
        teacher_names = []
        for sep in ["、", ",", "/"]:
            if sep in teacher_name:
                teacher_names = [t.strip() for t in teacher_name.split(sep)]
                break
                
        if not teacher_names:
            teacher_names = [teacher_name]
            
        # 提取學期
        semester = ""
        url = course.get("網址", "")
        if "v_strm=" in url:
            # e.g. https://onepiece.nchu.edu.tw/cofsys/plsql/Syllabus_main?v_strm=1141&v_class_nbr=3872
            parts = url.split("v_strm=")
            if len(parts) > 1:
                semester = parts[1].split("&")[0]
                
        if not semester:
            continue
            
        for name in teacher_names:
            if not name or len(name) > 20:
                continue
                
            if name not in teachers:
                teachers[name] = {
                    "name": name,
                    "departments": set(),
                    "courses": [],
                    "semesters": set(),
                    "course_count": 0,
                }
                
            dept = basic_info.get("開課系所", "")
            if dept:
                teachers[name]["departments"].add(dept)
                
            teachers[name]["semesters"].add(semester)
            teachers[name]["course_count"] += 1
            
            if len(teachers[name]["courses"]) < 20:
                course_info = {
                    "course_name": basic_info.get("課程名稱", ""),
                    "department": dept,
                    "semester": semester,
                    "semester_desc": semester_to_description(semester),
                }
                teachers[name]["courses"].append(course_info)
                
    return teachers

def finalize_teacher_data(teachers: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """最終處理教師資料"""
    result = []
    
    for name, data in teachers.items():
        departments = sorted(list(data["departments"]))
        semesters = sorted(list(data["semesters"]), reverse=True)
        
        dept_counts = defaultdict(int)
        for course in data["courses"]:
            dept = course.get("department", "")
            if dept:
                dept_counts[dept] += 1
                
        primary_department = ""
        if dept_counts:
            primary_department = max(dept_counts.keys(), key=lambda x: dept_counts[x])
            
        courses = sorted(data["courses"], key=lambda x: x["semester"], reverse=True)
        
        teacher_record = {
            "id": f"teacher_course_{hash(name) % 1000000:06d}",
            "name": name,
            "name_en": "",
            "title": "",
            "department": primary_department,
            "departments": departments,
            "college": "",
            "research_areas": [],
            "email": "",
            "phone": "",
            "semesters": semesters,
            "semesters_count": len(semesters),
            "course_count": data["course_count"],
            "courses": courses[:20],
            "source": "course_data",
        }
        result.append(teacher_record)
        
    result.sort(key=lambda x: x["course_count"], reverse=True)
    return result


def extract_all_teachers(
    limit_semesters: int = 0,
    output_file: Path = OUTPUT_FILE,
) -> Dict[str, Any]:
    print("=" * 60)
    print("從課程資料提取教師資訊")
    print("=" * 60)
    print(f"開始時間: {datetime.now().isoformat()}")
    print()

    courses_file = PROJECT_ROOT / "data" / "courses" / "all-courses-syllabi-processed.json"
    
    try:
        with open(courses_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            courses = data.get("courses", [])
    except Exception as e:
        print(f"讀取檔案失敗 {courses_file}: {e}")
        return {"success": False, "error": str(e)}
        
    print(f"找到 {len(courses)} 筆課程資料")
    
    all_teachers = extract_teachers_from_courses(courses)
    final_teachers = finalize_teacher_data(all_teachers)

    print()
    print(f"提取完成: 共 {len(final_teachers)} 位教師")

    # 統計資訊
    total_courses = sum(t["course_count"] for t in final_teachers)
    departments = set()
    for t in final_teachers:
        departments.update(t["departments"])

    print(f"涵蓋系所: {len(departments)} 個")
    print(f"課程總數: {total_courses}")

    # 儲存結果
    output_data = {
        "metadata": {
            "extracted_at": datetime.now().isoformat(),
            "semesters_processed": 1,
            "total_teachers": len(final_teachers),
            "total_courses": total_courses,
            "total_departments": len(departments),
            "source": "course_data",
        },
        "teachers": final_teachers,
    }

    # 確保輸出目錄存在
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n已儲存至: {output_file}")
    print(f"結束時間: {datetime.now().isoformat()}")

    return {
        "success": True,
        "output_path": str(output_file),
        "total_teachers": len(final_teachers),
        "total_courses": total_courses,
        "semesters_processed": 1,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="從課程資料提取教師資訊")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="只處理最近 N 個學期（預設：全部）",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="輸出檔案路徑",
    )

    args = parser.parse_args()

    output = Path(args.output) if args.output else OUTPUT_FILE

    result = extract_all_teachers(
        limit_semesters=args.limit,
        output_file=output,
    )

    if not result.get("success", False):
        print(f"\n錯誤: {result.get('error', '未知錯誤')}")
        sys.exit(1)
