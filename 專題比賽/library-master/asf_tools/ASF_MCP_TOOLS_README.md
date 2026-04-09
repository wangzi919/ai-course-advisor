# 非洲豬瘟 MCP 工具使用說明

本專案已為非洲豬瘟相關資料建立了三個 FastMCP 工具，可透過 MCP 協議進行查詢。

## 📦 已建立的工具

### 1. `asf_faq_api.py` - FAQ 查詢工具
**資料來源**: `asf_faqs.json`

**主要功能**:
- `search_asf_faqs()` - 搜尋 FAQ（標題、內容、分類）
- `search_by_classification()` - 按分類搜尋
- `get_all_classifications()` - 獲取所有分類統計
- `get_asf_faq_stats()` - 獲取 FAQ 統計資訊
- `get_faq_by_title()` - 根據標題獲取特定 FAQ
- `get_prevention_guidelines()` - 獲取防疫指南
- `get_border_quarantine_info()` - 獲取入境檢疫資訊
- `get_meat_product_regulations()` - 獲取肉品檢疫規定
- `search_penalty_info()` - 搜尋罰則資訊

### 2. `asf_news_api.py` - 新聞查詢工具
**資料來源**: `asf_news.json`

**主要功能**:
- `search_news()` - 搜尋新聞（標題、內容、URL）
- `get_latest_news()` - 獲取最新新聞
- `get_news_stats()` - 獲取新聞統計（依月份分組）
- `get_news_by_title()` - 根據標題獲取特定新聞

### 3. `asf_notices_api.py` - 宣導資訊查詢工具
**資料來源**: `asf_notices.json`

**主要功能**:
- `search_notices()` - 搜尋宣導資訊
- `get_all_notices()` - 獲取所有宣導資訊列表
- `get_notice_by_title()` - 根據標題獲取特定宣導資訊
- `get_notices_stats()` - 獲取宣導資訊統計
- `get_border_control_info()` - 獲取邊境管制相關資訊
- `get_biosecurity_measures()` - 獲取生物安全措施資訊

---

## 🚀 啟動方式

每個工具都可以獨立啟動為 MCP 伺服器：

```bash
# FAQ 工具
python asf_faq_api.py

# 新聞工具
python asf_news_api.py

# 宣導資訊工具
python asf_notices_api.py
```

---

## 💡 使用範例

### 範例 1: 搜尋 FAQ（透過 MCP 客戶端）
```json
{
  "tool": "search_asf_faqs",
  "arguments": {
    "keyword": "豬肉",
    "limit": 5
  }
}
```

### 範例 2: 獲取最新新聞
```json
{
  "tool": "get_latest_news",
  "arguments": {
    "limit": 3
  }
}
```

### 範例 3: 搜尋邊境管制資訊
```json
{
  "tool": "get_border_control_info",
  "arguments": {}
}
```

### 範例 4: 根據分類搜尋 FAQ
```json
{
  "tool": "search_by_classification",
  "arguments": {
    "classification": "入境檢疫",
    "limit": 10
  }
}
```

---

## 📊 資料結構說明

### FAQ 資料 (`asf_faqs.json`)
```json
{
  "title": "FAQ 標題",
  "content": "FAQ 內容",
  "metadata": {
    "url": "來源網址",
    "classification": "分類",
    "timestamp": "時間戳記"
  }
}
```

### 新聞資料 (`asf_news.json`)
```json
{
  "title": "新聞標題",
  "content": "新聞內容",
  "metadata": {
    "url": "來源網址",
    "timestamp": "發布日期 (YYYY-MM-DD)"
  }
}
```

### 宣導資訊 (`asf_notices.json`)
```json
{
  "title": "宣導資訊標題",
  "content": "宣導內容",
  "metadata": {
    "url": "來源網址",
    "timestamp": "時間戳記"
  }
}
```

---

## 🔧 進階功能建議

### 1. 日期範圍篩選
可擴充 `search_news()` 加入日期範圍參數：
```python
def search_news(keyword, limit=10, start_date=None, end_date=None):
    # 實作日期篩選邏輯
    pass
```

### 2. 全文索引
若資料量增大，可考慮整合：
- **Elasticsearch** - 全文搜尋引擎
- **Whoosh** - 純 Python 搜尋引擎
- **SQLite FTS5** - 輕量級全文搜尋

### 3. 快取機制
加入記憶體快取提升查詢效能：
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def search_with_cache(keyword, limit):
    return searcher.search_faqs(keyword, limit)
```

### 4. 單元測試
建立測試檔案 `test_asf_tools.py`：
```python
import unittest
from asf_faq_api import ASFFAQSearcher

class TestASFFAQSearcher(unittest.TestCase):
    def setUp(self):
        self.searcher = ASFFAQSearcher()
    
    def test_search_faqs(self):
        results = self.searcher.search_faqs('豬肉', limit=5)
        self.assertGreater(results['total'], 0)
    
    def test_get_all_classifications(self):
        stats = self.searcher.get_all_classifications()
        self.assertIn('total_classifications', stats)

if __name__ == '__main__':
    unittest.main()
```

### 5. API 文件自動生成
使用 `pydantic` 加強型別驗證並生成文件：
```python
from pydantic import BaseModel

class SearchRequest(BaseModel):
    keyword: str
    limit: int = 10
    case_sensitive: bool = False
```

---

## 🎯 快速測試指令

驗證工具是否正常運作：
```bash
# 測試語法
python -m py_compile asf_faq_api.py
python -m py_compile asf_news_api.py
python -m py_compile asf_notices_api.py

# 啟動工具（需搭配 MCP 客戶端使用）
python asf_faq_api.py
```

---

## 📝 注意事項

1. **JSON 檔案位置**: 確保 JSON 檔案與 Python 腳本在同一目錄
2. **編碼問題**: 所有檔案使用 UTF-8 編碼
3. **依賴套件**: 需安裝 `mcp` 套件（`pip install mcp`）
4. **搜尋效能**: 目前使用簡單字串匹配，資料量大時可能需要優化

---

## 🤝 貢獻與改進

歡迎提出以下改進建議：
- 增加更多專門查詢功能
- 優化搜尋演算法
- 加入自然語言處理（NLP）功能
- 整合外部 API
- 建立 Web 介面

---

## 📞 相關資源

- [FastMCP 文件](https://github.com/modelcontextprotocol/python-sdk)
- [非洲豬瘟專區官網](https://asf.aphia.gov.tw/)
- [農業部動植物防疫檢疫署](https://www.aphia.gov.tw/)
