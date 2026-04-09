# 非洲豬瘟緊急應變措施手冊 MCP Tools

本專案基於「臺中市防範非洲豬瘟緊急應變措施手冊」建立了一組 Model Context Protocol (MCP) 工具，提供結構化的方式來查詢和存取手冊中的防疫資訊。

## 專案結構

```
/user_data/library/
├── asf_tool/
│   ├── asf_emergency_response_api.py
│   ├── test_asf_api.py
│   └── ASF_EMERGENCY_RESPONSE_README.md
└── data/
    └── asf/
        └── taichung_asf_emergency_response_manual/
            ├── chapter_1_foreword.json
            ├── chapter_2_asf_introduction.json
            ├── chapter_3_response_center_framework.json
            ├── chapter_4_prevention.json
            ├── chapter_5_preparedness.json
            ├── chapter_6_response.json
            ├── asf_preliminary_screening_sop.json
            ├── asf_suspected_case_sampling_sop.json
            └── farm_inspection_checklist.json
```

## 功能特色

### 1. 結構化資料存取
- 自動載入手冊的 6 個主要章節
- 整合 3 個標準作業程序 (SOP)
- 提供統一的 API 介面查詢

### 2. 多種查詢方式
- **章節查詢**: 依章節編號查詢完整內容
- **主題查詢**: 依特定主題查詢相關資訊
- **關鍵字搜尋**: 全文搜尋功能
- **SOP 查詢**: 查詢標準作業程序

## 可用的 MCP 工具

### 1. `asf_manual_overview()`
取得手冊總覽，包括所有章節和 SOP 的摘要資訊。

### 2. `asf_chapter_content(chapter)`
查詢特定章節的完整內容。
- **參數**: `chapter` - 章節編號 (壹, 貳, 參, 肆, 伍, 陸)

### 3. `asf_basic_info(query_type)`
查詢非洲豬瘟基本資訊。
- **參數**: `query_type` - 查詢類型
  - `definition`: 非洲豬瘟定義
  - `symptoms`: 臨床症狀
  - `transmission`: 傳播途徑
  - `virus_characteristics`: 病毒特性
  - `pathology`: 病理學
  - `epidemiology`: 流行病學
  - `global_situation`: 全球疫情概況
  - `survival_conditions`: 病毒存活條件

### 4. `asf_response_center_info(query_type)`
查詢災害應變中心相關資訊。
- **參數**: `query_type` - 查詢類型
  - `structure`: 應變中心組織架構
  - `management_levels`: 分級管理機制
  - `central_groups`: 中央應變中心各組職掌
  - `local_structure`: 地方應變中心結構
  - `activation_criteria`: 啟動標準

### 5. `asf_sop_details(sop_type)`
查詢標準作業程序詳細內容。
- **參數**: `sop_type` - SOP 類型
  - `screening`: 初篩檢測 SOP
  - `sampling`: 疑似病例採樣 SOP
  - `inspection`: 豬場疫情訪查確認表

### 6. `asf_prevention_measures(measure_type)`
查詢預防措施相關資訊。
- **參數**: `measure_type` - 措施類型
  - `all`: 所有預防措施
  - `border_control`: 邊境管制
  - `farm_biosecurity`: 養豬場生物安全
  - `quarantine`: 檢疫措施
  - `public_awareness`: 宣導教育

### 7. `asf_response_measures(response_type)`
查詢應變措施相關資訊。
- **參數**: `response_type` - 應變類型
  - `all`: 所有應變措施
  - `outbreak_response`: 疫情爆發應變
  - `containment`: 疫情圍堵
  - `disposal`: 撲殺處置
  - `disinfection`: 消毒清潔
  - `movement_control`: 移動管制

### 8. `asf_preparedness_measures()`
查詢整備措施相關資訊。

### 9. `asf_search_content(keyword)`
在手冊內容中搜尋關鍵字。
- **參數**: `keyword` - 搜尋關鍵字

## 使用範例

### Python 直接使用
```python
from asf_emergency_response_api import *

# 取得手冊總覽
overview = asf_manual_overview()
print(f"手冊包含 {len(overview['chapters'])} 個章節")

# 查詢非洲豬瘟定義
definition = asf_basic_info("definition")
print(definition['content'][:200])

# 搜尋特定關鍵字
results = asf_search_content("病毒")
print(f"找到 {results['total_matches']} 個匹配結果")
```

### MCP Server 使用
```python
# 作為 MCP Server 運行
if __name__ == "__main__":
    mcp.run()
```

## 測試

執行測試腳本來驗證所有功能：

```bash
python test_asf_api.py
```

測試腳本會驗證：
- 資料載入功能
- 所有 API 工具的基本功能
- 錯誤處理機制
- 搜尋功能

## 技術特點

### 1. 模組化設計
- 清晰的函數分離
- 統一的錯誤處理
- 可擴充的架構

### 2. 資料完整性
- 自動驗證資料檔案存在
- 處理缺失的章節或 SOP
- 提供有意義的錯誤訊息

### 3. 搜尋功能
- 全文搜尋所有章節和 SOP
- 智能內容截取（避免過長輸出）
- 結構化的搜尋結果

### 4. 使用者友善
- 中文介面
- 詳細的參數說明
- 直觀的函數命名

## 支援的資料格式

本工具支援的 JSON 資料結構：

```json
{
  "title": "文件標題",
  "subtitle": "章節標題",
  "summary": "內容摘要",
  "sections": [
    {
      "heading": "段落標題",
      "content": "段落內容"
    }
  ]
}
```

## 未來擴充

可能的擴充方向：
1. 新增更多專業查詢功能
2. 支援多語言查詢
3. 整合外部防疫資料源
4. 新增資料視覺化功能
5. 支援即時疫情更新

## 授權

本專案基於臺中市政府公開的防疫資料建立，僅供學習和研究使用。

---

*建立日期: 2025年10月27日*
*版本: 1.0*