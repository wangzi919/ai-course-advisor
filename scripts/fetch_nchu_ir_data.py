#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從中興大學機構典藏系統 (NCHU IR) 取得研究論文資料

透過 OAI-PMH 協議批次取得論文的作者和研究主題關鍵字，
用於補充教師的研究專長資訊。

資料來源: https://ir.lib.nchu.edu.tw/
OAI-PMH: https://ir.lib.nchu.edu.tw/oai/request

使用方式：
    python scripts/fetch_nchu_ir_data.py
    python scripts/fetch_nchu_ir_data.py --limit 1000  # 限制筆數
"""

import json
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx

# 路徑設定
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "teachers" / "nchu_ir_data.json"

# OAI-PMH 設定
OAI_BASE_URL = "https://ir.lib.nchu.edu.tw/oai/request"
METADATA_PREFIX = "oai_dc"

# 學院 Set 對照
COLLEGE_SETS = {
    "com_11455_2": "工學院",
    "com_11455_10554": "文學院",
    "com_11455_10908": "獸醫學院",
    "com_11455_13116": "理學院",
    "com_11455_17294": "法政學院",
    "com_11455_17330": "生命科學院",
    "com_11455_18177": "管理學院",
    "com_11455_24114": "農業暨自然資源學院",
}

# XML 命名空間
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}


def fetch_oai_records(
    client: httpx.Client,
    set_spec: Optional[str] = None,
    resumption_token: Optional[str] = None,
) -> tuple[List[Dict], Optional[str]]:
    """從 OAI-PMH 取得記錄

    Args:
        client: HTTP 客戶端
        set_spec: 集合識別碼
        resumption_token: 續傳 token

    Returns:
        tuple: (記錄列表, 下一個 resumption token)
    """
    if resumption_token:
        url = f"{OAI_BASE_URL}?verb=ListRecords&resumptionToken={resumption_token}"
    else:
        url = f"{OAI_BASE_URL}?verb=ListRecords&metadataPrefix={METADATA_PREFIX}"
        if set_spec:
            url += f"&set={set_spec}"

    resp = client.get(url)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)

    # 檢查錯誤
    error = root.find(".//oai:error", NS)
    if error is not None:
        return [], None

    records = []
    for record in root.findall(".//oai:record", NS):
        header = record.find("oai:header", NS)
        if header is not None and header.get("status") == "deleted":
            continue

        metadata = record.find(".//oai_dc:dc", NS)
        if metadata is None:
            continue

        # 提取欄位
        title = metadata.find("dc:title", NS)
        creators = metadata.findall("dc:creator", NS)
        subjects = metadata.findall("dc:subject", NS)
        date = metadata.find("dc:date", NS)

        rec = {
            "title": title.text if title is not None else "",
            "creators": [c.text for c in creators if c.text],
            "subjects": [s.text for s in subjects if s.text],
            "date": date.text if date is not None else "",
        }
        records.append(rec)

    # 取得 resumption token
    token_elem = root.find(".//oai:resumptionToken", NS)
    next_token = None
    if token_elem is not None and token_elem.text:
        next_token = token_elem.text

    return records, next_token


def fetch_nchu_ir_data(
    limit: int = 0,
    output_file: Path = OUTPUT_FILE,
) -> Dict[str, Any]:
    """抓取中興大學機構典藏資料

    Args:
        limit: 每個學院的記錄數限制，0 表示全部
        output_file: 輸出檔案

    Returns:
        Dict: 處理結果摘要
    """
    print("=" * 60)
    print("從中興大學機構典藏系統抓取研究資料")
    print("=" * 60)
    print(f"開始時間: {datetime.now().isoformat()}")
    print(f"OAI-PMH: {OAI_BASE_URL}")
    print()

    client = httpx.Client(timeout=60, verify=False)

    try:
        all_records = []
        author_subjects: Dict[str, Set[str]] = defaultdict(set)
        author_count: Dict[str, int] = defaultdict(int)

        for set_spec, college in COLLEGE_SETS.items():
            print(f"\n【{college}】")
            print("-" * 40)

            college_records = []
            token = None
            batch = 0

            while True:
                batch += 1
                records, token = fetch_oai_records(client, set_spec, token)

                if not records:
                    break

                college_records.extend(records)
                print(f"  批次 {batch}: 取得 {len(records)} 筆 (累計 {len(college_records)})")

                # 處理作者和主題
                for rec in records:
                    for creator in rec.get("creators", []):
                        # 清理作者名稱
                        name = creator.strip()
                        if name and len(name) >= 2:
                            author_count[name] += 1
                            for subject in rec.get("subjects", []):
                                if subject:
                                    author_subjects[name].add(subject)

                # 檢查限制
                if limit > 0 and len(college_records) >= limit:
                    print(f"  達到限制 {limit}，停止")
                    break

                if not token:
                    break

                time.sleep(0.5)  # 禮貌性延遲

            all_records.extend(college_records)
            print(f"  {college} 共 {len(college_records)} 筆")

        print()
        print("=" * 60)
        print(f"總記錄數: {len(all_records)}")
        print(f"不重複作者: {len(author_subjects)}")

        # 整理作者資料
        authors_data = {}
        for name, subjects in author_subjects.items():
            if author_count[name] >= 2:  # 至少有 2 篇論文
                authors_data[name] = {
                    "name": name,
                    "publication_count": author_count[name],
                    "subjects": list(subjects),
                }

        print(f"有效作者 (>=2篇): {len(authors_data)}")

        # 統計
        total_subjects = sum(len(a["subjects"]) for a in authors_data.values())
        print(f"總主題標籤數: {total_subjects}")

        # 顯示主題最多的作者
        print("\n論文數最多的作者:")
        top_authors = sorted(authors_data.values(), key=lambda x: x["publication_count"], reverse=True)
        for a in top_authors[:10]:
            print(f"  {a['name']}: {a['publication_count']} 篇, {len(a['subjects'])} 個主題")

        # 儲存結果
        output_data = {
            "metadata": {
                "fetched_at": datetime.now().isoformat(),
                "source": "中興大學機構典藏系統",
                "source_url": "https://ir.lib.nchu.edu.tw/",
                "oai_pmh_url": OAI_BASE_URL,
                "total_records": len(all_records),
                "total_authors": len(authors_data),
                "total_subjects": total_subjects,
            },
            "authors": authors_data,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n已儲存至: {output_file}")
        print(f"結束時間: {datetime.now().isoformat()}")

        return {
            "success": True,
            "total_records": len(all_records),
            "total_authors": len(authors_data),
            "output_path": str(output_file),
        }

    finally:
        client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="從中興大學機構典藏抓取研究資料")
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="每個學院的記錄數限制，0 表示全部（預設：500）",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="輸出檔案路徑",
    )

    args = parser.parse_args()

    output = Path(args.output) if args.output else OUTPUT_FILE

    result = fetch_nchu_ir_data(limit=args.limit, output_file=output)

    if not result.get("success", False):
        print(f"\n錯誤: {result.get('error', '未知錯誤')}")
        sys.exit(1)
