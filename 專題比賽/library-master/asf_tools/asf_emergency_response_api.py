import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ASF_Emergency_Response_API")

# Load ASF emergency response manual data
def _load_asf_manual_data() -> Dict:
    """Load ASF emergency response manual data from JSON files."""
    current_dir = Path(__file__).parent
    manual_dir = current_dir.parent / "data" / "asf" / "taichung_asf_emergency_response_manual"
    
    if not manual_dir.exists():
        raise FileNotFoundError(f"ASF manual directory not found: {manual_dir}")
    
    data = {
        "chapters": [],
        "sops": []
    }
    
    # Load main chapters
    chapter_files = [
        ("壹", "chapter_1_foreword.json"),
        ("貳", "chapter_2_asf_introduction.json"),
        ("參", "chapter_3_response_center_framework.json"),
        ("肆", "chapter_4_prevention.json"),
        ("伍", "chapter_5_preparedness.json"),
        ("陸", "chapter_6_response.json")
    ]
    
    for chapter_num, filename in chapter_files:
        file_path = manual_dir / filename
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                chapter_data = json.load(f)
                chapter_data["chapter_number"] = chapter_num
                data["chapters"].append(chapter_data)
    
    # Load SOPs
    sop_files = [
        "asf_preliminary_screening_sop.json",
        "asf_suspected_case_sampling_sop.json",
        "farm_inspection_checklist.json"
    ]
    
    for filename in sop_files:
        file_path = manual_dir / filename
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                sop_data = json.load(f)
                data["sops"].append(sop_data)
    
    return data

# Global data variable
ASF_MANUAL_DATA = _load_asf_manual_data()

@mcp.tool()
def asf_manual_overview() -> Dict:
    """
    取得非洲豬瘟緊急應變措施手冊總覽
    
    Returns:
        dict: 手冊章節概覽和可用的查詢選項
    """
    chapters_info = []
    for chapter in ASF_MANUAL_DATA.get("chapters", []):
        chapters_info.append({
            "chapter_number": chapter.get("chapter_number"),
            "subtitle": chapter.get("subtitle"),
            "summary": chapter.get("summary")
        })
    
    sops_info = []
    for sop in ASF_MANUAL_DATA.get("sops", []):
        sops_info.append({
            "title": sop.get("title"),
            "subtitle": sop.get("subtitle", ""),
            "summary": sop.get("summary", "")
        })
    
    return {
        "manual_title": "臺中市防範非洲豬瘟緊急應變措施手冊",
        "chapters": chapters_info,
        "standard_procedures": sops_info,
        "available_queries": [
            "chapter_content", "response_center_info", "sop_details", 
            "asf_basic_info", "prevention_measures", "response_measures"
        ]
    }

@mcp.tool()
def asf_chapter_content(chapter: str) -> Dict:
    """
    查詢手冊特定章節內容
    
    Args:
        chapter: 章節編號，可選值:
            - 壹: 前言
            - 貳: 非洲豬瘟介紹及其重要性
            - 參: 非洲豬瘟災害應變中心架構
            - 肆: 預防
            - 伍: 整備
            - 陸: 應變
    
    Returns:
        dict: 指定章節的詳細內容
    """
    for ch in ASF_MANUAL_DATA.get("chapters", []):
        if ch.get("chapter_number") == chapter:
            return {
                "chapter_number": ch.get("chapter_number"),
                "title": ch.get("title"),
                "subtitle": ch.get("subtitle"),
                "summary": ch.get("summary"),
                "sections": ch.get("sections", [])
            }
    
    return {"error": f"章節 '{chapter}' 不存在。可用章節: 壹, 貳, 參, 肆, 伍, 陸"}

@mcp.tool()
def asf_basic_info(query_type: str) -> Dict:
    """
    查詢非洲豬瘟基本資訊
    
    Args:
        query_type: 查詢類型，可選值:
            - definition: 非洲豬瘟定義
            - symptoms: 臨床症狀
            - transmission: 傳播途徑
            - virus_characteristics: 病毒特性
            - pathology: 病理學
            - epidemiology: 流行病學
            - global_situation: 全球疫情概況
            - survival_conditions: 病毒存活條件
    
    Returns:
        dict: 相關非洲豬瘟基本資訊
    """
    # Find chapter 貳 (非洲豬瘟介紹及其重要性)
    chapter_2 = None
    for ch in ASF_MANUAL_DATA.get("chapters", []):
        if ch.get("chapter_number") == "貳":
            chapter_2 = ch
            break
    
    if not chapter_2:
        return {"error": "找不到非洲豬瘟介紹章節"}
    
    sections = chapter_2.get("sections", [])
    
    if query_type == "definition":
        for section in sections:
            if "何謂非洲豬瘟" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    elif query_type == "virus_characteristics":
        for section in sections:
            if "非洲豬瘟病毒與毒力簡介" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    elif query_type == "pathology":
        for section in sections:
            if "病理學" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    elif query_type == "epidemiology" or query_type == "transmission":
        for section in sections:
            if "流行病學" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    elif query_type == "survival_conditions":
        for section in sections:
            if "非洲豬瘟病毒於各種環境條件下適應力" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    elif query_type == "global_situation":
        for section in sections:
            if "全球疫情散播概況" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    
    return {"error": f"查詢類型 '{query_type}' 不存在或無相關資料"}

@mcp.tool()
def asf_response_center_info(query_type: str) -> Dict:
    """
    查詢災害應變中心相關資訊
    
    Args:
        query_type: 查詢類型，可選值:
            - structure: 應變中心組織架構
            - management_levels: 分級管理機制
            - central_groups: 中央應變中心各組職掌
            - local_structure: 地方應變中心結構
            - activation_criteria: 啟動標準
    
    Returns:
        dict: 相關應變中心資訊
    """
    # Find chapter 參 (非洲豬瘟災害應變中心架構)
    chapter_3 = None
    for ch in ASF_MANUAL_DATA.get("chapters", []):
        if ch.get("chapter_number") == "參":
            chapter_3 = ch
            break
    
    if not chapter_3:
        return {"error": "找不到災害應變中心架構章節"}
    
    sections = chapter_3.get("sections", [])
    
    if query_type == "structure":
        for section in sections:
            if "非洲豬瘟中央災害應變中心架構" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    elif query_type == "management_levels":
        for section in sections:
            if "分級管理機制" in section.get("heading", ""):
                return {
                    "heading": section.get("heading"),
                    "content": section.get("content")
                }
    elif query_type == "central_groups":
        group_sections = []
        for section in sections:
            if any(group in section.get("heading", "") for group in ["邊境管制", "疫情控制", "產業輔導", "健康照護", "物資整備", "民生經濟", "新聞資訊"]):
                group_sections.append({
                    "heading": section.get("heading"),
                    "content": section.get("content")
                })
        if group_sections:
            return {"groups": group_sections}
    
    return {"error": f"查詢類型 '{query_type}' 不存在或無相關資料"}

@mcp.tool()
def asf_sop_details(sop_type: str) -> Dict:
    """
    查詢標準作業程序詳細內容
    
    Args:
        sop_type: SOP類型，可選值:
            - screening: 初篩檢測SOP
            - sampling: 疑似病例採樣SOP
            - inspection: 豬場疫情訪查確認表
    
    Returns:
        dict: 相關SOP詳細內容
    """
    sops = ASF_MANUAL_DATA.get("sops", [])
    
    if sop_type == "screening":
        for sop in sops:
            if "初篩檢測" in sop.get("title", "") or "核酸定量檢測" in sop.get("title", ""):
                return {
                    "title": sop.get("title"),
                    "subtitle": sop.get("subtitle"),
                    "summary": sop.get("summary"),
                    "sections": sop.get("sections", [])
                }
    elif sop_type == "sampling":
        for sop in sops:
            if "採樣" in sop.get("title", ""):
                return {
                    "title": sop.get("title"),
                    "subtitle": sop.get("subtitle"),
                    "summary": sop.get("summary"),
                    "sections": sop.get("sections", [])
                }
    elif sop_type == "inspection":
        for sop in sops:
            if "訪查確認" in sop.get("title", ""):
                return {
                    "title": sop.get("title"),
                    "subtitle": sop.get("subtitle"),
                    "summary": sop.get("summary"),
                    "sections": sop.get("sections", [])
                }
    
    return {"error": f"SOP類型 '{sop_type}' 不存在。可用類型: screening, sampling, inspection"}

@mcp.tool()
def asf_prevention_measures(measure_type: str = "all") -> Dict:
    """
    查詢預防措施相關資訊
    
    Args:
        measure_type: 措施類型，可選值:
            - all: 所有預防措施
            - border_control: 邊境管制
            - farm_biosecurity: 養豬場生物安全
            - quarantine: 檢疫措施
            - public_awareness: 宣導教育
    
    Returns:
        dict: 相關預防措施資訊
    """
    # Find chapter 肆 (預防)
    chapter_4 = None
    for ch in ASF_MANUAL_DATA.get("chapters", []):
        if ch.get("chapter_number") == "肆":
            chapter_4 = ch
            break
    
    if not chapter_4:
        return {"error": "找不到預防措施章節"}
    
    if measure_type == "all":
        return {
            "chapter_number": chapter_4.get("chapter_number"),
            "title": chapter_4.get("title"),
            "subtitle": chapter_4.get("subtitle"),
            "summary": chapter_4.get("summary"),
            "sections": chapter_4.get("sections", [])
        }
    else:
        sections = chapter_4.get("sections", [])
        relevant_sections = []
        
        for section in sections:
            heading = section.get("heading", "").lower()
            if (measure_type == "border_control" and any(term in heading for term in ["邊境", "管制", "檢疫"])) or \
               (measure_type == "farm_biosecurity" and any(term in heading for term in ["生物安全", "養豬場", "防疫"])) or \
               (measure_type == "quarantine" and any(term in heading for term in ["檢疫", "隔離"])) or \
               (measure_type == "public_awareness" and any(term in heading for term in ["宣導", "教育", "訓練"])):
                relevant_sections.append(section)
        
        if relevant_sections:
            return {"relevant_sections": relevant_sections}
        else:
            return {"error": f"找不到與 '{measure_type}' 相關的預防措施資訊"}

@mcp.tool()
def asf_response_measures(response_type: str = "all") -> Dict:
    """
    查詢應變措施相關資訊
    
    Args:
        response_type: 應變類型，可選值:
            - all: 所有應變措施
            - outbreak_response: 疫情爆發應變
            - containment: 疫情圍堵
            - disposal: 撲殺處置
            - disinfection: 消毒清潔
            - movement_control: 移動管制
    
    Returns:
        dict: 相關應變措施資訊
    """
    # Find chapter 陸 (應變)
    chapter_6 = None
    for ch in ASF_MANUAL_DATA.get("chapters", []):
        if ch.get("chapter_number") == "陸":
            chapter_6 = ch
            break
    
    if not chapter_6:
        return {"error": "找不到應變措施章節"}
    
    if response_type == "all":
        return {
            "chapter_number": chapter_6.get("chapter_number"),
            "title": chapter_6.get("title"),
            "subtitle": chapter_6.get("subtitle"),
            "summary": chapter_6.get("summary"),
            "sections": chapter_6.get("sections", [])
        }
    else:
        sections = chapter_6.get("sections", [])
        relevant_sections = []
        
        for section in sections:
            heading = section.get("heading", "").lower()
            if (response_type == "outbreak_response" and any(term in heading for term in ["疫情", "爆發", "應變"])) or \
               (response_type == "containment" and any(term in heading for term in ["圍堵", "防堵", "封鎖"])) or \
               (response_type == "disposal" and any(term in heading for term in ["撲殺", "處置", "銷毀"])) or \
               (response_type == "disinfection" and any(term in heading for term in ["消毒", "清潔", "清理"])) or \
               (response_type == "movement_control" and any(term in heading for term in ["移動", "管制", "運輸"])):
                relevant_sections.append(section)
        
        if relevant_sections:
            return {"relevant_sections": relevant_sections}
        else:
            return {"error": f"找不到與 '{response_type}' 相關的應變措施資訊"}

@mcp.tool()
def asf_preparedness_measures() -> Dict:
    """
    查詢整備措施相關資訊
    
    Returns:
        dict: 整備措施詳細內容
    """
    # Find chapter 伍 (整備)
    chapter_5 = None
    for ch in ASF_MANUAL_DATA.get("chapters", []):
        if ch.get("chapter_number") == "伍":
            chapter_5 = ch
            break
    
    if not chapter_5:
        return {"error": "找不到整備措施章節"}
    
    return {
        "chapter_number": chapter_5.get("chapter_number"),
        "title": chapter_5.get("title"),
        "subtitle": chapter_5.get("subtitle"),
        "summary": chapter_5.get("summary"),
        "sections": chapter_5.get("sections", [])
    }

@mcp.tool()
def asf_search_content(keyword: str) -> Dict:
    """
    在手冊內容中搜尋關鍵字
    
    Args:
        keyword: 搜尋關鍵字
    
    Returns:
        dict: 包含關鍵字的相關內容
    """
    results = []
    
    # Search in chapters
    for chapter in ASF_MANUAL_DATA.get("chapters", []):
        chapter_matches = []
        
        # Search in chapter summary
        if keyword.lower() in chapter.get("summary", "").lower():
            chapter_matches.append({
                "location": "摘要",
                "content": chapter.get("summary", "")
            })
        
        # Search in sections
        for section in chapter.get("sections", []):
            if keyword.lower() in section.get("heading", "").lower() or \
               keyword.lower() in section.get("content", "").lower():
                chapter_matches.append({
                    "location": section.get("heading", ""),
                    "content": section.get("content", "")[:500] + "..." if len(section.get("content", "")) > 500 else section.get("content", "")
                })
        
        if chapter_matches:
            results.append({
                "chapter": chapter.get("subtitle", ""),
                "matches": chapter_matches
            })
    
    # Search in SOPs
    for sop in ASF_MANUAL_DATA.get("sops", []):
        sop_matches = []
        
        if keyword.lower() in sop.get("title", "").lower() or \
           keyword.lower() in sop.get("summary", "").lower():
            sop_matches.append({
                "location": "標題/摘要",
                "content": f"標題: {sop.get('title', '')}\n摘要: {sop.get('summary', '')}"
            })
        
        for section in sop.get("sections", []):
            if keyword.lower() in section.get("heading", "").lower() or \
               keyword.lower() in section.get("content", "").lower():
                sop_matches.append({
                    "location": section.get("heading", ""),
                    "content": section.get("content", "")[:500] + "..." if len(section.get("content", "")) > 500 else section.get("content", "")
                })
        
        if sop_matches:
            results.append({
                "sop": sop.get("title", ""),
                "matches": sop_matches
            })
    
    if results:
        return {
            "keyword": keyword,
            "total_matches": len(results),
            "results": results
        }
    else:
        return {
            "keyword": keyword,
            "total_matches": 0,
            "message": f"未找到包含關鍵字 '{keyword}' 的內容"
        }

if __name__ == "__main__":
    mcp.run()