# === ste_runner.py ===
# 改寫重點（對照 reference/ste_runner.py）：
#   1. 移除 RapidAPI / toolbench 依賴，改呼叫本地 Python 工具
#   2. api_info 只包含當前 API 本身的描述（對應 reference 的 TOOL_DESCRIPTION[api_name]）
#   3. parse_response 傳入 [api_name]（單一工具），與 reference 一致
#   4. 工具清單從 tool_metadata/ 自動載入
#   5. 使用 Ollama 本地模型

import sys
import os
import re
import json
import textwrap
from datetime import datetime
from pathlib import Path

# ===== 本地模組 =====
from utils import parse_response
from my_llm import chat_my, call_ollama
from local_tool_runner import run_local_tool

# ===== 全域設定 =====
RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
BASE_DIR = Path(__file__).parent

# ===== 載入工具 metadata =====
with open(BASE_DIR / "tool_metadata/tool_registry.json", "r", encoding="utf-8") as f:
    TOOL_REGISTRY = json.load(f)

with open(BASE_DIR / "tool_metadata/tool_description.json", "r", encoding="utf-8") as f:
    TOOL_DESCRIPTION = json.load(f)


# ===== 工具執行（本地版）=====
def run_tool(api_name: str, args: dict, truncate: int = 2048) -> str:
    """呼叫本地工具並回傳 JSON 字串結果。"""
    return run_local_tool(api_name, args, TOOL_REGISTRY, truncate)


# ===== 安全解析 JSON =====
def safe_json_loads(s: str) -> dict:
    """從字串中擷取並解析 JSON。"""
    match = re.search(r"\{[\s\S]*\}", s)
    if not match:
        raise ValueError(f"找不到有效 JSON：{s[:100]}")
    json_str = match.group(0)
    json_str = re.sub(r"//.*?(?=\n|$)", "", json_str)
    json_str = re.sub(r"/\*[\s\S]*?\*/", "", json_str)
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*\]", "]", json_str)
    return json.loads(json_str)


def strip_think(text: str) -> str:
    """移除 qwen3 等模型輸出的 <think>...</think> 推理區塊。"""
    # 移除完整的 <think>...</think> 區塊（含換行）
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    return text.strip()


# ===== LTM 格式化（長期記憶摘要）=====
def LTM(queries: list, results: list) -> list:
    return [f"Query: {q} | Solved: {results[i]}" for i, q in enumerate(queries)]


# ===== 主程式 =====
def main(
    model_ckpt: str = "qwen3:8b",
    num_episodes: int = 5,
    num_stm_slots: int = 2,
    max_turn: int = 5,
    dir_write: str = "results/ste/",
    api_filter: str = "",        # 只跑指定工具，例如 "course_search_by_keyword"，空字串=全部
):
    """
    STE 探索主程式：用 Ollama 模型自動探索本地工具，生成訓練資料。

    Args:
        model_ckpt: Ollama 模型名稱
        num_episodes: 每個工具探索幾輪
        num_stm_slots: 每輪包含幾個 follow-up 問題（含原始問題）
        max_turn: ReAct 最大迭代次數
        dir_write: 結果輸出目錄
        api_filter: 只跑包含此字串的工具名稱（空字串=全部）
    """
    os.makedirs(dir_write, exist_ok=True)

    # ===== 載入 Prompt 模板 =====
    with open(BASE_DIR / "prompts/prompt_explore.txt", "r", encoding="utf-8") as f:
        prompt_template = f.read().strip()

    parts = prompt_template.split("=========")
    if len(parts) < 4:
        raise ValueError(
            f"prompts/prompt_explore.txt 格式錯誤：需要 4 段用 ========= 分隔，目前只有 {len(parts)} 段"
        )
    template_q        = parts[0].strip()   # 生成新問題
    template_a        = parts[1].strip()   # ReAct 回答
    template_q_follow = parts[2].strip()   # 生成 follow-up 問題
    template_a_follow = parts[3].strip()   # Follow-up ReAct 回答

    past_msg_pre  = "以下是你已經探索過的查詢："
    past_msg_post = "請嘗試提出不同角度或使用情境的新問題。"

    # ===== 決定要跑哪些工具 =====
    if api_filter:
        api_list = [n for n in TOOL_REGISTRY.keys() if api_filter in n]
        if not api_list:
            raise ValueError(f"找不到符合 '{api_filter}' 的工具")
        print(f"⚙️  只跑過濾後的工具：{api_list}")
    else:
        api_list = list(TOOL_REGISTRY.keys())
        print(f"⚙️  共 {len(api_list)} 個工具")

    data_dict = {}

    # ===== 逐工具探索 =====
    for api_name in api_list:
        print(f"\n{'='*50}")
        print(f"🔍 探索工具：{api_name}")
        print(f"{'='*50}")

        # 每個 API 只用自身的描述（對照 reference）
        api_info = f"API_name: {api_name}\nDescription:\n{json.dumps(TOOL_DESCRIPTION.get(api_name, {}), indent=2, ensure_ascii=False)}"

        explored_queries, success_labels, all_sessions = [], [], []

        for ep in range(num_episodes):
            print(f"\n=== Episode {ep + 1}/{num_episodes} ===")
            messages = [{"role": "system", "content": "You are a helpful assistant."}]

            # ===== Step 1: 生成查詢問題 =====
            prompt_q = template_q.format(api_descriptions=api_info)
            if explored_queries:
                prompt_q += (
                    f"\n\n{past_msg_pre}\n"
                    + "\n".join(LTM(explored_queries, success_labels))
                    + f"\n\n{past_msg_post}"
                )
            prompt_q += "\n\n只輸出問題本身，不要輸出其他任何內容。\n使用者問題："

            query = strip_think(call_ollama(model_ckpt, prompt_q)).strip('"\'')
            print(f"🧠 New Query: {query}")
            explored_queries.append(query)

            item = {"query": query, "chains": [], "api_name": api_name}

            # ===== Step 2: ReAct 推理鏈 =====
            prompt_a = template_a.format(
                api_descriptions=api_info,
                api_names=api_name,
                query=query,
            )
            messages = chat_my(messages, prompt_a, model=model_ckpt)
            temp = messages[-1]["content"]
            parsed = parse_response(temp, [api_name], api_info, proc_thought=True)

            for turn in range(max_turn):
                if not parsed["parse_successful"]:
                    obs = parsed["parse_error_msg"]
                    print(f"  ⚠️  解析失敗：{obs[:80]}")
                elif parsed["finish"]:
                    item["chains"].append({
                        "step": turn,
                        "parsed": parsed,
                        "observation": "Final Answer",
                    })
                    print(f"  ✅ 完成！Final Answer 長度：{len(parsed.get('final_ans', ''))}")
                    break
                else:
                    try:
                        args = safe_json_loads(parsed["action_input"])
                        obs = run_tool(api_name, args)
                        print(f"  🔧 {parsed.get('action')}({list(args.keys())}) → {obs[:80]}...")
                    except Exception as e:
                        obs = f"Error: {e}"
                        print(f"  ❌ {e}")

                item["chains"].append({
                    "step": turn,
                    "parsed": parsed,
                    "observation": obs,
                })

                messages = chat_my(messages, "Observation: " + obs, model=model_ckpt)
                temp = messages[-1]["content"]
                parsed = parse_response(temp, [api_name], api_info, proc_thought=True)

            # ===== Step 3: Reflection =====
            chain_summary = json.dumps(
                item["chains"][-1] if item["chains"] else {}, ensure_ascii=False, indent=2
            )
            reflection_prompt = textwrap.dedent(f"""
                User Query:
                {query}

                Reasoning chain:
                {chain_summary[:500]}

                Did you successfully fulfill this query? Reply exactly 'Yes' or 'No'.
            """).strip()

            res = call_ollama(model_ckpt, reflection_prompt, temperature=0).strip()
            successful = "Yes" if "Yes" in res else "No"
            print(f"  ✅ Reflection: {successful}")

            item["reflection"] = successful
            success_labels.append(successful)
            all_sessions.append(item)

            # ===== Step 4: Follow-up 問題 =====
            for f_idx in range(num_stm_slots - 1):
                print(f"\n  --- Follow-up #{f_idx + 1} ---")

                follow_q = template_q_follow.format(api_descriptions=api_info)
                if explored_queries:
                    follow_q += (
                        f"\n\n{past_msg_pre}\n"
                        + "\n".join(LTM(explored_queries, success_labels))
                        + f"\n\n{past_msg_post}"
                    )
                follow_q += "\n\n只輸出問題本身，不要輸出其他任何內容。\n使用者問題："

                # Follow-up query 從對話歷史產生（對照 reference 的寫法）
                follow_query = strip_think(chat_my(messages, follow_q, model=model_ckpt)[-1]["content"]).strip().strip('"\'')
                print(f"  💬 Follow Query: {follow_query}")
                explored_queries.append(follow_query)

                item_follow = {"query": follow_query, "chains": [], "api_name": api_name}

                # Follow-up ReAct
                prompt_follow_a = template_a_follow.format(query=follow_query)
                messages = chat_my(messages, prompt_follow_a, model=model_ckpt)
                temp = messages[-1]["content"]
                parsed = parse_response(temp, [api_name], api_info, proc_thought=True)

                for turn in range(max_turn):
                    if not parsed["parse_successful"]:
                        obs = parsed["parse_error_msg"]
                        print(f"  ⚠️  解析失敗：{obs[:80]}")
                    elif parsed["finish"]:
                        item_follow["chains"].append({
                            "step": turn,
                            "parsed": parsed,
                            "observation": "Final Answer",
                        })
                        print(f"  ✅ Follow 完成！")
                        break
                    else:
                        try:
                            args = safe_json_loads(parsed["action_input"])
                            obs = run_tool(api_name, args)
                            print(f"  🔧 Follow Turn {turn}: {parsed.get('action')} → {obs[:80]}...")
                        except Exception as e:
                            obs = f"Error: {e}"
                            print(f"  ❌ {e}")

                    item_follow["chains"].append({
                        "step": turn,
                        "parsed": parsed,
                        "observation": obs,
                    })
                    messages = chat_my(messages, "Observation: " + obs, model=model_ckpt)
                    temp = messages[-1]["content"]
                    parsed = parse_response(temp, [api_name], api_info, proc_thought=True)

                # Follow-up Reflection
                chain_summary_f = json.dumps(
                    item_follow["chains"][-1] if item_follow["chains"] else {},
                    ensure_ascii=False, indent=2
                )
                ref_prompt = textwrap.dedent(f"""
                    User Query:
                    {follow_query}

                    Reasoning chain:
                    {chain_summary_f[:500]}

                    Did you successfully fulfill this query? Reply exactly 'Yes' or 'No'.
                """).strip()

                res = call_ollama(model_ckpt, ref_prompt, temperature=0).strip()
                suc = "Yes" if "Yes" in res else "No"
                print(f"  ✅ Follow-up Reflection: {suc}")

                item_follow["reflection"] = suc
                success_labels.append(suc)
                all_sessions.append(item_follow)

        data_dict[api_name] = all_sessions
        total_ep = len(all_sessions)
        yes_ep = success_labels.count("Yes")
        print(f"\n📊 {api_name}：共 {total_ep} 筆，成功 {yes_ep} 筆")

    # ===== 寫出結果 =====
    safe_model = model_ckpt.replace(":", "-").replace("/", "-")
    out_path = os.path.join(dir_write, f"{safe_model}_{RUN_ID}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in data_dict.values())
    success = sum(
        1 for sessions in data_dict.values()
        for s in sessions if s.get("reflection") == "Yes"
    )
    print(f"\n{'='*50}")
    print(f"📁 結果已儲存：{out_path}")
    print(f"📊 總計：{total} 筆，成功：{success} 筆（{100*success//max(total,1)}%）")
    print(f"{'='*50}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="STE 工具探索訓練資料生成")
    parser.add_argument("--model",    default="qwen3:8b",    help="Ollama 模型名稱")
    parser.add_argument("--episodes", type=int, default=15,   help="每個工具探索幾輪")
    parser.add_argument("--stm",      type=int, default=2,   help="每輪 follow-up 數量（含原始問題）")
    parser.add_argument("--turns",    type=int, default=5,   help="ReAct 最大迭代次數")
    parser.add_argument("--output",   default="results/ste/", help="輸出目錄")
    parser.add_argument("--filter",   default="",            help="只跑包含此字串的工具名稱")
    args = parser.parse_args()

    main(
        model_ckpt=args.model,
        num_episodes=args.episodes,
        num_stm_slots=args.stm,
        max_turn=args.turns,
        dir_write=args.output,
        api_filter=args.filter,
    )