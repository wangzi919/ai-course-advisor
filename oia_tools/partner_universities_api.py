#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中興大學締約學校查詢工具（含一般合作、交換學生、雙聯學位等）"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nchu_partner_universities")

# --------------------------------------------------------------------------- #
# 資料載入                                                                      #
# --------------------------------------------------------------------------- #

def _load_data() -> list:
    json_file = Path(__file__).parent.parent / "data" / "oia" / "partner_universities.json"
    if not json_file.exists():
        raise FileNotFoundError(f"資料檔案不存在: {json_file}")
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)["data"]


UNIVERSITIES: list = _load_data()

# --------------------------------------------------------------------------- #
# MCP Tools                                                                    #
# --------------------------------------------------------------------------- #

@mcp.tool()
def nchu_partner_universities_overview() -> str:
    """取得中興大學締約學校的統計概覽，作為查詢締約學校的入口。

    適用情境：使用者詢問中興大學有多少締約學校、分布哪些洲別或國家時使用。
    取得概覽後，再呼叫 nchu_partner_universities_search() 以洲別、國家或合作項目篩選詳細結果。

    回傳 JSON 包含：
        - total: 獨立締約學校總數（同一學校多項合作只算一所）
        - total_agreements: 合作項目總筆數（同一學校多項合作各算一筆）
        - continents: 各洲別的獨立學校數（count）與合作筆數（agreements）
        - programs: 各合作項目類型的獨立學校數（count）與合作筆數（agreements）
    """
    continent_schools: dict = {}
    seen_by_continent: dict = {}
    for u in UNIVERSITIES:
        c = u["洲別"]
        if c not in continent_schools:
            continent_schools[c] = {"continent": u["continent"], "count": 0, "agreements": 0}
            seen_by_continent[c] = set()
        continent_schools[c]["agreements"] += 1
        if u["學校名稱"] not in seen_by_continent[c]:
            seen_by_continent[c].add(u["學校名稱"])
            continent_schools[c]["count"] += 1

    program_schools: dict = {}
    seen_by_program: dict = {}
    for u in UNIVERSITIES:
        p = u["合作項目"]
        if p not in program_schools:
            program_schools[p] = {"count": 0, "agreements": 0}
            seen_by_program[p] = set()
        program_schools[p]["agreements"] += 1
        if u["學校名稱"] not in seen_by_program[p]:
            seen_by_program[p].add(u["學校名稱"])
            program_schools[p]["count"] += 1

    return json.dumps({
        "total": len(set(u["學校名稱"] for u in UNIVERSITIES)),
        "total_agreements": len(UNIVERSITIES),
        "continents": [
            {"洲別": k, "continent": v["continent"], "count": v["count"], "agreements": v["agreements"]}
            for k, v in sorted(continent_schools.items(), key=lambda x: -x[1]["count"])
        ],
        "programs": [
            {"合作項目": k, "count": v["count"], "agreements": v["agreements"]}
            for k, v in sorted(program_schools.items(), key=lambda x: -x[1]["count"])
        ],
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def nchu_partner_universities_search(
    keyword: str = "",
    continent: str = "",
    country: str = "",
    program: str = "",
    limit: int = 5,
    offset: int = 0,
) -> str:
    """搜尋中興大學締約學校。

    適用情境：使用者想知道中興大學與哪些學校有合作關係、可以交換的學校、或特定國家/洲別的合作學校時使用。
    所有篩選參數皆為選填，可單獨或組合使用。

    重要：若未提供任何篩選條件，請先呼叫 nchu_partner_universities_overview() 取得洲別與合作項目統計，
    再詢問使用者要查哪個洲別或國家，避免一次回傳過多資料。

    參數：
        keyword: 關鍵字，搜尋學校名稱（中英文）或國家名稱（留空則不篩選）
        continent: 洲別篩選，可使用中文（如 \"亞洲\"、\"歐洲\"、\"美洲\"、\"大洋洲\"）
                   或英文（如 \"Asia\"、\"Europe\"、\"Americas\"、\"Oceania\"）
        country: 國家篩選，可使用中文（如 \"日本\"、\"美國\"）或英文（如 \"Japan\"、\"USA\"）
        program: 合作項目篩選，可使用中文（如 \"交換學生\"、\"雙聯\"、\"一般\"）
                 或英文（如 \"Student Exchange\"、\"Dual Degree\"、\"MOU\"）
        limit: 每次回傳筆數上限（預設 5）
        offset: 從第幾筆開始回傳（預設 0，用於翻頁）

    回傳 JSON 包含：
        - total: 符合篩選條件的獨立學校總數
        - offset: 本次從第幾筆開始
        - limit: 本次上限
        - has_more: 是否還有更多結果（true 時可用 offset + limit 繼續查詢）
        - universities: 本頁締約學校列表，每筆已合併同校多筆合作（合作項目與本校合作範圍為列表）

    重要：回傳的 universities 列表中每一筆都必須完整列出給使用者，不可省略、不可用「...等」代替。
    若 has_more 為 true，告知使用者還有更多結果並詢問是否繼續查看。
    """
    results = UNIVERSITIES

    if keyword:
        kw = keyword.lower()
        results = [
            u for u in results
            if any(kw in str(u.get(f, "")).lower()
                   for f in ("學校名稱", "institution", "國家", "country"))
        ]
    if continent:
        cont_lower = continent.lower()
        results = [u for u in results if cont_lower in u["洲別"].lower() or cont_lower in u["continent"].lower()]
    if country:
        c_lower = country.lower()
        results = [u for u in results if c_lower in u["國家"].lower() or c_lower in u["country"].lower()]
    if program:
        p_lower = program.lower()
        results = [u for u in results if p_lower in u["合作項目"].lower() or p_lower in u["program"].lower()]

    # 依學校名稱去重，合作項目與本校合作範圍合併為列表
    merged: dict = {}
    for u in results:
        name = u["學校名稱"]
        if name not in merged:
            merged[name] = {
                "學校名稱": name,
                "institution": u["institution"],
                "國家": u["國家"],
                "country": u["country"],
                "洲別": u["洲別"],
                "continent": u["continent"],
                "簽約時間": u["簽約時間"],
                "學校網址": u["學校網址"],
                "合作項目": [],
                "本校合作範圍": [],
            }
        if u["合作項目"] not in merged[name]["合作項目"]:
            merged[name]["合作項目"].append(u["合作項目"])
        if u["本校合作範圍"] not in merged[name]["本校合作範圍"]:
            merged[name]["本校合作範圍"].append(u["本校合作範圍"])

    unique_results = list(merged.values())
    total = len(unique_results)
    limit = min(limit, 5)
    page = unique_results[offset: offset + limit]

    return json.dumps({
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "universities": page,
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
