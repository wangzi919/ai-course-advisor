# 教師專長查詢工具

中興大學教師資料查詢 MCP 工具，整合多個資料來源提供教師研究專長搜尋功能。

## 功能特色

- **多來源資料整合**：整合課程系統、ORCID、GRB 研究計畫、農業部計畫、機構典藏等資料
- **多維度搜尋**：支援按姓名、系所、學院、研究專長等條件搜尋
- **研究專長豐富**：結合論文關鍵字、計畫主題、研究領域等資訊

## 資料來源

| 來源 | 說明 | 資料量 |
|------|------|--------|
| 課程系統 | 從課程資料提取授課教師 | ~1,655 位 |
| ORCID | 學術研究人員識別碼系統 | ~542 位（有中文名）|
| GRB | 政府研究資訊系統計畫資料 | ~799 位主持人 |
| 農業部 | 農業科技計畫資料 | ~155 位主持人 |
| 機構典藏 | NCHU IR 論文主題標籤 | ~18,322 位作者 |

## MCP 工具函數

| 函數 | 說明 |
|------|------|
| `nchu_teacher_search` | 綜合搜尋（關鍵字、系所、學院）|
| `nchu_teacher_search_by_name` | 按姓名搜尋 |
| `nchu_teacher_search_by_department` | 按系所搜尋 |
| `nchu_teacher_search_by_college` | 按學院搜尋 |
| `nchu_teacher_search_by_research_area` | 按研究專長搜尋 |
| `nchu_teacher_get_detail` | 取得教師詳細資訊 |
| `nchu_teacher_list_departments` | 列出所有系所 |
| `nchu_teacher_list_colleges` | 列出所有學院 |
| `nchu_teacher_list_research_areas` | 列出研究專長 |

## 資料更新

資料檔案較大，未納入 Git 版控。請執行以下腳本重新生成：

```bash
# 1. 從課程系統提取教師
python scripts/extract_teachers_from_courses.py

# 2. 抓取 GRB 研究計畫（近 10 年）
python scripts/fetch_grb_data.py --years 10

# 3. 抓取農業部科技計畫
python scripts/fetch_moa_data.py

# 4. 抓取機構典藏資料
python scripts/fetch_nchu_ir_data.py --limit 500

# 5. 統一資料格式
python scripts/unify_teachers.py
```

## 使用範例

```python
# 搜尋研究專長包含「機器學習」的教師
nchu_teacher_search_by_research_area("機器學習")

# 搜尋資工系教師
nchu_teacher_search_by_department("資訊工程學系")

# 搜尋電資學院教師
nchu_teacher_search_by_college("電機資訊學院")

# 綜合搜尋
nchu_teacher_search(keywords="人工智慧", college="電機資訊學院")

# 列出所有研究專長
nchu_teacher_list_research_areas(limit=50)
```

## 檔案結構

```
teacher_tools/
├── teacher_search_api.py    # MCP 工具 API
└── README.md

scripts/
├── extract_teachers_from_courses.py  # 課程資料提取
├── fetch_grb_data.py                 # GRB 資料抓取
├── fetch_moa_data.py                 # 農業部資料抓取
├── fetch_nchu_ir_data.py             # 機構典藏資料抓取
└── unify_teachers.py                 # 資料統一

data/teachers/
├── raw/                    # 原始資料
├── teachers_all.json       # 統一後的教師資料（需生成）
└── ...                     # 其他資料檔（需生成）
```
