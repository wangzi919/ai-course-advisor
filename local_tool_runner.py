# === local_tool_runner.py ===
# 取代原本的 toolbench/tool_runner.py，直接呼叫本地 Python 工具
import sys, os, json, types
from pathlib import Path

# ===== Mock mcp 套件（工具用到 FastMCP 但訓練時不需要實際跑 MCP server）=====
def _mock_mcp():
    for mod_name in ['mcp', 'mcp.server', 'mcp.server.fastmcp']:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)
    class _FakeFastMCP:
        def __init__(self, *a, **kw): pass
        def tool(self): return lambda f: f
        def run(self, *a, **kw): pass
    sys.modules['mcp.server.fastmcp'].FastMCP = _FakeFastMCP
    sys.modules['mcp.server'].fastmcp = sys.modules['mcp.server.fastmcp']
    sys.modules['mcp'].server = sys.modules['mcp.server']

_mock_mcp()

# 讓 import 找得到工具模組
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "course_tools"))
sys.path.insert(0, str(BASE_DIR / "library_tools"))

# ===== 延遲載入所有工具模組（避免啟動時全部初始化）=====
_module_cache = {}

def _load_module(module_path: str):
    """根據 module 路徑載入對應工具"""
    if module_path in _module_cache:
        return _module_cache[module_path]

    mod_name = Path(module_path).stem  # e.g. "course_search_api"
    full_path = BASE_DIR / module_path

    import importlib.util
    spec = importlib.util.spec_from_file_location(mod_name, full_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _module_cache[module_path] = mod
    return mod


def run_local_tool(api_name: str, args: dict, registry: dict, truncate: int = 2048) -> str:
    """
    呼叫本地工具函數，回傳 JSON 字串結果。
    
    Args:
        api_name: 工具函數名稱（對應 tool_registry 的 key）
        args: 函數參數 dict
        registry: tool_registry.json 內容
        truncate: 回傳結果最大字元數
    
    Returns:
        JSON 字串
    """
    if api_name not in registry:
        return json.dumps({"error": f"工具 '{api_name}' 不存在"}, ensure_ascii=False)

    info = registry[api_name]
    module_path = info["module"]
    function_name = info["function"]

    try:
        mod = _load_module(module_path)
        func = getattr(mod, function_name)
        result = func(**args)

        # 統一轉成可解析的結果
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except Exception:
                return result[:truncate]
        else:
            parsed = result

        # 截斷 results 列表，避免切壞 JSON
        if isinstance(parsed, dict) and 'results' in parsed:
            if len(parsed['results']) > 5:
                parsed['results'] = parsed['results'][:5]
                parsed['_truncated'] = True

        result_str = json.dumps(parsed, ensure_ascii=False)
        return result_str[:truncate]

    except TypeError as e:
        return json.dumps({"error": f"參數錯誤: {e}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"工具執行失敗: {e}"}, ensure_ascii=False)


# ===== 簡單測試 =====
if __name__ == "__main__":
    with open(BASE_DIR / "tool_metadata/tool_registry.json", encoding="utf-8") as f:
        registry = json.load(f)

    print("=== 測試 course_search_by_keyword ===")
    result = run_local_tool(
        "course_search_by_keyword",
        {"keyword": "人工智慧", "limit": 3},
        registry
    )
    data = json.loads(result)
    print(f"找到 {data.get('total', 0)} 筆，顯示 {data.get('showing', 0)} 筆")
    for r in data.get("results", [])[:2]:
        print(f"  - {r['course'].get('課程名稱', '')} / {r['course'].get('開課系所', '')}")

    print("\n=== 測試 library_guide_search ===")
    result2 = run_local_tool(
        "library_guide_search",
        {"keyword": "借書"},
        registry
    )
    data2 = json.loads(result2)
    print(f"找到 {data2.get('total_results', 0)} 筆")