"""FastMCP tool that provides information about NCHU library opening hours."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

# 資料檔案路徑
DATA_DIR = Path(__file__).parent.parent / "data" / "library"
HOURS_FILE = DATA_DIR / "library_hours.json"

mcp = FastMCP("nchu_library_hours")


def load_library_hours() -> dict[str, Any]:
    """
    載入圖書館開放時間資料

    Returns:
        dict: 圖書館開放時間資料
    """
    if not HOURS_FILE.exists():
        return {
            "error": "資料檔案不存在",
            "message": "請先執行爬蟲腳本或手動建立資料檔案",
            "file_path": str(HOURS_FILE)
        }

    try:
        with open(HOURS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        return {
            "error": "讀取資料失敗",
            "message": str(e)
        }


@mcp.tool()
def get_library_hours() -> str:
    """
    取得所有圖書館空間的開放時間資訊

    Returns:
        str: 格式化的圖書館開放時間資訊
    """
    data = load_library_hours()

    if "error" in data:
        return f"錯誤: {data['error']}\n{data.get('message', '')}"

    # 格式化輸出
    result = []
    result.append("=" * 60)
    result.append("中興大學圖書館開放時間")
    result.append("=" * 60)
    result.append(f"資料更新時間: {data.get('last_updated', '未知')}")
    result.append(f"資料來源: {data.get('source_url', '')}")

    if data.get('note'):
        result.append(f"備註: {data['note']}")

    result.append("")
    result.append("各空間開放時間:")
    result.append("-" * 60)

    spaces = data.get('spaces', [])
    for i, space in enumerate(spaces, 1):
        result.append(f"\n{i}. {space.get('space_name', '未知空間')}")

        if space.get('floor'):
            result.append(f"   樓層: {space['floor']}")

        result.append(f"   開放時間: {space.get('hours', '未提供')}")

        if space.get('notes'):
            result.append(f"   備註: {space['notes']}")

    result.append("")
    result.append("=" * 60)
    result.append(f"共 {len(spaces)} 個空間")
    result.append("=" * 60)

    return "\n".join(result)


@mcp.tool()
def search_library_space(space_name: str) -> str:
    """
    搜尋特定圖書館空間的開放時間

    Args:
        space_name: 空間名稱（支援部分匹配）

    Returns:
        str: 搜尋結果
    """
    data = load_library_hours()

    if "error" in data:
        return f"錯誤: {data['error']}\n{data.get('message', '')}"

    spaces = data.get('spaces', [])
    matches = []

    # 搜尋匹配的空間
    for space in spaces:
        if space_name.lower() in space.get('space_name', '').lower():
            matches.append(space)

    if not matches:
        return f"找不到包含「{space_name}」的空間\n\n可用的空間:\n" + "\n".join(
            f"- {s['space_name']}" for s in spaces
        )

    # 格式化輸出
    result = []
    result.append(f"搜尋「{space_name}」的結果:")
    result.append("=" * 60)

    for space in matches:
        result.append(f"\n空間名稱: {space.get('space_name')}")

        if space.get('floor'):
            result.append(f"樓層: {space['floor']}")

        result.append(f"開放時間: {space.get('hours', '未提供')}")

        if space.get('notes'):
            result.append(f"備註: {space['notes']}")

        result.append("-" * 60)

    result.append(f"\n找到 {len(matches)} 個匹配的空間")

    return "\n".join(result)


@mcp.tool()
def get_24hour_spaces() -> str:
    """
    取得 24 小時開放的空間資訊

    Returns:
        str: 24 小時開放空間列表
    """
    data = load_library_hours()

    if "error" in data:
        return f"錯誤: {data['error']}\n{data.get('message', '')}"

    spaces = data.get('spaces', [])
    all_day_spaces = []

    # 搜尋包含「24」或「24小時」的空間
    for space in spaces:
        hours = space.get('hours', '').lower()
        if '24' in hours or '全天' in hours or '全年無休' in hours:
            all_day_spaces.append(space)

    if not all_day_spaces:
        return "目前沒有 24 小時開放的空間資訊"

    # 格式化輸出
    result = []
    result.append("24 小時開放空間:")
    result.append("=" * 60)

    for space in all_day_spaces:
        result.append(f"\n空間名稱: {space.get('space_name')}")

        if space.get('floor'):
            result.append(f"樓層: {space['floor']}")

        result.append(f"開放時間: {space.get('hours')}")

        if space.get('notes'):
            result.append(f"備註: {space['notes']}")

        result.append("-" * 60)

    result.append(f"\n共 {len(all_day_spaces)} 個 24 小時開放空間")

    return "\n".join(result)


@mcp.tool()
def get_library_hours_summary() -> str:
    """
    取得圖書館開放時間摘要（簡要資訊）

    Returns:
        str: 簡要的開放時間資訊
    """
    data = load_library_hours()

    if "error" in data:
        return f"錯誤: {data['error']}\n{data.get('message', '')}"

    result = []
    result.append("圖書館開放時間摘要")
    result.append("=" * 60)
    result.append(f"更新時間: {data.get('last_updated', '未知')}")
    result.append("")

    spaces = data.get('spaces', [])
    for space in spaces:
        space_name = space.get('space_name', '未知')
        hours = space.get('hours', '未提供')
        result.append(f"• {space_name}: {hours}")

    result.append("")
    result.append("詳細資訊請使用 get_library_hours 工具")

    return "\n".join(result)


@mcp.tool()
def check_library_hours_update() -> str:
    """
    檢查圖書館開放時間資料的更新狀態

    Returns:
        str: 資料更新狀態資訊
    """
    data = load_library_hours()

    if "error" in data:
        return f"錯誤: {data['error']}\n{data.get('message', '')}"

    result = []
    result.append("資料更新狀態")
    result.append("=" * 60)

    last_updated = data.get('last_updated', '')
    if last_updated:
        result.append(f"最後更新時間: {last_updated}")

        try:
            update_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            now = datetime.now()
            delta = now - update_time.replace(tzinfo=None)

            result.append(f"距今: {delta.days} 天")

            if delta.days > 30:
                result.append("")
                result.append("⚠️  警告: 資料超過 30 天未更新")
                result.append("建議檢查圖書館網站是否有最新公告")
            elif delta.days > 7:
                result.append("")
                result.append("提醒: 資料已超過一週未更新")

        except Exception:
            result.append("無法解析更新時間")

    else:
        result.append("無更新時間資訊")

    result.append("")
    result.append(f"資料來源: {data.get('source_url', '未知')}")
    result.append(f"空間總數: {len(data.get('spaces', []))}")

    if data.get('note'):
        result.append("")
        result.append(f"備註: {data['note']}")

    return "\n".join(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
