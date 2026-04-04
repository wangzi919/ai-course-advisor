#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從 GRB 政府研究資訊系統下載研究計畫資料並篩選中興大學

GRB (Government Research Bulletin) 收錄民國 82 年迄今的政府研究計畫資料。
本腳本會下載 XML 資料，篩選出中興大學的研究計畫。

使用方式：
    python scripts/fetch_grb_data.py
    python scripts/fetch_grb_data.py --years 3  # 只下載最近 3 年
"""

import io
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# 路徑設定
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "teachers" / "grb_nchu_projects.json"

# GRB 伺服器 URL 模板
GRB_BASE_URL = "https://manager.grb.gov.tw"

# 目前民國年
CURRENT_ROC_YEAR = datetime.now().year - 1911


def get_grb_url(roc_year: int) -> str:
    """取得特定民國年度的 GRB 資料 URL"""
    return f"{GRB_BASE_URL}/GRB_{roc_year}_xml.zip"


def is_nchu_project(org_name: str) -> bool:
    """檢查是否為中興大學的研究計畫"""
    if not org_name:
        return False
    return "中興大學" in org_name or "中興" in org_name and "大學" in org_name


def download_and_parse_grb_xml(
    client: httpx.Client,
    roc_year: int,
) -> List[Dict[str, Any]]:
    """下載並解析 GRB XML 資料

    Args:
        client: HTTP 客戶端
        roc_year: 民國年度

    Returns:
        List[Dict]: 該年度所有中興大學的研究計畫
    """
    url = get_grb_url(roc_year)
    print(f"  民國 {roc_year} 年 ({roc_year + 1911}): ", end="", flush=True)

    try:
        resp = client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}")
            return []

        # 解壓 ZIP
        projects = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for filename in zf.namelist():
                if filename.endswith(".xml"):
                    with zf.open(filename) as f:
                        # 嘗試不同編碼
                        content = None
                        raw_content = f.read()
                        for encoding in ["utf-8", "big5", "cp950"]:
                            try:
                                content = raw_content.decode(encoding)
                                break
                            except UnicodeDecodeError:
                                continue

                        if content is None:
                            print(f"解碼失敗")
                            continue

                        # 解析 XML
                        try:
                            root = ET.fromstring(content)
                        except ET.ParseError as e:
                            print(f"XML 解析錯誤: {e}")
                            continue

                        # 遍歷所有記錄（可能是 row 或 GRB05）
                        total = 0
                        nchu_count = 0
                        for row in root:
                            total += 1
                            org = row.find("EXCU_ORGAN_NAME")
                            org_text = org.text if org is not None else ""

                            if is_nchu_project(org_text):
                                nchu_count += 1
                                project = {
                                    "project_id": _get_text(row, "PROJKEY"),
                                    "plan_no": _get_text(row, "PLAN_NO"),
                                    "project_name": _get_text(row, "PNCH_DESC"),
                                    "project_name_en": _get_text(row, "PENG_DESC"),
                                    "year_roc": roc_year,
                                    "year": roc_year + 1911,
                                    "organization": org_text,
                                    "pi_name": _get_text(row, "PI"),
                                    "researchers": _get_text(row, "RESEARCHER"),
                                    "research_field": _get_text(row, "RESEARCH_FIELD"),
                                    "research_type": _get_text(row, "RESEARCH_TYPE"),
                                    "research_attribute": _get_text(row, "RESEARCH_ATTRIBUTE"),
                                    "keywords_zh": _get_text(row, "KEYWORD_C"),
                                    "keywords_en": _get_text(row, "KEYWORD_E"),
                                    "funding_agency": _get_text(row, "PLAN_ORGAN_CODE"),
                                    "budget_k": _get_text(row, "PLAN_AMT"),
                                    "start_ym": _get_text(row, "PERIOD_STYM"),
                                    "end_ym": _get_text(row, "PERIOD_ENYM"),
                                    "abstract_zh": _get_text(row, "ABSTRACT_C"),
                                }
                                projects.append(project)

                        print(f"{nchu_count} 筆 (共 {total} 筆)")

        return projects

    except Exception as e:
        print(f"錯誤: {e}")
        return []


def _get_text(element: ET.Element, tag: str) -> str:
    """從 XML 元素取得子元素的文字內容"""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def fetch_nchu_grb_projects(
    years: int = 3,
    output_file: Path = OUTPUT_FILE
) -> Dict[str, Any]:
    """抓取中興大學的 GRB 研究計畫資料

    Args:
        years: 下載最近幾年的資料，0 表示全部（民國 82 年起）
        output_file: 輸出檔案

    Returns:
        Dict: 處理結果摘要
    """
    print("=" * 60)
    print("從 GRB 抓取中興大學研究計畫資料")
    print("=" * 60)
    print(f"開始時間: {datetime.now().isoformat()}")
    print()

    # 計算年份範圍
    if years > 0:
        start_year = CURRENT_ROC_YEAR - years + 1
        end_year = CURRENT_ROC_YEAR
    else:
        start_year = 82  # 民國 82 年起
        end_year = CURRENT_ROC_YEAR

    year_range = list(range(start_year, end_year + 1))
    print(f"下載年份: 民國 {start_year} 年 ~ {end_year} 年 ({len(year_range)} 年)")
    print()

    client = httpx.Client(timeout=120, follow_redirects=True)

    try:
        all_projects = []

        for roc_year in year_range:
            projects = download_and_parse_grb_xml(client, roc_year)
            all_projects.extend(projects)

        print()
        print(f"處理完成: {len(all_projects)} 筆中興大學研究計畫")

        # 按年份和主持人整理統計
        by_year = {}
        by_pi = {}
        research_fields = set()
        keywords_set = set()

        for project in all_projects:
            year = project.get("year")
            if year:
                by_year[year] = by_year.get(year, 0) + 1

            pi = project.get("pi_name", "").strip()
            if pi:
                if pi not in by_pi:
                    by_pi[pi] = []
                by_pi[pi].append(project)

            field = project.get("research_field", "").strip()
            if field:
                research_fields.add(field)

            # 收集關鍵字
            kw = project.get("keywords_zh", "")
            if kw:
                for k in kw.replace("；", ";").replace("、", ";").split(";"):
                    k = k.strip()
                    if k:
                        keywords_set.add(k)

        print()
        print("各年度計畫數:")
        for year in sorted(by_year.keys(), reverse=True):
            print(f"  {year}: {by_year[year]} 件")

        print()
        print(f"共有 {len(by_pi)} 位計畫主持人")
        print(f"研究領域: {len(research_fields)} 種")
        print(f"關鍵詞: {len(keywords_set)} 個")

        # 儲存結果
        output_data = {
            "metadata": {
                "fetched_at": datetime.now().isoformat(),
                "source": "GRB 政府研究資訊系統",
                "source_url": GRB_BASE_URL,
                "year_range": {
                    "start_roc": start_year,
                    "end_roc": end_year,
                    "start": start_year + 1911,
                    "end": end_year + 1911,
                },
                "total_projects": len(all_projects),
                "unique_pis": len(by_pi),
                "research_fields": len(research_fields),
                "unique_keywords": len(keywords_set),
            },
            "projects": all_projects,
            "by_pi": {
                pi: {
                    "name": pi,
                    "project_count": len(projects),
                    "years": sorted(set(p.get("year") for p in projects if p.get("year"))),
                    "fields": list(set(p.get("research_field") for p in projects if p.get("research_field"))),
                    "keywords": list(set(
                        k.strip()
                        for p in projects
                        for k in (p.get("keywords_zh", "") or "").replace("；", ";").replace("、", ";").split(";")
                        if k.strip()
                    )),
                }
                for pi, projects in by_pi.items()
            },
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n已儲存至: {output_file}")
        print(f"結束時間: {datetime.now().isoformat()}")

        return {
            "success": True,
            "total_projects": len(all_projects),
            "unique_pis": len(by_pi),
            "output_path": str(output_file),
        }

    finally:
        client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="從 GRB 抓取中興大學研究計畫資料")
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="下載最近幾年的資料，0 表示全部（預設：3）",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="輸出檔案路徑",
    )

    args = parser.parse_args()

    output = Path(args.output) if args.output else OUTPUT_FILE

    result = fetch_nchu_grb_projects(years=args.years, output_file=output)

    if not result.get("success", False):
        print(f"\n錯誤: {result.get('error', '未知錯誤')}")
        sys.exit(1)
