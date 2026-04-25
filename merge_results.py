import os
import json
from collections import defaultdict

def merge_json_files(base_dir="results/ste", output_file="results/ste/combined_results.json"):
    combined_data = defaultdict(list)
    file_count = 0
    total_sessions = 0

    print(f"Start scanning directory: {base_dir}")

    # 遞迴走訪目錄
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            # 只處理 .json 檔案，且跳過輸出檔案本身
            if file.endswith(".json") and file != os.path.basename(output_file):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 判斷讀入的資料格式 (清單或字典)
                    if isinstance(data, list):
                        sessions = data
                        for item in sessions:
                            # 優先從 item 中取得 api_name
                            api_name = item.get("api_name")
                            
                            # 如果 item 裡沒寫 api_name，則嘗試從資料夾名稱推斷
                            if not api_name:
                                parent_dir = os.path.basename(root)
                                if parent_dir != "ste":
                                    api_name = parent_dir
                                else:
                                    api_name = "unknown_api"

                            # 重新建構 item，符合用戶範例格式
                            clean_item = {
                                "query": item.get("query", ""),
                                "chains": item.get("chains", []),
                                "reflection": item.get("reflection", "No")
                            }
                            
                            combined_data[api_name].append(clean_item)
                            total_sessions += 1

                    elif isinstance(data, dict):
                        # 如果已經是字典格式 (api_name: list)，則直接合併
                        for api_name, items in data.items():
                            combined_data[api_name].extend(items)
                            total_sessions += len(items)
                    else:
                        continue
                    
                    file_count += 1
                    print(f"Done processing: {file_path}")
                
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    # 寫入最終檔案
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)

    print(f"\nMerge completed!")
    print(f"Total files processed: {file_count}")
    print(f"Total sessions merged: {total_sessions}")
    print(f"Result saved to: {output_file}")

if __name__ == "__main__":
    merge_json_files()
