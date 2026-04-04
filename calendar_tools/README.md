# 學校行事曆工具 (School Calendar Tools)

本目錄包含中興大學學校行事曆的爬蟲和 API 工具。

## 功能概述

### 資料來源
- **網址**: https://www.nchu.edu.tw/calendar/
- **資料類型**: 中興大學 114 學年度行事曆（第 1 和第 2 學期）
- **更新頻率**: 建議每日或每週更新一次

### 檔案結構

```
calendar_tools/
├── school_calendar_api.py    # FastMCP API 工具
└── README.md                  # 本文件
```

## 資料格式

### JSON 資料結構

**單一日期事件範例**：
```json
{
  "semester": "114-1",
  "start_date": "2025-08-01",
  "end_date": null,
  "event": "學期開始。Fall semester begins",
  "category": "其他"
}
```

**日期區間事件範例**：
```json
{
  "semester": "114-1",
  "start_date": "2025-08-11",
  "end_date": "2025-08-15",
  "event": "研究所新生辦理學雜費減免。New graduate students apply for tuition & miscellaneous fee exemption",
  "category": "其他"
}
```

**欄位說明**：
- `semester`: 學年度-學期（格式：114-1、114-2）
- `start_date`: 事件開始日期（格式：YYYY-MM-DD）
- `end_date`: 事件結束日期（格式：YYYY-MM-DD，如果是單一日期則為 null）
- `event`: 完整事件描述（包含中英文）
- `category`: 事件類別

**日期查詢說明**：
- 查詢某個日期時，會自動匹配在該日期範圍內的所有事件
- 例如：查詢 2025-08-12，會找到開始日期為 2025-08-11、結束日期為 2025-08-15 的事件

### 事件類別

- **開學**: 開學相關事件
- **放假**: 放假、假期、連假、補假
- **考試**: 考試、測驗、期中考、期末考
- **選課**: 選課、加退選
- **註冊**: 註冊、繳費
- **畢業**: 畢業、學位考試
- **活動**: 活動、典禮、慶祝
- **行政**: 截止、申請、繳交
- **其他**: 其他未分類事件

## 使用方式

### 1. 執行爬蟲

```bash
# 使用 uv 執行（推薦）
uv run python runners/run_school_calendar.py

# 或使用虛擬環境
.venv/bin/python runners/run_school_calendar.py
```

### 2. 啟動 API 服務

```bash
# 啟動 FastMCP 服務
uv run python calendar_tools/school_calendar_api.py
```

### 3. API 工具列表

| 工具名稱 | 功能 | 主要參數 |
|---------|------|---------|
| `school_calendar_search` | 搜尋行事曆事件 | keyword, date_range, category, month |
| `school_calendar_get_upcoming` | 取得即將到來的事件 | days, limit |
| `school_calendar_get_by_category` | 依類別篩選事件 | category |
| `school_calendar_get_month` | 取得特定月份事件 | year, month |
| `school_calendar_get_holidays` | 取得所有放假日 | limit |
| `school_calendar_get_exams` | 取得所有考試日期 | limit |
| `school_calendar_get_registration` | 取得選課和註冊日期 | limit |
| `school_calendar_get_today` | 取得今天的事件 | 無 |

## 範例查詢

### 搜尋特定關鍵字

```python
# 搜尋包含"選課"的事件
school_calendar_search(keyword="選課")
```

### 取得未來 30 天的事件

```python
# 取得未來 30 天內的事件
school_calendar_get_upcoming(days=30, limit=20)
```

### 取得特定月份的事件

```python
# 取得 2025 年 9 月的所有事件
school_calendar_get_month(year=2025, month=9)
```

### 取得放假日

```python
# 取得所有放假日
school_calendar_get_holidays()
```

## 資料儲存位置

- **JSON 資料**: `data/calendar/school_calendar.json`
- **HTML 快取**: `data/calendar/school_calendar_cache.html`
- **日誌檔案**: `logs/run_school_calendar.log`

## 開發資訊

### Scraper 實作

- **檔案位置**: `scrapers/school_calendar.py`
- **基礎類別**: `BaseScraper`
- **解析邏輯**:
  - 提取學年度和學期資訊
  - 解析 MsoNormalTable 表格
  - 提取民國年月資訊
  - 解析重要記事欄位中的事件
  - 處理日期區間（單一日期或日期範圍）
  - 處理跨年事件（例如 8 月到隔年 7 月）
  - 自動分類事件

### 特色功能

1. **學年度和學期識別**: 自動提取學年度和學期資訊
2. **日期區間支援**: 正確處理單一日期和日期區間事件
3. **自動年份處理**: 正確處理跨學年的事件日期
4. **事件分類**: 根據關鍵字自動分類事件
5. **HTML 快取**: 避免重複請求伺服器
6. **熱重載支援**: 資料更新後自動通知 MCP 服務

## 注意事項

1. 行事曆資料通常在學期開始前更新，建議定期執行爬蟲
2. 民國年會自動轉換為西元年
3. 跨年事件（如 8 月開學到隔年 7 月）會自動處理年份
4. PM2 熱重載警告可以忽略（若未使用 PM2 服務）

## 更新日期

最後更新：2026-01-13
