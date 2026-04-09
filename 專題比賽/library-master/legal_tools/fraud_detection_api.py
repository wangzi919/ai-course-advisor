"""FastMCP tool that provides fraud search functionality."""

from __future__ import annotations

import json
import requests
from typing import Optional
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("fraud_case_retrieval")


def search_fraud_cases(query_text: str, top_k: int = 2) -> str:
    """Search for fraud cases.
    
    Args:
        query_text: The text to search for fraud-related cases
        top_k: Number of top results to return (default: 2)
        
    Returns:
        JSON response containing fraud case search results
    """
    
    # API endpoint
    url = "http://140.120.13.248:11208/retrieve"
    
    # Request payload
    payload = {
        "crime_type": "fraud",
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
def get_available_fraud_factors() -> str:
    """取得可用的詐欺量刑因子清單。
    
    提供所有可用的詐欺量刑因子供 agent 參考和使用。
    
    Returns:
        JSON格式的詐欺量刑因子清單
    """
    
    # 定義詐欺量刑因子
    fraud_factors = {
        "large_property_seizure": {
            "name": "扣押大量財物作為證物",
            "description": "詐騙案件中扣押大量財物作為證物的情況"
        },
        "impersonating_official": {
            "name": "冒用公務員名義",
            "description": "冒用政府機關公務員身分進行詐騙活動"
        },
        "multiple_false_documents": {
            "name": "多輪的虛假文件交付",
            "description": "多次、反覆提供虛假文件或證明進行詐騙"
        },
        "organized_crime_structure": {
            "name": "犯罪集團的結構與協作程度高",
            "description": "詐騙集團組織結構完整且成員間協作程度高"
        },
        "cross_border_fraud": {
            "name": "跨境詐騙",
            "description": "涉及跨國或跨境的詐騙活動"
        },
        "creating_emergency_threats": {
            "name": "製造緊急情況或威脅",
            "description": "故意製造緊急狀況或威脅來迫使被害人行動"
        },
        "huge_amount_involved": {
            "name": "涉案金額巨大",
            "description": "詐騙案件涉及的金額規模巨大"
        },
        "victim_trust_level": {
            "name": "被害人對匯款用途的信任程度",
            "description": "被害人對詐騙者所聲稱的匯款用途信任程度"
        },
        "criminal_organization_scale": {
            "name": "犯罪組織規模",
            "description": "參與詐騙活動的犯罪組織規模大小"
        },
        "inducing_quick_decisions": {
            "name": "誘使快速決策",
            "description": "故意營造時間壓力，誘使被害人快速做出決定"
        },
        "exploiting_social_context": {
            "name": "利用社會情境或事件",
            "description": "利用當前社會事件或特殊情境進行詐騙"
        },
        "emotional_manipulation": {
            "name": "受他人濫用情感因素",
            "description": "利用情感因素操縱被害人進行詐騙"
        },
        "inducing_false_belief": {
            "name": "誘使被害人相信虛假情況",
            "description": "透過各種手段誘使被害人相信虛假的情況或訊息"
        }
    }
    
    result = {
        "available_factors": fraud_factors,
        "total_factors": len(fraud_factors),
        "usage_note": "Agent 可根據詐欺案件內容選擇適用的量刑因子"
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def search_similar_fraud_cases(keywords: str, top_k: int = 5) -> str:
    """根據關鍵字搜尋相似的詐欺案例。
    
    使用關鍵字作為查詢條件，搜尋具有相似特徵的詐欺案例。
    
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
                "example": "冒用公務員名義 跨境詐騙 涉案金額巨大"
            }, ensure_ascii=False, indent=2)
        
        # 呼叫詐欺案例搜尋功能
        search_result = search_fraud_cases(query_text, top_k)
        
        # 包裝結果
        result = {
            "search_query": query_text,
            "search_results": json.loads(search_result)
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"搜尋相似詐欺案例時發生錯誤: {str(e)}"
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
