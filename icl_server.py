# === icl_server.py ===
# 輕量 Flask 伺服器，把 icl_runner.run_query() 包裝成 HTTP API。
# 前端只需呼叫 POST /api/chat  { "query": "..." }
# 就能取得 icl_runner 的最終回答。
#
# 啟動方式：
#   python icl_server.py
#   python icl_server.py --port 5001
#   python icl_server.py --model_ckpt llama3.1:8b-instruct-fp16 --port 5001

import sys
import os
import json
import argparse
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

# Fix Windows console encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ── 載入 icl_runner 的核心元件 ────────────────────────────────────────────────
from icl_runner import (
    load_train_data,
    retrieve_demos,
    build_icl_prompt,
    safe_json_loads,
    clean_think_tags,
    run_query,
)
from my_llm import chat_my
from react_parser import parse_response
from local_tool_runner import run_local_tool

# ── Flask ─────────────────────────────────────────────────────────────────────
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    print("❌ 需要安裝 Flask 和 flask-cors：")
    print("   pip install flask flask-cors")
    sys.exit(1)

app = Flask(__name__)
CORS(app)  # 允許前端 (不同 port) 跨域呼叫

# ── 全域資源（伺服器啟動時載入一次）─────────────────────────────────────────
_resources = {}
_lock = threading.Lock()  # 確保並行請求安全


def load_resources(
    train_data_path: str,
    tool_desc_path: str,
    tool_reg_path: str,
    prompt_path: str,
    tool_errata_path: str = "results/tool_errata.json",
):
    """載入所有靜態資源到記憶體（只做一次）。"""
    print("[*] 載入資源中...")

    train_items, allowed_apis = load_train_data(train_data_path)
    print(f"[OK] 訓練資料：{len(train_items)} 筆，{len(allowed_apis)} 種 API")

    with open(tool_desc_path, "r", encoding="utf-8") as f:
        tool_description = json.load(f)

    with open(tool_reg_path, "r", encoding="utf-8") as f:
        tool_registry = json.load(f)

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read().strip()

    # 載入 tool errata（可選）
    tool_errata = {}
    if os.path.exists(tool_errata_path):
        try:
            with open(tool_errata_path, "r", encoding="utf-8") as f:
                tool_errata = json.load(f)
            print(f"[OK] 已載入 {len(tool_errata)} 條 API 使用規則 (tool_errata)")
        except Exception as e:
            print(f"[WARN] 無法載入 tool_errata：{e}")
    else:
        print(f"[INFO] 未找到 {tool_errata_path}，不注入 API 使用規則。")

    valid_api_names = [
        n for n in allowed_apis
        if n in tool_description and n in tool_registry
    ]
    print(f"[OK] 可用 API：{len(valid_api_names)} 個")

    _resources.update({
        "train_items":      train_items,
        "allowed_apis":     allowed_apis,
        "tool_description": tool_description,
        "tool_registry":    tool_registry,
        "prompt_template":  prompt_template,
        "tool_errata":      tool_errata,
    })


# ── API 端點 ──────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    接收前端 POST 請求：
        { "query": "使用者問題" }
    回傳：
        { "answer": "模型最終回答", "success": true }
    或
        { "error": "錯誤訊息", "success": false }
    """
    data = request.get_json(silent=True)
    if not data or not data.get("query", "").strip():
        return jsonify({"success": False, "error": "缺少 query 欄位"}), 400

    query = data["query"].strip()
    model_ckpt   = data.get("model_ckpt",  app.config["MODEL_CKPT"])
    top_k_demos  = int(data.get("top_k_demos", app.config["TOP_K_DEMOS"]))
    max_turns    = int(data.get("max_turns",   app.config["MAX_TURNS"]))

    print(f"\n📩 收到查詢：{query[:80]}")

    try:
        with _lock:
            answer = run_query(
                query=query,
                train_items=_resources["train_items"],
                allowed_apis=_resources["allowed_apis"],
                tool_description=_resources["tool_description"],
                tool_registry=_resources["tool_registry"],
                prompt_template=_resources["prompt_template"],
                model_ckpt=model_ckpt,
                tool_errata=_resources.get("tool_errata", {}),
                if_visualize=False,
                max_turns=max_turns,
                top_k_demos=top_k_demos,
            )
        return jsonify({"success": True, "answer": answer})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """健康檢查端點，確認伺服器是否就緒。"""
    return jsonify({
        "status": "ok",
        "model": app.config.get("MODEL_CKPT"),
        "api_count": len(_resources.get("allowed_apis", [])),
    })


@app.route("/", methods=["GET"])
def index():
    """Serve the ICL chat frontend HTML page."""
    html_path = os.path.join(BASE_DIR, "web", "icl_chat.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return """
    <h2>ICL Runner API Server</h2>
    <p>POST <code>/api/chat</code> with JSON body <code>{"query": "..."}</code></p>
    <p>GET  <code>/api/health</code> to check server status</p>
    """, 200



# ── 啟動 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ICL Runner Flask Server")
    parser.add_argument("--port",            type=int,   default=5001)
    parser.add_argument("--host",            type=str,   default="0.0.0.0")
    parser.add_argument("--model_ckpt",      type=str,   default="llama3.1:8b-instruct-fp16")
    parser.add_argument("--top_k_demos",     type=int,   default=3)
    parser.add_argument("--max_turns",       type=int,   default=3)
    parser.add_argument("--train_data_path", type=str,   default="results/ste/tool_data_train.json")
    parser.add_argument("--tool_desc_path",  type=str,   default="tool_metadata/tool_description.json")
    parser.add_argument("--tool_reg_path",   type=str,   default="tool_metadata/tool_registry.json")
    parser.add_argument("--prompt_path",        type=str,   default="prompts/prompt_template.txt")
    parser.add_argument("--tool_errata_path",   type=str,   default="results/tool_errata.json")
    args = parser.parse_args()

    # 存到 Flask config，讓端點讀取
    app.config["MODEL_CKPT"]  = args.model_ckpt
    app.config["TOP_K_DEMOS"] = args.top_k_demos
    app.config["MAX_TURNS"]   = args.max_turns

    # 一次性載入所有資源
    load_resources(
        train_data_path=args.train_data_path,
        tool_desc_path=args.tool_desc_path,
        tool_reg_path=args.tool_reg_path,
        prompt_path=args.prompt_path,
        tool_errata_path=args.tool_errata_path,
    )

    print(f"\n[START] ICL Server 啟動於 http://{args.host}:{args.port}")
    print(f"        模型：{args.model_ckpt}")
    print(f"        前端請呼叫：POST http://localhost:{args.port}/api/chat")
    print()

    app.run(host=args.host, port=args.port, debug=False, threaded=False)


if __name__ == "__main__":
    main()
