import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Hospital_Rules_API")

# Load hospital rules data
def _load_hospital_data() -> Dict:
    """Load hospital rules data from JSON file."""
    current_dir = Path(__file__).parent
    json_file = current_dir / "data/hospital/hospital_rule.json"
    
    if not json_file.exists():
        raise FileNotFoundError(f"Hospital rules file not found: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

# Global data variable
HOSPITAL_DATA = _load_hospital_data()

@mcp.tool()
def hospital_info_query(category: str) -> Dict:
    """
    查詢醫院基本資訊
    
    Args:
        category: 查詢類別，可選值:
            - profile: 醫院簡介
            - mission: 使命
            - vision: 願景
            - spirit: 精神
            - values: 價值觀
            - tasks: 主要任務
            - all: 所有基本資訊
    
    Returns:
        dict: 相關醫院資訊
    """
    profile = HOSPITAL_DATA.get("hospital_profile", {})
    
    if category == "profile":
        return {"intro": profile.get("intro", "")}
    elif category == "mission":
        return {"mission": profile.get("mission", "")}
    elif category == "vision":
        return {"vision": profile.get("vision", {})}
    elif category == "spirit":
        return {"spirit": profile.get("spirit", "")}
    elif category == "values":
        return {"values": profile.get("values", [])}
    elif category == "tasks":
        return {"tasks": profile.get("tasks", [])}
    elif category == "all":
        return profile
    else:
        return {"error": f"Invalid category: {category}. Valid options: profile, mission, vision, spirit, values, tasks, all"}

@mcp.tool()
def admission_guide(query_type: str) -> Dict:
    """
    提供入院相關指引和流程
    
    Args:
        query_type: 查詢類型，可選值:
            - process: 入院流程
            - documents: 所需文件
            - wifi: WiFi設定
            - reporting: 報到規定
            - bed_arrangement: 配床原則
            - schedule: 服務時間
    
    Returns:
        dict: 入院相關資訊和指引
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Find admission chapter (chapter 1 and 2)
    wifi_info = None
    admission_info = None
    
    for chapter in chapters:
        if chapter.get("number") == 1:
            for section in chapter.get("sections", []):
                if "Wi-Fi" in section.get("title", ""):
                    wifi_info = section
        elif chapter.get("number") == 2:
            admission_info = chapter
    
    if query_type == "wifi":
        if wifi_info:
            return {
                "title": wifi_info.get("title", ""),
                "content": wifi_info.get("content", [])
            }
        return {"error": "WiFi information not found"}
    
    elif query_type == "process" and admission_info:
        for section in admission_info.get("sections", []):
            if "住院流程" in section.get("title", ""):
                return {
                    "title": section.get("title", ""),
                    "content": section.get("content", [])
                }
    
    elif query_type == "documents" and admission_info:
        for section in admission_info.get("sections", []):
            if "住院流程" in section.get("title", ""):
                # Extract document requirements from content
                docs_info = []
                for content in section.get("content", []):
                    if "應準備之文件" in content:
                        docs_info.append(content)
                return {"documents_required": docs_info}
    
    elif query_type == "reporting" and admission_info:
        for section in admission_info.get("sections", []):
            if "報到規定" in section.get("title", ""):
                return {
                    "title": section.get("title", ""),
                    "content": section.get("content", [])
                }
    
    elif query_type == "bed_arrangement" and admission_info:
        for section in admission_info.get("sections", []):
            if "配床原則" in section.get("title", ""):
                return {
                    "title": section.get("title", ""),
                    "content": section.get("content", [])
                }
    
    elif query_type == "schedule":
        # Extract service hours from various sections
        schedule_info = []
        for chapter in chapters:
            for section in chapter.get("sections", []):
                for content in section.get("content", []):
                    if "服務時間" in content or "AM" in content or "PM" in content:
                        schedule_info.append(content)
        return {"service_schedule": schedule_info}
    
    return {"error": f"Invalid query_type: {query_type} or information not found"}

@mcp.tool()
def room_and_facilities(facility_type: str) -> Dict:
    """
    查詢病房等級、收費標準和院內設施
    
    Args:
        facility_type: 設施類型，可選值:
            - room_rates: 病房收費標準
            - amenities: 病房設施
            - phone_numbers: 分機號碼
            - convenience: 便利設施
            - parking: 停車資訊
            - transportation: 交通資訊
    
    Returns:
        dict: 設施和收費相關資訊
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    if facility_type == "room_rates":
        # Find room rates in chapter 2
        for chapter in chapters:
            if chapter.get("number") == 2:
                for section in chapter.get("sections", []):
                    if "病房等級與收費標準" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
    
    elif facility_type == "amenities":
        # Find facilities info in chapter 1
        for chapter in chapters:
            if chapter.get("number") == 1:
                for section in chapter.get("sections", []):
                    if "病房設施" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", []),
                            "extensions": section.get("extensions", [])
                        }
    
    elif facility_type == "phone_numbers":
        # Find phone info
        phone_info = []
        for chapter in chapters:
            if chapter.get("number") == 1:
                for section in chapter.get("sections", []):
                    if "服務電話" in section.get("title", "") or "分機" in section.get("title", ""):
                        phone_info.append({
                            "title": section.get("title", ""),
                            "content": section.get("content", []),
                            "extensions": section.get("extensions", [])
                        })
        return {"phone_information": phone_info}
    
    elif facility_type == "convenience":
        # Find convenience facilities
        for chapter in chapters:
            if chapter.get("number") == 1:
                for section in chapter.get("sections", []):
                    if "便利設施" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
    
    elif facility_type == "transportation":
        # Find transportation info
        for chapter in chapters:
            if chapter.get("number") == 1:
                for section in chapter.get("sections", []):
                    if "交通路線" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", []),
                            "note": section.get("note", "")
                        }
    
    return {"error": f"Invalid facility_type: {facility_type} or information not found"}

@mcp.tool()
def patient_rights_obligations(category: str) -> Dict:
    """
    查詢病人權利與義務相關規定
    
    Args:
        category: 查詢類別，可選值:
            - rights: 病人權利
            - obligations: 病人義務
            - question_guidelines: 如何擬定問題清單
            - all: 所有權利義務資訊
    
    Returns:
        dict: 病人權利義務相關資訊
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Find patient rights and obligations chapter (chapter 4)
    for chapter in chapters:
        if chapter.get("number") == 4:
            sections = chapter.get("sections", [])
            
            if category == "rights":
                for section in sections:
                    if "病人權利" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
            
            elif category == "obligations":
                for section in sections:
                    if "病人義務" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
            
            elif category == "question_guidelines":
                for section in sections:
                    if "如何擬定您的問題清單" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
            
            elif category == "all":
                return {
                    "chapter_title": chapter.get("title", ""),
                    "sections": sections
                }
    
    return {"error": f"Invalid category: {category} or information not found"}

@mcp.tool()
def care_guidelines(guideline_type: str) -> Dict:
    """
    提供住院期間照護指引和配合事項
    
    Args:
        guideline_type: 指引類型，可選值:
            - diet: 飲食相關
            - visiting: 探病規定
            - safety: 安全注意事項
            - equipment: 電器使用規定
            - food_storage: 食物保存
            - personal_care: 個人照護
            - mask_wearing: 口罩佩戴規定
    
    Returns:
        dict: 照護指引和注意事項
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Find care guidelines chapter (chapter 5)
    for chapter in chapters:
        if chapter.get("number") == 5:
            sections = chapter.get("sections", [])
            
            for section in sections:
                title = section.get("title", "")
                
                if guideline_type == "diet" and "飲食" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif guideline_type == "visiting" and "探病" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif guideline_type == "safety" and ("安寧" in title or "安全" in title):
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif guideline_type == "equipment" and "電器" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif guideline_type == "food_storage" and "食物" in title and "保存" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif guideline_type == "personal_care" and ("照護" in title or "個人用品" in title):
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif guideline_type == "mask_wearing" and "口罩" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
    
    return {"error": f"Invalid guideline_type: {guideline_type} or information not found"}

@mcp.tool()
def fee_calculator(service_type: str, days: Optional[int] = None, room_type: Optional[str] = None) -> Dict:
    """
    計算或查詢醫療費用
    
    Args:
        service_type: 服務類型，可選值:
            - room_fees: 病房費用
            - meal_fees: 伙食費用
            - insurance_coverage: 健保給付
            - partial_payment: 部分負擔
            - non_covered: 健保不給付項目
        days: 住院天數（可選）
        room_type: 病房類型（可選）
    
    Returns:
        dict: 費用計算結果和說明
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    if service_type == "room_fees":
        # Find room fee information
        for chapter in chapters:
            if chapter.get("number") in [2, 3]:
                for section in chapter.get("sections", []):
                    if "收費標準" in section.get("title", "") or "病房等級" in section.get("title", ""):
                        content = section.get("content", [])
                        result = {
                            "title": section.get("title", ""),
                            "content": content
                        }
                        
                        # If days provided, add calculation note
                        if days:
                            result["calculation_note"] = f"住院{days}天的費用計算請參考收費標準"
                        
                        return result
    
    elif service_type == "meal_fees":
        # Find meal fee information
        for chapter in chapters:
            if chapter.get("number") in [5, 6]:
                for section in chapter.get("sections", []):
                    if "伙食費" in section.get("title", "") or "飲食" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
    
    elif service_type == "insurance_coverage":
        # Find insurance coverage info
        for chapter in chapters:
            if chapter.get("number") == 6:
                for section in chapter.get("sections", []):
                    if "健保病人應自行負擔費用" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
    
    elif service_type == "partial_payment":
        # Find partial payment info
        for chapter in chapters:
            if chapter.get("number") == 6:
                for section in chapter.get("sections", []):
                    if "部分負擔" in section.get("content", []):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
    
    elif service_type == "non_covered":
        # Find non-covered items
        for chapter in chapters:
            if chapter.get("number") == 6:
                for section in chapter.get("sections", []):
                    if "不給付項目" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
    
    return {"error": f"Invalid service_type: {service_type} or information not found"}

@mcp.tool()
def document_application(document_type: str) -> Dict:
    """
    提供各類證明文件申請流程和費用
    
    Args:
        document_type: 文件類型，可選值:
            - medical_certificate: 診斷證明書
            - birth_certificate: 出生證明書
            - death_certificate: 死亡證明書
            - medical_records: 病歷摘要
            - receipt_copy: 收據副本
            - disability_assessment: 身心障礙鑑定
            - reports_imaging: 檢查報告及影像
            - care_worker: 外籍看護申請
    
    Returns:
        dict: 申請流程、所需文件和費用資訊
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Find document application chapter (chapter 7)
    for chapter in chapters:
        if chapter.get("number") == 7:
            sections = chapter.get("sections", [])
            
            for section in sections:
                title = section.get("title", "")
                
                if document_type == "medical_certificate" and "診斷證明書" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif document_type == "birth_certificate" and "出生證明書" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif document_type == "death_certificate" and "死亡證明書" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif document_type == "medical_records" and "病歷摘要" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif document_type == "receipt_copy" and "收據副本" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif document_type == "disability_assessment" and "身心障礙" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif document_type == "reports_imaging" and ("檢查報告" in title or "影像" in title):
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
                elif document_type == "care_worker" and "外籍看護" in title:
                    return {
                        "title": title,
                        "content": section.get("content", [])
                    }
    
    return {"error": f"Invalid document_type: {document_type} or information not found"}

@mcp.tool()
def hospital_services(service_category: str) -> Dict:
    """
    查詢醫院附屬服務和設施
    
    Args:
        service_category: 服務類別，可選值:
            - shops: 商店設施
            - wheelchair_rental: 輪椅租借
            - parking: 停車服務
            - transport: 交通服務
            - care_services: 照護服務
            - funeral_services: 太平間服務
            - medical_equipment: 醫療輔具
    
    Returns:
        dict: 服務內容、位置和收費資訊
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Find hospital services chapter (chapter 8)
    for chapter in chapters:
        if chapter.get("number") == 8:
            sections = chapter.get("sections", [])
            
            for section in sections:
                title = section.get("title", "")
                content = section.get("content", [])
                
                if service_category == "shops" and ("商店" in title or "設施" in title):
                    return {
                        "title": title,
                        "content": content
                    }
                elif service_category == "wheelchair_rental" and "輪椅" in title:
                    return {
                        "title": title,
                        "content": content
                    }
                elif service_category == "parking" and any("停車" in c for c in content):
                    parking_info = [c for c in content if "停車" in c]
                    return {
                        "title": title,
                        "parking_information": parking_info
                    }
                elif service_category == "transport" and ("交通" in title or any("計程車" in c or "救護車" in c for c in content)):
                    transport_info = [c for c in content if "計程車" in c or "救護車" in c or "交通" in c]
                    return {
                        "title": title,
                        "transport_services": transport_info
                    }
                elif service_category == "care_services" and ("照護" in title or any("照護" in c for c in content)):
                    care_info = [c for c in content if "照護" in c]
                    return {
                        "title": title,
                        "care_services": care_info
                    }
                elif service_category == "funeral_services" and ("太平間" in title or any("太平間" in c for c in content)):
                    funeral_info = [c for c in content if "太平間" in c or "安息室" in c]
                    return {
                        "title": title,
                        "funeral_services": funeral_info
                    }
                elif service_category == "medical_equipment" and "醫療輔具" in title:
                    return {
                        "title": title,
                        "content": content
                    }
    
    return {"error": f"Invalid service_category: {service_category} or information not found"}

@mcp.tool()
def discharge_procedures(procedure_type: str = "standard") -> Dict:
    """
    提供出院手續和轉院申請流程
    
    Args:
        procedure_type: 手續類型，可選值:
            - standard: 標準出院流程
            - transfer: 轉院流程
            - self_discharge: 自動出院
            - timing: 出院時間規定
    
    Returns:
        dict: 出院流程、時間和注意事項
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Find discharge procedures chapter (chapter 9)
    for chapter in chapters:
        if chapter.get("number") == 9:
            sections = chapter.get("sections", [])
            
            for section in sections:
                title = section.get("title", "")
                content = section.get("content", [])
                
                if procedure_type == "standard" and "出院流程" in title:
                    return {
                        "title": title,
                        "content": content
                    }
                elif procedure_type == "transfer" and ("轉院" in title or any("轉院" in c for c in content)):
                    transfer_info = [c for c in content if "轉院" in c]
                    return {
                        "title": title,
                        "transfer_procedures": transfer_info
                    }
                elif procedure_type == "self_discharge" and any("自動出院" in c for c in content):
                    self_discharge_info = [c for c in content if "自動出院" in c]
                    return {
                        "title": title,
                        "self_discharge_info": self_discharge_info
                    }
                elif procedure_type == "timing" and any("出院時間" in c for c in content):
                    timing_info = [c for c in content if "出院時間" in c or "10時" in c]
                    return {
                        "title": title,
                        "timing_information": timing_info
                    }
    
    return {"error": f"Invalid procedure_type: {procedure_type} or information not found"}

@mcp.tool()
def safety_emergency(query_type: str) -> Dict:
    """
    提供住院安全指引和緊急情況處理
    
    Args:
        query_type: 查詢類型，可選值:
            - safety_guidelines: 安全指引
            - emergency_contacts: 緊急聯絡方式
            - help_line: 請幫幫我專線
            - fall_prevention: 防跌指引
            - medication_safety: 用藥安全
    
    Returns:
        dict: 安全指引、緊急聯絡方式和專線資訊
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Find safety guidelines chapter (chapter 10)
    for chapter in chapters:
        if chapter.get("number") == 10:
            sections = chapter.get("sections", [])
            
            for section in sections:
                title = section.get("title", "")
                content = section.get("content", [])
                
                if query_type == "safety_guidelines":
                    return {
                        "title": title,
                        "content": content
                    }
                elif query_type == "help_line" and any("7885" in c for c in content):
                    help_line_info = [c for c in content if "7885" in c or "請幫幫我" in c]
                    return {
                        "title": title,
                        "help_line_info": help_line_info
                    }
                elif query_type == "fall_prevention" and any("跌倒" in c for c in content):
                    fall_info = [c for c in content if "跌倒" in c]
                    return {
                        "title": title,
                        "fall_prevention": fall_info
                    }
                elif query_type == "medication_safety" and any("給藥" in c or "藥物" in c for c in content):
                    med_safety = [c for c in content if "給藥" in c or "藥物" in c]
                    return {
                        "title": title,
                        "medication_safety": med_safety
                    }
    
    # Emergency contacts from chapter 1
    if query_type == "emergency_contacts":
        for chapter in chapters:
            if chapter.get("number") == 1:
                for section in chapter.get("sections", []):
                    if "服務電話" in section.get("title", ""):
                        return {
                            "title": section.get("title", ""),
                            "content": section.get("content", [])
                        }
    
    return {"error": f"Invalid query_type: {query_type} or information not found"}

@mcp.tool()
def search_hospital_rules(keyword: str) -> Dict:
    """
    在醫院規則中搜索特定關鍵字
    
    Args:
        keyword: 搜索關鍵字
    
    Returns:
        dict: 包含關鍵字的相關內容
    """
    results = []
    chapters = HOSPITAL_DATA.get("chapters", [])
    
    # Search in hospital profile
    profile = HOSPITAL_DATA.get("hospital_profile", {})
    for key, value in profile.items():
        if isinstance(value, str) and keyword in value:
            results.append({
                "location": "醫院簡介",
                "section": key,
                "content": value
            })
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and keyword in item:
                    results.append({
                        "location": "醫院簡介",
                        "section": key,
                        "content": item
                    })
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str) and keyword in sub_value:
                    results.append({
                        "location": "醫院簡介",
                        "section": f"{key} - {sub_key}",
                        "content": sub_value
                    })
    
    # Search in chapters
    for chapter in chapters:
        chapter_title = chapter.get("title", "")
        chapter_number = chapter.get("number", "")
        
        if keyword in chapter_title:
            results.append({
                "location": f"第{chapter_number}章",
                "section": "章節標題",
                "content": chapter_title
            })
        
        for section in chapter.get("sections", []):
            section_title = section.get("title", "")
            
            if keyword in section_title:
                results.append({
                    "location": f"第{chapter_number}章 - {chapter_title}",
                    "section": "節標題",
                    "content": section_title
                })
            
            for content in section.get("content", []):
                if keyword in content:
                    results.append({
                        "location": f"第{chapter_number}章 - {chapter_title}",
                        "section": section_title,
                        "content": content
                    })
            
            # Search in extensions if exists
            for extension in section.get("extensions", []):
                if keyword in extension:
                    results.append({
                        "location": f"第{chapter_number}章 - {chapter_title}",
                        "section": f"{section_title} (補充)",
                        "content": extension
                    })
    
    return {
        "keyword": keyword,
        "total_results": len(results),
        "results": results
    }

@mcp.tool()
def get_chapter_overview() -> Dict:
    """
    獲取醫院規則所有章節概覽
    
    Returns:
        dict: 所有章節的標題和編號
    """
    chapters = HOSPITAL_DATA.get("chapters", [])
    overview = []
    
    for chapter in chapters:
        chapter_info = {
            "number": chapter.get("number"),
            "title": chapter.get("title"),
            "sections_count": len(chapter.get("sections", []))
        }
        
        # Get section titles
        section_titles = []
        for section in chapter.get("sections", []):
            section_titles.append(section.get("title", ""))
        
        chapter_info["section_titles"] = section_titles
        overview.append(chapter_info)
    
    return {
        "hospital_name": "彰化基督教醫院",
        "total_chapters": len(chapters),
        "chapters": overview
    }

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
