# 圖書館開放時間資料

## 資料說明

本目錄包含中興大學圖書館各空間的開放時間資料。

### 檔案說明

- `library_hours.json` - 圖書館開放時間資料（JSON 格式）
- `library_hours_cache.html` - 圖書館網頁的 HTML 快取（可選）
- `README.md` - 本說明文件

## 資料來源

- **官方網站**: https://www.lib.nchu.edu.tw/service.php?cID=35
- **資料格式**: JSON
- **更新方式**: 手動更新（網站有防爬保護）

## 資料結構

```json
{
  "last_updated": "更新時間 (ISO 8601 格式)",
  "source_url": "資料來源網址",
  "note": "備註說明",
  "spaces": [
    {
      "space_name": "空間名稱",
      "floor": "樓層",
      "hours": "開放時間",
      "notes": "備註"
    }
  ]
}
```

## 手動更新流程

由於圖書館網站有防爬蟲保護，需要手動更新資料。以下是更新步驟：

### 方法一：直接編輯 JSON 檔案

1. 訪問圖書館開放時間網頁: https://www.lib.nchu.edu.tw/service.php?cID=35
2. 查看各空間的開放時間
3. 編輯 `library_hours.json` 檔案
4. 更新 `last_updated` 欄位為當前時間
5. 更新各空間的 `hours` 和 `notes` 欄位
6. 儲存檔案

### 方法二：使用爬蟲腳本（需手動下載 HTML）

1. 在瀏覽器中訪問: https://www.lib.nchu.edu.tw/service.php?cID=35
2. 右鍵選擇「另存新檔」，儲存為完整網頁
3. 將 HTML 檔案重新命名為 `library_hours_cache.html`
4. 移動檔案到此目錄
5. 執行爬蟲腳本:

```bash
cd /home/user/library
uv run python scripts/scrape_library_hours.py
```

腳本會自動從 HTML 快取檔案中解析資料並更新 JSON 檔案。

## 定期更新建議

建議更新頻率：

- **學期初**: 開學第一週
- **假期前**: 寒暑假開始前一週
- **例假日**: 連續假期前檢查
- **定期檢查**: 每月第一週

## 使用 API

可以透過 Library Hours API 讀取開放時間資料：

```python
# 範例程式碼
from library_tools.library_hours_api import mcp

# 取得所有空間開放時間
all_hours = mcp.call_tool("get_library_hours", {})

# 搜尋特定空間
space_info = mcp.call_tool("search_library_space", {
    "space_name": "24小時自習室"
})
```

## 注意事項

1. **資料時效性**: 圖書館開放時間可能因特殊情況調整，請以官網公告為準
2. **假期調整**: 寒暑假、例假日及特殊節日的開放時間通常會調整
3. **緊急公告**: 遇颱風、地震等緊急狀況，開放時間可能臨時變更
4. **預約系統**: 部分空間（如研究小間、討論室）需要透過線上預約系統預約

## 相關連結

- [圖書館官網](https://www.lib.nchu.edu.tw/)
- [圖書館服務時間](https://www.lib.nchu.edu.tw/service.php?cID=35)
- [圖書館最新消息](https://www.lib.nchu.edu.tw/news.php)
- [空間預約系統](https://www.lib.nchu.edu.tw/booking/)

## 更新日誌

### 2025-11-05
- 初始化圖書館開放時間資料結構
- 建立範本資料
- 新增手動更新說明文件
- 建立爬蟲腳本（支援從 HTML 快取讀取）

## 聯絡資訊

如有資料錯誤或建議，請聯絡：
- 圖書館服務台: (04) 2284-0290 轉 501
- Email: lib@nchu.edu.tw
