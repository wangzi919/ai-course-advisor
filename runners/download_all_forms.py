"""
下載所有教務處表單文件並按類型分類儲存

此腳本會：
1. 讀取 oaa_forms.json 中的所有表單資料
2. 下載所有檔案連結
3. 按照檔案類型（PDF, DOCX, ODT 等）分類儲存
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests
from typing import Dict, List

# 設定路徑
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "forms"
FORMS_JSON = DATA_DIR / "oaa_forms.json"
DOWNLOADS_DIR = DATA_DIR / "downloads"

# 建立下載目錄結構
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """
    清理檔案名稱，移除不合法字元

    Args:
        filename: 原始檔案名稱

    Returns:
        清理後的檔案名稱
    """
    # 移除或替換不合法字元
    illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in illegal_chars:
        filename = filename.replace(char, '_')

    # 限制檔案名稱長度
    name, ext = os.path.splitext(filename)
    if len(name) > 200:
        name = name[:200]

    return name + ext


def extract_filename_from_url(url: str) -> str:
    """
    從 URL 中提取檔案名稱

    Args:
        url: 檔案下載連結

    Returns:
        檔案名稱
    """
    # 解析 URL 參數
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # 嘗試從 'name' 參數取得檔名
    if 'name' in params and params['name']:
        return params['name'][0]

    # 如果沒有 name 參數，使用 file 參數
    if 'file' in params and params['file']:
        return params['file'][0]

    # 最後使用 URL 的最後部分
    return os.path.basename(parsed.path)


def download_file(url: str, save_path: Path, timeout: int = 30) -> bool:
    """
    下載檔案

    Args:
        url: 下載連結
        save_path: 儲存路徑
        timeout: 超時時間（秒）

    Returns:
        是否成功下載
    """
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        # 寫入檔案
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True

    except Exception as e:
        print(f"  ❌ 下載失敗: {e}")
        return False


def get_file_type_dir(file_type: str) -> Path:
    """
    根據檔案類型取得對應的目錄

    Args:
        file_type: 檔案類型（如 PDF, DOCX, ODT）

    Returns:
        目錄路徑
    """
    type_dir = DOWNLOADS_DIR / file_type.lower()
    type_dir.mkdir(parents=True, exist_ok=True)
    return type_dir


def download_all_forms() -> Dict[str, any]:
    """
    下載所有表單文件

    Returns:
        下載統計資訊
    """
    # 讀取表單資料
    print(f"📖 讀取表單資料: {FORMS_JSON}")
    with open(FORMS_JSON, 'r', encoding='utf-8') as f:
        forms_data = json.load(f)

    total_forms = forms_data['metadata']['total_count']
    print(f"📊 共有 {total_forms} 個表單\n")

    # 統計資訊
    stats = {
        'total_files': 0,
        'downloaded': 0,
        'failed': 0,
        'skipped': 0,
        'by_type': {}
    }

    # 遍歷所有表單
    for i, form in enumerate(forms_data['data'], 1):
        title = form['title']
        department = form['department']
        file_links = form.get('file_links', [])

        print(f"[{i}/{total_forms}] {title} ({department})")
        print(f"  📎 {len(file_links)} 個檔案")

        # 下載每個檔案
        for idx, link in enumerate(file_links):
            url = link['url']
            file_type = link['type']
            size = link.get('size', 'Unknown')

            stats['total_files'] += 1

            # 使用表單標題作為檔案名稱
            # 如果同一表單有多個相同類型檔案，加上序號
            if len([l for l in file_links if l['type'] == file_type]) > 1:
                # 計算當前是第幾個同類型檔案
                same_type_idx = len([l for l in file_links[:idx] if l['type'] == file_type]) + 1
                filename = f"{title}_{same_type_idx}.{file_type.lower()}"
            else:
                filename = f"{title}.{file_type.lower()}"

            filename = sanitize_filename(filename)

            # 決定儲存路徑
            type_dir = get_file_type_dir(file_type)
            save_path = type_dir / filename

            # 檢查檔案是否已存在
            if save_path.exists():
                print(f"  ⏭️  跳過 {file_type}: {filename} (已存在)")
                stats['skipped'] += 1
                continue

            # 下載檔案
            print(f"  ⬇️  下載 {file_type} ({size}): {filename}")

            if download_file(url, save_path):
                stats['downloaded'] += 1

                # 更新類型統計
                if file_type not in stats['by_type']:
                    stats['by_type'][file_type] = 0
                stats['by_type'][file_type] += 1

                print(f"  ✓ 儲存至: {save_path}")
            else:
                stats['failed'] += 1

            # 避免請求過快
            time.sleep(0.5)

        print()  # 空行分隔

    return stats


def print_summary(stats: Dict[str, any]):
    """
    列印下載摘要

    Args:
        stats: 統計資訊
    """
    print("\n" + "=" * 60)
    print("📊 下載摘要")
    print("=" * 60)
    print(f"總檔案數: {stats['total_files']}")
    print(f"✓ 成功下載: {stats['downloaded']}")
    print(f"⏭️  跳過（已存在）: {stats['skipped']}")
    print(f"❌ 失敗: {stats['failed']}")

    if stats['by_type']:
        print("\n按類型統計：")
        for file_type, count in sorted(stats['by_type'].items()):
            print(f"  {file_type}: {count} 個檔案")

    print("\n儲存位置:")
    print(f"  {DOWNLOADS_DIR}")

    # 列出各類型目錄
    if DOWNLOADS_DIR.exists():
        subdirs = [d for d in DOWNLOADS_DIR.iterdir() if d.is_dir()]
        for subdir in sorted(subdirs):
            file_count = len(list(subdir.glob('*')))
            print(f"  └─ {subdir.name}/  ({file_count} 個檔案)")

    print("=" * 60)


def main():
    """主程式"""
    print("\n🚀 開始下載所有教務處表單文件\n")

    # 檢查 JSON 檔案是否存在
    if not FORMS_JSON.exists():
        print(f"❌ 找不到表單資料檔案: {FORMS_JSON}")
        return

    # 執行下載
    try:
        stats = download_all_forms()
        print_summary(stats)

        print("\n✓ 所有下載完成！")

    except KeyboardInterrupt:
        print("\n\n⚠️  下載已中斷")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
