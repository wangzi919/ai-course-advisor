#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中興大學雙聯學位計畫查詢工具（締約說明與締約學校列表）"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nchu_dual_degree")

# --------------------------------------------------------------------------- #
# 資料載入                                                                      #
# --------------------------------------------------------------------------- #

def _load_data() -> dict:
    json_file = Path(__file__).parent.parent / "data" / "oia" / "dual_degree.json"
    if not json_file.exists():
        raise FileNotFoundError(f"資料檔案不存在: {json_file}")
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)


_RAW = _load_data()
UNIVERSITIES: list = _RAW["data"]
INFO: dict = _RAW["info"]

# --------------------------------------------------------------------------- #
# MCP Tools                                                                    #
# --------------------------------------------------------------------------- #

@mcp.tool()
def nchu_dual_degree_get_info() -> str:
    """取得中興大學雙聯學位計畫的締約說明與相關法規連結。

    適用情境：使用者詢問雙聯學位的申請程序、合約內容、注意事項或相關法規時使用。
    若要查詢有哪些締約學校，請改用 nchu_dual_degree_list_continents() 或 nchu_dual_degree_search()。

    回傳 JSON 包含：
        - sections: 各段落說明（締約對象之評估、合約內容、注意事項）
        - regulations: 相關法規連結列表（title、url）
    """
    return json.dumps(INFO, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_dual_degree_list_continents() -> str:
    """列出各洲締約學校數量，作為查詢雙聯學位締約學校的入口。

    這是探索締約學校的入口工具，了解各洲分布後，
    再呼叫 nchu_dual_degree_search() 以洲別或國家篩選詳細結果。

    回傳 JSON 包含：
        - total: 締約學校總數
        - active: 有效（未過期）學校數
        - continents: 各洲名稱、總數與有效數量
    """
    continents: dict = {}
    for u in UNIVERSITIES:
        c = u["洲屬"]
        if c not in continents:
            continents[c] = {"total": 0, "active": 0}
        continents[c]["total"] += 1
        if not u["已過期"]:
            continents[c]["active"] += 1

    return json.dumps({
        "total": len(UNIVERSITIES),
        "active": sum(1 for u in UNIVERSITIES if not u["已過期"]),
        "continents": [
            {"洲屬": k, **v}
            for k, v in sorted(continents.items(), key=lambda x: -x[1]["total"])
        ],
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_dual_degree_search(
    keyword: str = "",
    continent: str = "",
    country: str = "",
    degree: str = "",
    active_only: bool = False,
    program_type: str = "",
) -> str:
    """搜尋中興大學雙聯學位締約學校。

    適用情境：使用者想知道有哪些國家或學校可以申請雙聯學位時使用。
    所有參數皆為選填，可單獨或組合使用。

    參數：
        keyword: 關鍵字，搜尋學校名稱、國家、系所（留空則不篩選）
        continent: 洲別，例如 "亞洲"、"歐洲"、"美洲"、"大洋洲"
        country: 國家名稱，例如 "日本"、"美國"、"法國"
        degree: 學位類型，例如 "學士"、"碩士"、"博士"
        active_only: 是否只顯示未過期的有效合約（預設 False 顯示全部）
        program_type: 計畫類型，"dual_degree"（雙聯學位）或 "3_plus_x"（3+X 學位）

    回傳 JSON 包含：
        - total: 符合筆數
        - universities: 締約學校列表
    """
    results = UNIVERSITIES

    if keyword:
        kw = keyword.lower()
        results = [
            u for u in results
            if any(kw in str(u.get(f, "")).lower()
                   for f in ("學校名稱", "國家", "系所"))
        ]
    if continent:
        results = [u for u in results if continent in u["洲屬"]]
    if country:
        results = [u for u in results if country in u["國家"]]
    if degree:
        results = [u for u in results if degree in u["學位"]]
    if active_only:
        results = [u for u in results if not u["已過期"]]
    if program_type:
        results = [u for u in results if u["program_type"] == program_type]

    return json.dumps({
        "total": len(results),
        "universities": results,
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
