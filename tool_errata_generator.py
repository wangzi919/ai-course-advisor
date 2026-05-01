# === tool_errata_generator.py ===
"""
Tool Errata Generator
---------------------
參考 semantic_generator2.1.py，針對 course_advisor_main 專案的資料結構調整。

功能：
  1. 從 combined_results.json 中蒐集「有問題」的 session：
     - reflection == "No"（整體推理失敗）
     - reflection == "Yes" 但某個 chain 的 parse_successful == False（格式出錯）
  2. 對每個 API 統計錯誤模式（error counter、missing action_input 等）
  3. 將錯誤範例（含 thought）組成 Prompt，請模型歸納出一條修正規則
  4. 輸出到 results/tool_errata.json

與原版差異：
  - 使用 chat_my (my_llm.py) 而非 call_ollama
  - 適配本地 parsed 結構（失敗的 chain 無 thought/action/action_input 欄位）
"""

import os
import re
import json
from collections import Counter
from typing import Dict, Any
from my_llm import chat_my

# ── 設定 ─────────────────────────────────────────────────────────────────────
DATA_PATH      = "results/ste/combined_results.json"
TOOL_DESC_PATH = "tool_metadata/tool_description.json"
OUT_PATH       = "results/tool_errata.json"
MODEL_CKPT     = "qwen3:32b"           # 改成你想用的模型

MAX_CHAINS_PER_SESSION = 6   # 每個 session 最多取幾個 chain
MAX_EXAMPLES_PER_API   = 6   # 每個 API 最多保留幾個 unique 範例
MAX_PROMPT_EXAMPLES    = 4   # 送給模型看的範例數

# 純格式錯誤（ReAct 標記缺失），與 API 參數無關，過濾揁除
FORMAT_ERROR_PATTERNS = [
    'thought should begin with',
    'use only one "thought"',
    'use only one "action"',
    'use only one "action input"',
    'begin with "thought:"',
    'must include "action:"',
    'must include "action input:"',
]

def is_format_error(err_msg: str) -> bool:
    """True 如果這個錯誤訊息屬於純 ReAct 格式錯誤。"""
    if not err_msg:
        return False
    low = err_msg.lower()
    return any(pat in low for pat in FORMAT_ERROR_PATTERNS)


# ── 工具函式 ─────────────────────────────────────────────────────────────────
def safe_json_loads(s: str):
    """盡量把字串 parse 成 dict，失敗就回傳原字串。"""
    if not isinstance(s, str):
        return s
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return s.strip()
    js = m.group(0)
    js = re.sub(r",\s*}", "}", js)
    js = re.sub(r",\s*\]", "]", js)
    try:
        return json.loads(js)
    except Exception:
        return js.strip()


def normalize_action_input(action_input: str):
    """把 action_input 字串 parse 成 dict 並排序 key，方便去重。"""
    parsed = safe_json_loads(action_input or "")
    if isinstance(parsed, dict):
        return {k: parsed[k] for k in sorted(parsed.keys())}
    return parsed


def extract_error_msg(obs: str) -> str:
    """從 observation 字串中提取錯誤訊息（如有）。"""
    if not isinstance(obs, str):
        return ""
    if "error" in obs.lower():
        m = re.search(r"\{[\s\S]*?\}", obs)
        if m:
            return m.group(0)
        return obs.strip()[:200]
    return ""


def shorten(s, L=200) -> str:
    if not isinstance(s, str):
        return str(s) if s is not None else ""
    return s if len(s) <= L else s[:L] + "..."


def parse_rule(resp: str):
    """從 LLM 回應中抽取 'Rule: ...' 那一行。"""
    if not resp:
        return None
    m = re.search(r"Rule\s*:\s*(.+)", resp)
    if m:
        return m.group(1).strip()
    return None


# ── 核心邏輯：蒐集一個成功範例（作為對比）────────────────────────────────────
def collect_successful_example(sessions: list) -> dict | None:
    """
    從 sessions 中找一個「reflection == Yes 且所有 chain 都 parse 成功」的 session，
    回傳其中最後一個成功的 action chain 作為對比範例。
    """
    for s in sessions:
        refl = str(s.get("reflection", "")).strip().lower()
        if refl != "yes":
            continue
        chains = s.get("chains", [])
        # 確認所有 chain 都 parse 成功
        if any(c.get("parsed", {}).get("parse_successful") is False for c in chains):
            continue
        # 找最後一個非 finish 的 action chain
        for c in reversed(chains):
            parsed = c.get("parsed", {})
            if parsed.get("finish"):
                continue
            if not parsed.get("parse_successful"):
                continue
            return {
                "query":        shorten(s.get("query", ""), 240),
                "thought":      shorten(parsed.get("thought", ""), 240),
                "action":       parsed.get("action", ""),
                "action_input": normalize_action_input(parsed.get("action_input", "")),
                "observation":  shorten(str(c.get("observation", "")), 300),
            }
    return None


# ── 核心邏輯：蒐集有問題的範例 ───────────────────────────────────────────────
def collect_problematic_examples(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    找出兩種有問題的 session：
      1. reflection == "No"
      2. reflection == "Yes" 但其中某個 chain 的 parse_successful == False
    """
    results = {}

    for api_name, sessions in data.items():
        bad_sessions = []

        for s in sessions:
            refl = str(s.get("reflection", "")).strip().lower()
            if refl == "no":
                bad_sessions.append(s)
                continue
            if refl == "yes":
                # 有成功推理但格式出過錯
                chains = s.get("chains", [])
                for c in chains:
                    if c.get("parsed", {}).get("parse_successful") is False:
                        bad_sessions.append(s)
                        break

        if not bad_sessions:
            continue

        examples = []
        error_counter = Counter()
        missing_action_input_count = 0

        for s in bad_sessions:
            q = s.get("query", "")
            chains = s.get("chains", [])[:MAX_CHAINS_PER_SESSION]

            for c in chains:
                parsed = c.get("parsed", {})

                # 本地結構：失敗的 chain 不一定有 thought/action/action_input
                thought       = parsed.get("thought", "")
                action        = parsed.get("action", "")
                action_input  = normalize_action_input(parsed.get("action_input", ""))
                parse_err     = parsed.get("parse_error_msg", "")
                obs           = c.get("observation", "")
                err           = extract_error_msg(str(obs))

                # 如果 parse 本身失敗，parse_error_msg 也算錯誤
                effective_err = err or parse_err
                if effective_err:
                    error_counter[shorten(effective_err, 150)] += 1

                if not action_input or action_input == {} or action_input == "":
                    missing_action_input_count += 1

                examples.append({
                    "query":        shorten(q, 240),
                    "thought":      shorten(thought, 240),
                    "action":       action,
                    "action_input": action_input,
                    "parse_error":  shorten(parse_err, 200),
                    "obs_error":    shorten(err, 200),
                })

        # 只保留「真正有 API 調用錢誤 or obs 錯誤」的範例，遮掌純格式錯誤
        api_examples = [
            ex for ex in examples
            if ex.get("obs_error")                        # 有真實 API 輸出錯誤
            or (
                ex.get("parse_error")
                and not is_format_error(ex["parse_error"])  # parse 錯誤不是格式問題
            )
            or (                                          # action_input 明顯填錯（非空且成功解析）
                ex.get("action_input")
                and ex.get("action")
                and ex.get("obs_error") == ""
            )
        ]
        # 如果沒有任何 API 層次的錯誤範例，跳過這個 API
        if not api_examples:
            print(f"  [SKIP] {api_name} 沒有可用的 API 層錯誤範例，跳過")
            continue

        # 去重（以 action_input 為 key）
        seen = set()
        uniq_examples = []
        for ex in examples:
            key = (
                json.dumps(ex["action_input"], ensure_ascii=False, sort_keys=True)
                if isinstance(ex["action_input"], dict)
                else str(ex["action_input"])
            )
            if key in seen:
                continue
            seen.add(key)
            uniq_examples.append(ex)
            if len(uniq_examples) >= MAX_EXAMPLES_PER_API:
                break

        top_err_list = [
            f"[{cnt}x] {e.replace(chr(10), ' ')[:200]}"
            for e, cnt in error_counter.most_common(6)
            if not is_format_error(e)          # 過濾純格式錯誤
        ]

        # 成功範例（從所有 sessions 裡找，不限於 bad_sessions）
        good_example = collect_successful_example(sessions)

        results[api_name] = {
            "stats": {
                "total_problem_sessions":     len(bad_sessions),
                "missing_action_input_count": missing_action_input_count,
                "top_errors":                 top_err_list,
            },
            "examples":      uniq_examples,
            "good_example":  good_example,   # 可能是 None（若無成功 session）
        }

    return results


# ── Prompt ───────────────────────────────────────────────────────────────────
PROMPT_TEMPLATE = """You are an assistant that writes a single actionable rule for an API, based on recurring failure traces.

IMPORTANT: Focus ONLY on errors related to incorrect parameter values, wrong parameter names, missing required parameters, or misunderstanding of how to use this API.
Do NOT write rules about ReAct formatting (e.g., "Thought:", "Action:", "Action Input:" labels) — those are irrelevant here.

API name: {api_name}
API description:
{api_description}

Summary statistics:
- total_problem_sessions: {total_problem_sessions}
- missing_action_input_count: {missing_action_input_count}
- top API-usage errors (most common):
  {top_errors}

✅ A correct successful call (for contrast):
{good_example_block}

❌ Representative problematic attempts (focus on parameter or API-usage issues):
{examples_block}

Task:
Analyze what went wrong with the API parameters or usage in the failing examples,
comparing them with the successful call.
Explain concisely why those API calls failed, then summarize ONE actionable rule
that a model should follow when calling this API.
Start your rule with:
Rule: <your concise rule here>
"""


def build_prompt(api_name: str, api_desc: dict, info: dict) -> str:
    s = info["stats"]
    examples = info["examples"][:MAX_PROMPT_EXAMPLES]
    examples_text = (
        "\n".join([json.dumps(ex, ensure_ascii=False) for ex in examples])
        if examples else "None"
    )
    good = info.get("good_example")
    good_text = json.dumps(good, ensure_ascii=False) if good else "(no successful example available)"

    return PROMPT_TEMPLATE.format(
        api_name=api_name,
        api_description=json.dumps(api_desc, ensure_ascii=False, indent=2),
        total_problem_sessions=s["total_problem_sessions"],
        missing_action_input_count=s["missing_action_input_count"],
        top_errors="\n  ".join(s["top_errors"]) if s["top_errors"] else "None",
        good_example_block=good_text,
        examples_block=examples_text,
    )


# ── 主程式 ───────────────────────────────────────────────────────────────────
def main():
    print(f"[*] 載入資料：{DATA_PATH}")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[*] 載入工具描述：{TOOL_DESC_PATH}")
    with open(TOOL_DESC_PATH, "r", encoding="utf-8") as f:
        tool_desc = json.load(f)

    # 讀取已存在的輸出（斷點續傳）
    tool_errata = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, "r", encoding="utf-8") as f:
                tool_errata = json.load(f)
            print(f"[OK] 已載入 {len(tool_errata)} 條舊規則，將跳過已處理的 API。")
        except Exception as e:
            print(f"[WARN] 無法讀取舊檔：{e}，從頭開始。")

    problematic = collect_problematic_examples(data)
    print(f"[OK] 發現 {len(problematic)} 個 API 有問題 session。\n")

    for api_name, info in problematic.items():
        if api_name in tool_errata:
            print(f"[SKIP] {api_name}（已有規則）")
            continue

        n = info["stats"]["total_problem_sessions"]
        print(f"[PROC] {api_name}  ({n} 個問題 session)")

        desc = tool_desc.get(api_name, {"description": "No description available."})
        prompt = build_prompt(api_name, desc, info)

        try:
            messages = [{"role": "system", "content": "You are a helpful assistant."}]
            messages = chat_my(messages, prompt, model=MODEL_CKPT)
            resp = messages[-1]["content"]

            rule = parse_rule(resp) or "(no rule extracted)"
            if rule == "(no rule extracted)":
                print(f"  [WARN] 未能抽取規則，儲存完整回應。")

            tool_errata[api_name] = rule
            print(f"  Rule: {rule}\n")

        except Exception as e:
            print(f"  [ERROR] {e}")
            tool_errata[api_name] = f"(error: {e})"

        # 每處理一個 API 就立即存檔（斷點保護）
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(tool_errata, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] 共 {len(tool_errata)} 條規則儲存至 {OUT_PATH}")


if __name__ == "__main__":
    main()
