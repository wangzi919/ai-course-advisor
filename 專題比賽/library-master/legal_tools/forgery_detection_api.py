"""FastMCP tool that provides forgery search functionality."""

from __future__ import annotations

import json
import requests
from typing import Optional
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("forgery_case_retrieval")


def search_forgery_cases(query_text: str, top_k: int = 2) -> str:
    """Search for forgery cases.
    
    Args:
        query_text: The text to search for forgery-related cases
        top_k: Number of top results to return (default: 2)
        
    Returns:
        JSON response containing forgery case search results
    """
    
    # API endpoint
    url = "http://140.120.13.248:11208/retrieve"
    
    # Request payload
    payload = {
        "crime_type": "forgery",
        "top_k": top_k,
        "query_text": query_text
    }
    
    # Headers
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    try:
        # Make the API request
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        # Parse and return the response
        result = response.json()
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except requests.exceptions.RequestException as e:
        return f"API 請求失敗: {str(e)}"
    except json.JSONDecodeError as e:
        return f"回應解析失敗: {str(e)}"
    except Exception as e:
        return f"搜尋過程發生錯誤: {str(e)}"


@mcp.tool()
def get_available_forgery_factors() -> str:
    """取得可用的偽造量刑因子清單。
    
    提供所有可用的偽造量刑因子供 agent 參考和使用。
    
    Returns:
        JSON格式的偽造量刑因子清單
    """
    
    # 定義偽造量刑因子
    forgery_factors = {
        "document_type": {
            "name": "偽造文件類型",
            "description": "偽造的文件類型（身分證、護照、印章、契約等）"
        },
        "forgery_method": {
            "name": "偽造手法",
            "description": "採用的偽造技術或手法（電腦合成、手工偽造、影印變造等）"
        },
        "forgery_quality": {
            "name": "偽造精密度",
            "description": "偽造文件的精密程度和仿真度"
        },
        "official_document": {
            "name": "偽造公文書",
            "description": "偽造政府機關、法院或其他官方文件"
        },
        "private_document": {
            "name": "偽造私文書",
            "description": "偽造私人文件、契約或證明文件"
        },
        "commercial_purpose": {
            "name": "營利目的",
            "description": "以營利為目的進行偽造活動"
        },
        "financial_damage": {
            "name": "造成財產損害",
            "description": "偽造行為造成他人財產損失的金額"
        },
        "identity_theft": {
            "name": "冒用他人身分",
            "description": "使用他人身分證件或個人資料進行偽造"
        },
        "systematic_forgery": {
            "name": "系統性偽造",
            "description": "有組織、大量或持續性的偽造活動"
        },
        "professional_tools": {
            "name": "使用專業工具",
            "description": "使用專業設備或軟體進行偽造"
        },
        "public_faith_damage": {
            "name": "損害公共信用",
            "description": "對政府或機關文件公信力造成損害"
        },
        "repeat_offender": {
            "name": "累犯",
            "description": "有偽造文書前科或重複犯罪"
        },
        "organized_crime": {
            "name": "集團犯罪",
            "description": "參與偽造集團或有組織的犯罪活動"
        },
        "cross_border": {
            "name": "跨境偽造",
            "description": "涉及跨國或跨境的偽造活動"
        },
        "multiple_documents": {
            "name": "偽造多種文件",
            "description": "同時偽造多種類型的文件"
        },
        "fraud_group_connection": {
            "name": "詐騙集團聯繫",
            "description": "與詐騙集團有關聯或合作進行偽造文書活動"
        },
        "multiple_banks_involved": {
            "name": "涉及多家銀行",
            "description": "偽造文書活動涉及多家金融機構或銀行"
        },
        "victim_count": {
            "name": "涉及被害人數量",
            "description": "偽造文書活動影響的被害人人數規模"
        },
        "multiple_offenses": {
            "name": "行為次數多",
            "description": "多次重複進行偽造文書的犯罪行為"
        },
        "intimidation_behavior": {
            "name": "實施恐嚇行為",
            "description": "在偽造文書過程中對他人進行威脅或恐嚇"
        },
        "forgery_subject": {
            "name": "偽造主體",
            "description": "偽造文書的具體主體對象（個人、企業、機關等）"
        },
        "target_account_amount": {
            "name": "目標帳戶的金額",
            "description": "偽造文書所涉及的目標帳戶金額規模"
        }
    }
    
    result = {
        "available_factors": forgery_factors,
        "total_factors": len(forgery_factors),
        "usage_note": "Agent 可根據偽造案件內容選擇適用的量刑因子"
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def search_similar_forgery_cases(keywords: str, top_k: int = 5) -> str:
    """根據關鍵字搜尋相似的偽造案例。
    
    使用關鍵字作為查詢條件，搜尋具有相似特徵的偽造案例。
    
    Args:
        keywords: 搜尋關鍵字，可以是量刑因子名稱或相關詞彙，多個關鍵字用空格分隔
        top_k: 返回相似案例的數量 (預設: 5)
        
    Returns:
        JSON格式的相似案例搜尋結果
    """
    
    try:
        # 直接使用輸入的關鍵字作為查詢文字
        query_text = keywords.strip()
        
        if not query_text:
            return json.dumps({
                "error": "請提供搜尋關鍵字",
                "example": "偽造身分證 營利目的"
            }, ensure_ascii=False, indent=2)
        
        # 呼叫偽造案例搜尋功能
        search_result = search_forgery_cases(query_text, top_k)
        
        # 包裝結果
        result = {
            "search_query": query_text,
            "search_results": json.loads(search_result)
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"搜尋相似偽造案例時發生錯誤: {str(e)}"
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
