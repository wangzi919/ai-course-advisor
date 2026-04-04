#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從農業部開放資料平臺下載科技計畫資料並篩選中興大學

資料來源: https://data.gov.tw/dataset/159734
API: https://data.moa.gov.tw/Service/OpenData/TransService.aspx

使用方式：
    python scripts/fetch_moa_data.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

# 路徑設定
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "teachers" / "moa_nchu_projects.json"

# 農業部開放資料 API
MOA_API_URL = "https://data.moa.gov.tw/Service/OpenData/TransService.aspx?UnitId=GGKERB9kPQzJ&IsTransData=1"


def is_nchu_project(project: Dict[str, Any]) -> bool:
    """檢查是否為中興大學的計畫"""
    director_dept = project.get("director_dept", "")
    return "中興大學" in director_dept or "中興" in director_dept


def fetch_moa_projects() -> Dict[str, Any]:
    """抓取農業部科技計畫資料

    Returns:
        Dict: 處理結果摘要
    """
    print("=" * 60)
    print("從農業部開放資料平臺抓取科技計畫資料")
    print("=" * 60)
    print(f"開始時間: {datetime.now().isoformat()}")
    print()

    client = httpx.Client(timeout=120)

    try:
        print(f"下載資料...")
        resp = client.get(MOA_API_URL)
        resp.raise_for_status()

        all_projects = resp.json()
        print(f"總計畫數: {len(all_projects)}")

        # 篩選中興大學的計畫
        nchu_projects = []
        for p in all_projects:
            if is_nchu_project(p):
                project = {
                    "year": p.get("year"),
                    "project_id": p.get("cpid", ""),
                    "project_name": p.get("cname", ""),
                    "category": p.get("category", ""),
                    "type": p.get("type2", ""),
                    "property": p.get("prop", ""),
                    "method": p.get("method", ""),
                    "field": p.get("field", ""),
                    "goal": p.get("goal", ""),
                    "funding_dept": p.get("dept", ""),
                    "organization": p.get("director_dept", ""),
                    "pi_name": p.get("director_name", ""),
                    "moa_budget": p.get("coa_price", 0),
                    "other_budget": p.get("other_price", 0),
                    "total_budget": p.get("total", 0),
                    "benefit": p.get("benefit", ""),
                }
                nchu_projects.append(project)

        print(f"中興大學計畫: {len(nchu_projects)} 筆")

        # 按年份和主持人整理統計
        by_year = {}
        by_pi = {}
        fields = set()

        for project in nchu_projects:
            year = project.get("year")
            if year:
                by_year[year] = by_year.get(year, 0) + 1

            pi = project.get("pi_name", "").strip()
            if pi:
                if pi not in by_pi:
                    by_pi[pi] = []
                by_pi[pi].append(project)

            field = project.get("field", "").strip()
            if field:
                fields.add(field)

        print()
        print("各年度計畫數:")
        for year in sorted(by_year.keys(), reverse=True):
            print(f"  {year}: {by_year[year]} 件")

        print()
        print(f"共有 {len(by_pi)} 位計畫主持人")
        print(f"研究領域: {len(fields)} 種")

        # 顯示研究領域分布
        print()
        print("研究領域分布:")
        field_count = {}
        for p in nchu_projects:
            f = p.get("field", "")
            if f:
                field_count[f] = field_count.get(f, 0) + 1
        for f, c in sorted(field_count.items(), key=lambda x: -x[1])[:10]:
            print(f"  {f}: {c} 件")

        # 儲存結果
        output_data = {
            "metadata": {
                "fetched_at": datetime.now().isoformat(),
                "source": "農業部開放資料平臺",
                "source_url": "https://data.gov.tw/dataset/159734",
                "api_url": MOA_API_URL,
                "total_projects": len(nchu_projects),
                "unique_pis": len(by_pi),
                "fields": len(fields),
            },
            "projects": nchu_projects,
            "by_pi": {
                pi: {
                    "name": pi,
                    "project_count": len(projects),
                    "years": sorted(set(p.get("year") for p in projects if p.get("year"))),
                    "fields": list(set(p.get("field") for p in projects if p.get("field"))),
                    "total_budget": sum(p.get("total_budget", 0) for p in projects),
                }
                for pi, projects in by_pi.items()
            },
        }

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n已儲存至: {OUTPUT_FILE}")
        print(f"結束時間: {datetime.now().isoformat()}")

        return {
            "success": True,
            "total_projects": len(nchu_projects),
            "unique_pis": len(by_pi),
            "output_path": str(OUTPUT_FILE),
        }

    finally:
        client.close()


if __name__ == "__main__":
    result = fetch_moa_projects()

    if not result.get("success", False):
        print(f"\n錯誤: {result.get('error', '未知錯誤')}")
        sys.exit(1)
