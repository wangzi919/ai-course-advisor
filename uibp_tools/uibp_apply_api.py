"""
中興大學校學士申請流程查詢 API

此 API 提供工具幫助學生了解校學士學位申請流程、時程、所需文件等資訊。
"""

import json
from pathlib import Path
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP 伺服器
mcp = FastMCP("nchu_uibp_apply")

# 載入申請流程資料
DATA_FILE = Path(__file__).parent.parent / "data" / "uibp" / "uibp_apply.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    apply_data = json.load(f)

# 取得主要資料
_data = apply_data.get("data", [{}])[0]


@mcp.tool()
def nchu_uibp_get_apply_process() -> Dict[str, Any]:
    """
    取得校學士完整申請流程

    回傳校學士申請的完整流程資訊，包含所有步驟、時程、聯絡方式。
    適合回答「如何申請校學士」、「校學士申請流程」等問題。

    Returns:
        Dictionary with full application process information

    Examples:
        uibp_get_apply_process()
    """
    return {
        "steps": _data.get("steps", []),
        "timeline": _data.get("timeline", {}),
        "contact": _data.get("contact", {}),
        "metadata": apply_data.get("metadata", {})
    }


@mcp.tool()
def nchu_uibp_get_apply_step(step_number: int) -> Dict[str, Any]:
    """
    取得校學士申請特定步驟的詳細資訊

    Args:
        step_number: 步驟編號（1-4）

    Returns:
        Dictionary with step details

    Examples:
        uibp_get_apply_step(1)  # 取得第一步驟：修習課程
        uibp_get_apply_step(2)  # 取得第二步驟：預約會談
        uibp_get_apply_step(3)  # 取得第三步驟：撰寫計畫書
        uibp_get_apply_step(4)  # 取得第四步驟：繳交送審
    """
    steps = _data.get("steps", [])

    if step_number < 1 or step_number > len(steps):
        return {
            "error": f"步驟編號必須在 1 到 {len(steps)} 之間",
            "available_steps": len(steps)
        }

    step = steps[step_number - 1]
    return {
        "step": step,
        "total_steps": len(steps)
    }


@mcp.tool()
def nchu_uibp_get_apply_timeline() -> Dict[str, Any]:
    """
    取得校學士申請重要時程

    回傳文件繳交期間、結果公告時間等重要時程資訊。
    適合回答「校學士申請截止日期」、「什麼時候放榜」等問題。

    Returns:
        Dictionary with timeline information

    Examples:
        uibp_get_apply_timeline()
    """
    return {
        "timeline": _data.get("timeline", {}),
        "last_updated": apply_data.get("metadata", {}).get("last_updated", "")
    }


@mcp.tool()
def nchu_uibp_get_apply_contact() -> Dict[str, Any]:
    """
    取得校學士申請聯絡資訊

    回傳承辦單位、電話、信箱、地址等聯絡資訊。
    適合回答「校學士申請問題要問誰」、「承辦人聯絡方式」等問題。

    Returns:
        Dictionary with contact information

    Examples:
        uibp_get_apply_contact()
    """
    return {
        "contact": _data.get("contact", {}),
        "data_source": apply_data.get("metadata", {}).get("data_source", "")
    }


@mcp.tool()
def nchu_uibp_list_apply_steps() -> Dict[str, Any]:
    """
    列出校學士申請所有步驟摘要

    快速列出所有申請步驟的標題，方便概覽整個流程。

    Returns:
        Dictionary with steps overview

    Examples:
        uibp_list_apply_steps()
    """
    steps = _data.get("steps", [])

    return {
        "steps": [
            {
                "step": s.get("step"),
                "title": s.get("title")
            }
            for s in steps
        ],
        "total_steps": len(steps)
    }


@mcp.tool()
def nchu_uibp_apply_stats() -> Dict[str, Any]:
    """
    顯示校學士申請資料統計資訊

    Returns:
        Dictionary with statistics about apply data
    """
    steps = _data.get("steps", [])
    timeline = _data.get("timeline", {})
    metadata = apply_data.get("metadata", {})

    return {
        "total_steps": len(steps),
        "has_timeline": bool(timeline),
        "last_updated": metadata.get("last_updated", ""),
        "data_source": metadata.get("data_source", "")
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
