#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統一教師資料格式轉換程式

合併來自不同來源的教師資料：
1. 系所網頁爬取資料 (teachers_scraped_latest.json)
2. 課程系統提取資料 (teachers_from_courses.json)

功能：
- 合併資料
- 去重和正規化
- 建立索引（by_name, by_department, by_college, by_research_area）
- 輸出統一格式

輸出: data/teachers/teachers_all.json
"""

import json
import hashlib
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

# 將 project root 加入 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 路徑設定
DATA_DIR = PROJECT_ROOT / "data" / "teachers"
SCRAPED_FILE = DATA_DIR / "raw" / "teachers_scraped_latest.json"
COURSES_FILE = DATA_DIR / "teachers_from_courses.json"
ORCID_FILE = DATA_DIR / "orcid_data.json"
GRB_FILE = DATA_DIR / "grb_nchu_projects.json"
MOA_FILE = DATA_DIR / "moa_nchu_projects.json"
IR_FILE = DATA_DIR / "nchu_ir_data.json"
OUTPUT_FILE = DATA_DIR / "teachers_all.json"

# 學院對照表（系所 -> 學院）
DEPARTMENT_TO_COLLEGE = {
    # 文學院
    "中國文學系": "文學院",
    "中文系": "文學院",
    "外國語文學系": "文學院",
    "外文系": "文學院",
    "歷史學系": "文學院",
    "歷史系": "文學院",
    "台灣文學與跨國文化研究所": "文學院",
    "圖書資訊學研究所": "文學院",
    "台灣人文創新學士學位學程": "文學院",

    # 農資學院
    "農藝學系": "農業暨自然資源學院",
    "農藝系": "農業暨自然資源學院",
    "園藝學系": "農業暨自然資源學院",
    "園藝系": "農業暨自然資源學院",
    "森林學系": "農業暨自然資源學院",
    "森林系": "農業暨自然資源學院",
    "應用經濟學系": "農業暨自然資源學院",
    "應經系": "農業暨自然資源學院",
    "植物病理學系": "農業暨自然資源學院",
    "植病系": "農業暨自然資源學院",
    "昆蟲學系": "農業暨自然資源學院",
    "昆蟲系": "農業暨自然資源學院",
    "動物科學系": "農業暨自然資源學院",
    "動科系": "農業暨自然資源學院",
    "土壤環境科學系": "農業暨自然資源學院",
    "土環系": "農業暨自然資源學院",
    "水土保持學系": "農業暨自然資源學院",
    "水保系": "農業暨自然資源學院",
    "食品暨應用生物科技學系": "農業暨自然資源學院",
    "食生系": "農業暨自然資源學院",
    "生物產業機電工程學系": "農業暨自然資源學院",
    "生機系": "農業暨自然資源學院",
    "生物產業管理研究所": "農業暨自然資源學院",
    "景觀與遊憩學士學位學程": "農業暨自然資源學院",

    # 理學院
    "化學系": "理學院",
    "應用數學系": "理學院",
    "應數系": "理學院",
    "物理學系": "理學院",
    "物理系": "理學院",
    "資訊科學與工程學系": "理學院",
    "奈米科學研究所": "理學院",
    "統計學研究所": "理學院",
    "基因體暨生物資訊學研究所": "理學院",

    # 工學院
    "土木工程學系": "工學院",
    "土木系": "工學院",
    "機械工程學系": "工學院",
    "機械系": "工學院",
    "環境工程學系": "工學院",
    "環工系": "工學院",
    "化學工程學系": "工學院",
    "化工系": "工學院",
    "材料科學與工程學系": "工學院",
    "材料系": "工學院",
    "精密工程研究所": "工學院",
    "生醫工程研究所": "工學院",

    # 生科院
    "生命科學系": "生命科學院",
    "生科系": "生命科學院",
    "分子生物學研究所": "生命科學院",
    "生物化學研究所": "生命科學院",
    "生物科技學研究所": "生命科學院",
    "生物醫學研究所": "生命科學院",

    # 獸醫學院
    "獸醫學系": "獸醫學院",
    "獸醫系": "獸醫學院",
    "微生物暨公共衛生學研究所": "獸醫學院",
    "獸醫病理生物學研究所": "獸醫學院",

    # 管理學院
    "財務金融學系": "管理學院",
    "財金系": "管理學院",
    "企業管理學系": "管理學院",
    "企管系": "管理學院",
    "行銷學系": "管理學院",
    "資訊管理學系": "管理學院",
    "資管系": "管理學院",
    "會計學系": "管理學院",
    "會計系": "管理學院",
    "科技管理研究所": "管理學院",
    "運動與健康管理研究所": "管理學院",

    # 法政學院
    "法律學系": "法政學院",
    "法律系": "法政學院",
    "國際政治研究所": "法政學院",
    "國家政策與公共事務研究所": "法政學院",
    "教師專業發展研究所": "法政學院",

    # 電資學院
    "電機工程學系": "電機資訊學院",
    "電機系": "電機資訊學院",
    "資訊工程學系": "電機資訊學院",
    "資工系": "電機資訊學院",
    "通訊工程研究所": "電機資訊學院",
    "光電工程研究所": "電機資訊學院",
    "電機資訊學院學士班": "電機資訊學院",

    # 醫學院
    "學士後醫學系": "醫學院",

    # 循環經濟學院
    "循環經濟研究學院": "循環經濟研究學院",

    # 其他
    "通識教育中心": "共同教育委員會",
    "語言中心": "共同教育委員會",
    "體育室": "共同教育委員會",
    "師資培育中心": "共同教育委員會",
}


def normalize_department_name(dept: str) -> str:
    """正規化系所名稱

    Args:
        dept: 原始系所名稱

    Returns:
        str: 正規化後的系所名稱
    """
    if not dept:
        return ""

    # 移除常見後綴
    dept = dept.strip()
    dept = re.sub(r"（.*?）$", "", dept)
    dept = re.sub(r"\(.*?\)$", "", dept)

    return dept.strip()


def get_college_for_department(dept: str) -> str:
    """取得系所對應的學院

    Args:
        dept: 系所名稱

    Returns:
        str: 學院名稱
    """
    if not dept:
        return ""

    # 直接查表
    if dept in DEPARTMENT_TO_COLLEGE:
        return DEPARTMENT_TO_COLLEGE[dept]

    # 嘗試部分匹配
    for key, college in DEPARTMENT_TO_COLLEGE.items():
        if key in dept or dept in key:
            return college

    # 根據名稱推斷
    if "文學" in dept or "中文" in dept or "歷史" in dept or "外文" in dept:
        return "文學院"
    elif "農" in dept or "園藝" in dept or "森林" in dept or "食品" in dept:
        return "農業暨自然資源學院"
    elif "化學" in dept or "物理" in dept or "數學" in dept:
        return "理學院"
    elif "土木" in dept or "機械" in dept or "環境" in dept or "化工" in dept or "材料" in dept:
        return "工學院"
    elif "生命" in dept or "生物" in dept or "分子" in dept:
        return "生命科學院"
    elif "獸醫" in dept:
        return "獸醫學院"
    elif "財金" in dept or "企管" in dept or "管理" in dept or "會計" in dept or "資管" in dept or "行銷" in dept:
        return "管理學院"
    elif "法律" in dept or "政治" in dept or "政策" in dept:
        return "法政學院"
    elif "電機" in dept or "資訊" in dept or "資工" in dept or "通訊" in dept or "光電" in dept:
        return "電機資訊學院"
    elif "醫" in dept:
        return "醫學院"

    return ""


def generate_teacher_id(name: str, department: str) -> str:
    """生成教師唯一識別碼

    Args:
        name: 教師姓名
        department: 系所名稱

    Returns:
        str: 唯一識別碼
    """
    raw = f"{name}_{department}"
    return f"teacher_{hashlib.md5(raw.encode()).hexdigest()[:12]}"


def load_scraped_data() -> List[Dict[str, Any]]:
    """載入系所網頁爬取資料

    Returns:
        List[Dict]: 教師資料列表
    """
    if not SCRAPED_FILE.exists():
        print(f"找不到爬取資料檔案: {SCRAPED_FILE}")
        return []

    try:
        with open(SCRAPED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("teachers", [])
    except Exception as e:
        print(f"讀取爬取資料失敗: {e}")
        return []


def load_course_data() -> List[Dict[str, Any]]:
    """載入課程系統提取資料

    Returns:
        List[Dict]: 教師資料列表
    """
    if not COURSES_FILE.exists():
        print(f"找不到課程資料檔案: {COURSES_FILE}")
        return []

    try:
        with open(COURSES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("teachers", [])
    except Exception as e:
        print(f"讀取課程資料失敗: {e}")
        return []


def load_orcid_data() -> Dict[str, Dict[str, Any]]:
    """載入 ORCID 資料

    Returns:
        Dict: 以中文姓名為 key 的 ORCID 資料字典
    """
    if not ORCID_FILE.exists():
        print(f"找不到 ORCID 資料檔案: {ORCID_FILE}")
        return {}

    try:
        with open(ORCID_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 建立中文姓名索引
        orcid_by_name: Dict[str, Dict[str, Any]] = {}

        for researcher in data.get("researchers", []):
            # 使用中文名作為 key
            chinese_name = researcher.get("chinese_name", "")
            if chinese_name:
                orcid_by_name[chinese_name] = researcher

            # 也用其他名字建立索引
            for other_name in researcher.get("other_names", []):
                # 檢查是否為中文名
                if 2 <= len(other_name) <= 4 and all("\u4e00" <= c <= "\u9fff" for c in other_name):
                    if other_name not in orcid_by_name:
                        orcid_by_name[other_name] = researcher

        return orcid_by_name

    except Exception as e:
        print(f"讀取 ORCID 資料失敗: {e}")
        return {}


def load_grb_data() -> Dict[str, Dict[str, Any]]:
    """載入 GRB 研究計畫資料

    Returns:
        Dict: 以計畫主持人姓名為 key 的 GRB 資料字典
    """
    if not GRB_FILE.exists():
        print(f"找不到 GRB 資料檔案: {GRB_FILE}")
        return {}

    try:
        with open(GRB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # by_pi 已經是以主持人姓名為 key 的字典
        return data.get("by_pi", {})

    except Exception as e:
        print(f"讀取 GRB 資料失敗: {e}")
        return {}


def load_moa_data() -> Dict[str, Dict[str, Any]]:
    """載入農業部科技計畫資料

    Returns:
        Dict: 以計畫主持人姓名為 key 的農業部資料字典
    """
    if not MOA_FILE.exists():
        print(f"找不到農業部資料檔案: {MOA_FILE}")
        return {}

    try:
        with open(MOA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # by_pi 已經是以主持人姓名為 key 的字典
        return data.get("by_pi", {})

    except Exception as e:
        print(f"讀取農業部資料失敗: {e}")
        return {}


def load_ir_data() -> Dict[str, Dict[str, Any]]:
    """載入中興大學機構典藏資料

    Returns:
        Dict: 以作者姓名為 key 的 IR 資料字典
    """
    if not IR_FILE.exists():
        print(f"找不到機構典藏資料檔案: {IR_FILE}")
        return {}

    try:
        with open(IR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # authors 已經是以作者姓名為 key 的字典
        return data.get("authors", {})

    except Exception as e:
        print(f"讀取機構典藏資料失敗: {e}")
        return {}


def merge_teacher_records(
    scraped: Optional[Dict[str, Any]],
    course: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """合併兩個教師記錄

    以爬取資料為主，課程資料為輔

    Args:
        scraped: 爬取的教師資料
        course: 課程系統的教師資料

    Returns:
        Dict: 合併後的教師資料
    """
    if scraped is None and course is None:
        return {}

    if scraped is None:
        return course.copy()

    if course is None:
        return scraped.copy()

    # 以爬取資料為基礎
    merged = scraped.copy()

    # 補充課程資料中的資訊
    if not merged.get("department") and course.get("department"):
        merged["department"] = course["department"]

    if not merged.get("college") and course.get("college"):
        merged["college"] = course["college"]

    # 合併課程資訊
    if course.get("courses"):
        if "courses" not in merged:
            merged["courses"] = []
        existing = {(c.get("course_name"), c.get("semester")) for c in merged.get("courses", [])}
        for c in course.get("courses", []):
            key = (c.get("course_name"), c.get("semester"))
            if key not in existing:
                merged["courses"].append(c)

    # 合併學期資訊
    if course.get("semesters"):
        if "semesters" not in merged:
            merged["semesters"] = []
        merged["semesters"] = list(set(merged.get("semesters", []) + course.get("semesters", [])))
        merged["semesters"].sort(reverse=True)

    # 更新課程數
    merged["course_count"] = course.get("course_count", 0)

    return merged


def unify_teachers() -> Dict[str, Any]:
    """統一教師資料

    Returns:
        Dict: 處理結果摘要
    """
    print("=" * 60)
    print("統一教師資料")
    print("=" * 60)
    print(f"開始時間: {datetime.now().isoformat()}")
    print()

    # 載入資料
    scraped_teachers = load_scraped_data()
    course_teachers = load_course_data()
    orcid_by_name = load_orcid_data()
    grb_by_pi = load_grb_data()
    moa_by_pi = load_moa_data()
    ir_by_author = load_ir_data()

    print(f"爬取資料: {len(scraped_teachers)} 筆")
    print(f"課程資料: {len(course_teachers)} 筆")
    print(f"ORCID 資料: {len(orcid_by_name)} 筆（有中文名）")
    print(f"GRB 資料: {len(grb_by_pi)} 位計畫主持人")
    print(f"農業部資料: {len(moa_by_pi)} 位計畫主持人")
    print(f"機構典藏資料: {len(ir_by_author)} 位作者")

    # 建立索引（以姓名為 key）
    scraped_by_name: Dict[str, List[Dict]] = defaultdict(list)
    for teacher in scraped_teachers:
        name = teacher.get("name", "").strip()
        if name:
            scraped_by_name[name].append(teacher)

    course_by_name: Dict[str, Dict] = {}
    for teacher in course_teachers:
        name = teacher.get("name", "").strip()
        if name:
            course_by_name[name] = teacher

    # 合併資料
    all_teachers: Dict[str, Dict[str, Any]] = {}

    # 處理爬取資料
    for name, records in scraped_by_name.items():
        for record in records:
            dept = record.get("department", "")
            key = f"{name}_{dept}"

            course_record = course_by_name.get(name)
            merged = merge_teacher_records(record, course_record)

            if key not in all_teachers:
                all_teachers[key] = merged

    # 處理課程資料中未出現在爬取資料的教師
    for name, record in course_by_name.items():
        if name not in scraped_by_name:
            dept = record.get("department", "")
            key = f"{name}_{dept}"
            if key not in all_teachers:
                all_teachers[key] = record

    print(f"合併後: {len(all_teachers)} 筆")

    # 正規化和補充資料
    final_teachers = []
    for key, teacher in all_teachers.items():
        # 正規化系所名稱
        dept = normalize_department_name(teacher.get("department", ""))
        teacher["department"] = dept

        # 補充學院資訊
        if not teacher.get("college"):
            teacher["college"] = get_college_for_department(dept)

        # 生成 ID
        teacher["id"] = generate_teacher_id(
            teacher.get("name", ""),
            teacher.get("department", "")
        )

        # 確保必要欄位存在
        teacher.setdefault("name_en", "")
        teacher.setdefault("title", "")
        teacher.setdefault("research_areas", [])
        teacher.setdefault("email", "")
        teacher.setdefault("phone", "")
        teacher.setdefault("office", "")
        teacher.setdefault("personal_url", "")
        teacher.setdefault("photo_url", "")
        teacher.setdefault("education", [])
        teacher.setdefault("experience", [])
        teacher.setdefault("courses", [])
        teacher.setdefault("semesters", [])
        teacher.setdefault("course_count", 0)
        teacher.setdefault("orcid_id", "")

        # 嘗試從 ORCID 補充資料
        teacher_name = teacher.get("name", "")
        if teacher_name and teacher_name in orcid_by_name:
            orcid_data = orcid_by_name[teacher_name]

            # 補充英文名
            if not teacher.get("name_en") and orcid_data.get("name_en"):
                teacher["name_en"] = orcid_data["name_en"]

            # 補充 ORCID ID
            if orcid_data.get("orcid_id"):
                teacher["orcid_id"] = orcid_data["orcid_id"]
                teacher["orcid_url"] = orcid_data.get("orcid_url", "")

            # 補充研究專長（從 keywords）
            if not teacher.get("research_areas") and orcid_data.get("keywords"):
                teacher["research_areas"] = orcid_data["keywords"]

            # 從 ORCID 職位補充職稱
            if not teacher.get("title") and orcid_data.get("nchu_positions"):
                for pos in orcid_data["nchu_positions"]:
                    role = pos.get("role", "")
                    if role:
                        teacher["title"] = role
                        break

        # 嘗試從 GRB 研究計畫補充資料
        if teacher_name and teacher_name in grb_by_pi:
            grb_data = grb_by_pi[teacher_name]

            # 補充研究專長（從 GRB 關鍵詞和研究領域）
            existing_areas = set(teacher.get("research_areas", []))

            # 從 GRB 關鍵詞補充
            for keyword in grb_data.get("keywords", []):
                if keyword and keyword not in existing_areas:
                    existing_areas.add(keyword)

            # 從研究領域補充
            for field in grb_data.get("fields", []):
                if field and field not in existing_areas:
                    existing_areas.add(field)

            teacher["research_areas"] = list(existing_areas)

            # 新增 GRB 計畫相關資訊
            teacher["grb_project_count"] = grb_data.get("project_count", 0)
            teacher["grb_years"] = grb_data.get("years", [])

        # 嘗試從農業部科技計畫補充資料
        if teacher_name and teacher_name in moa_by_pi:
            moa_data = moa_by_pi[teacher_name]

            # 補充研究專長（從農業部研究領域）
            existing_areas = set(teacher.get("research_areas", []))

            # 從研究領域補充
            for field in moa_data.get("fields", []):
                if field and field not in existing_areas:
                    existing_areas.add(field)

            teacher["research_areas"] = list(existing_areas)

            # 新增農業部計畫相關資訊
            teacher["moa_project_count"] = moa_data.get("project_count", 0)
            teacher["moa_years"] = moa_data.get("years", [])
            teacher["moa_total_budget"] = moa_data.get("total_budget", 0)

        # 嘗試從機構典藏補充研究主題
        if teacher_name and teacher_name in ir_by_author:
            ir_data = ir_by_author[teacher_name]

            # 補充研究專長（從 IR 主題標籤）
            existing_areas = set(teacher.get("research_areas", []))

            # 從主題標籤補充（限制數量避免過多）
            ir_subjects = ir_data.get("subjects", [])
            added_count = 0
            for subject in ir_subjects:
                if subject and subject not in existing_areas:
                    # 過濾太短或太長的主題
                    if 2 <= len(subject) <= 50:
                        existing_areas.add(subject)
                        added_count += 1
                        # 限制最多新增 20 個主題
                        if added_count >= 20:
                            break

            teacher["research_areas"] = list(existing_areas)

            # 新增機構典藏相關資訊
            teacher["ir_publication_count"] = ir_data.get("publication_count", 0)
            teacher["ir_subject_count"] = len(ir_subjects)

        final_teachers.append(teacher)

    # 排序（按學院、系所、姓名）
    final_teachers.sort(key=lambda x: (
        x.get("college", ""),
        x.get("department", ""),
        x.get("name", ""),
    ))

    print(f"最終教師數: {len(final_teachers)}")

    # 建立索引
    indexes = build_indexes(final_teachers)

    # 統計資訊
    colleges = set(t.get("college", "") for t in final_teachers if t.get("college"))
    departments = set(t.get("department", "") for t in final_teachers if t.get("department"))
    with_orcid = sum(1 for t in final_teachers if t.get("orcid_id"))
    with_research_areas = sum(1 for t in final_teachers if t.get("research_areas"))
    with_grb = sum(1 for t in final_teachers if t.get("grb_project_count", 0) > 0)
    with_moa = sum(1 for t in final_teachers if t.get("moa_project_count", 0) > 0)
    with_ir = sum(1 for t in final_teachers if t.get("ir_publication_count", 0) > 0)

    print(f"涵蓋學院: {len(colleges)} 個")
    print(f"涵蓋系所: {len(departments)} 個")
    print(f"有 ORCID: {with_orcid} 人")
    print(f"有 GRB 計畫: {with_grb} 人")
    print(f"有農業部計畫: {with_moa} 人")
    print(f"有機構典藏: {with_ir} 人")
    print(f"有研究專長: {with_research_areas} 人")

    # 儲存結果
    output_data = {
        "metadata": {
            "unified_at": datetime.now().isoformat(),
            "total_teachers": len(final_teachers),
            "total_colleges": len(colleges),
            "total_departments": len(departments),
            "with_orcid": with_orcid,
            "with_grb": with_grb,
            "with_moa": with_moa,
            "with_ir": with_ir,
            "with_research_areas": with_research_areas,
            "sources": {
                "scraped": len(scraped_teachers),
                "courses": len(course_teachers),
                "orcid": len(orcid_by_name),
                "grb": len(grb_by_pi),
                "moa": len(moa_by_pi),
                "ir": len(ir_by_author),
            },
        },
        "indexes": indexes,
        "teachers": final_teachers,
    }

    # 確保輸出目錄存在
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n已儲存至: {OUTPUT_FILE}")
    print(f"結束時間: {datetime.now().isoformat()}")

    return {
        "success": True,
        "output_path": str(OUTPUT_FILE),
        "total_teachers": len(final_teachers),
        "total_colleges": len(colleges),
        "total_departments": len(departments),
    }


def build_indexes(teachers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """建立教師資料索引

    Args:
        teachers: 教師資料列表

    Returns:
        Dict: 索引資料
    """
    by_college: Dict[str, List[str]] = defaultdict(list)
    by_department: Dict[str, List[str]] = defaultdict(list)
    by_research_area: Dict[str, List[str]] = defaultdict(list)

    for teacher in teachers:
        teacher_id = teacher.get("id", "")

        # 學院索引
        college = teacher.get("college", "")
        if college:
            by_college[college].append(teacher_id)

        # 系所索引
        dept = teacher.get("department", "")
        if dept:
            by_department[dept].append(teacher_id)

        # 研究專長索引
        for area in teacher.get("research_areas", []):
            if area:
                by_research_area[area].append(teacher_id)

    return {
        "by_college": dict(by_college),
        "by_department": dict(by_department),
        "by_research_area": dict(by_research_area),
        "colleges": sorted(by_college.keys()),
        "departments": sorted(by_department.keys()),
        "research_areas": sorted(by_research_area.keys()),
    }


if __name__ == "__main__":
    result = unify_teachers()

    if not result.get("success", False):
        print(f"\n錯誤: {result.get('error', '未知錯誤')}")
        sys.exit(1)
