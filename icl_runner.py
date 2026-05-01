# === icl_runner.py ===
# In-Context Learning runner for the NCHU Course Advisor.
#
# Fixed settings (equivalent to icl_runner2.py with):
#   setting       = "ICL"
#   retrieve_mode = "filtered"
#   retrieve_type = "tool_doc"
#
# Key design decisions:
#   - API whitelist:   Only APIs that appear in tool_data_train.json are permitted.
#   - ICL demos:       For each user query, we retrieve the most relevant demo examples
#                      from tool_data_train.json using simple keyword overlap.  The demo
#                      actions determine which API descriptions are shown to the model
#                      (filtered / tool_doc mode).
#   - Tool execution:  Real tool calls are made through local_tool_runner.py.
#   - Interactive:     The script prompts the user to enter queries in a REPL loop.

import sys
import os
import json
import re

# ── ensure the project root is on sys.path ────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from my_llm import chat_my
from react_parser import parse_response
from local_tool_runner import run_local_tool

# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def format_action_input(raw_input):
    """Pretty-print an action_input value (string or object)."""
    if not isinstance(raw_input, str):
        return json.dumps(raw_input, indent=2, ensure_ascii=False)

    # Strip trailing inline comments that break JSON parsing
    clean_input = re.sub(r'//.*', '', raw_input).strip()

    try:
        parsed = json.loads(clean_input)
        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed, indent=4, ensure_ascii=False)
        if isinstance(parsed, str) and parsed.strip().startswith("{"):
            inner = json.loads(parsed)
            return json.dumps(inner, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return raw_input


def safe_json_loads(s: str) -> dict:
    """Try to extract the first valid JSON object from a string."""
    decoder = json.JSONDecoder()
    s_stripped = str(s).strip()
    for i in range(len(s_stripped)):
        if s_stripped[i] == '{':
            try:
                obj, _ = decoder.raw_decode(s_stripped, i)
                return obj
            except json.JSONDecodeError:
                continue
    return {}


def clean_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks that some models emit."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


# ═════════════════════════════════════════════════════════════════════════════
# Dataset / demo retrieval
# ═════════════════════════════════════════════════════════════════════════════

def load_train_data(train_path: str):
    """
    Load tool_data_train.json and return:
        train_items   : list of all dicts  (each has query/action/action_input/…)
        allowed_apis  : set of API names that appear in the dataset
    """
    with open(train_path, "r", encoding="utf-8") as f:
        train_items = json.load(f)

    allowed_apis = {item["action"] for item in train_items if "action" in item}
    return train_items, allowed_apis


def _tokenize(text: str) -> set:
    """
    Tokenize text in a way that works for both Chinese and Latin characters.

    Problem: re.findall(r'\\w+', ...) groups ALL consecutive \\w characters
    together.  For Chinese text (which has no spaces), this produces a SINGLE
    huge token for the entire sentence, making overlap scoring useless.

    Solution:
      - Each CJK character (U+4E00–U+9FFF and common extension blocks) is
        treated as its own token.
      - Consecutive ASCII letters / digits / underscores are kept as a word.
    """
    tokens = set()
    # CJK Unified Ideographs (and a few extension planes used in Traditional Chinese)
    CJK_RANGES = (
        ('\u4e00', '\u9fff'),   # CJK Unified Ideographs
        ('\u3400', '\u4dbf'),   # CJK Extension A
        ('\uf900', '\ufaff'),   # CJK Compatibility Ideographs
    )

    for ch in text:
        for lo, hi in CJK_RANGES:
            if lo <= ch <= hi:
                tokens.add(ch)
                break

    # Also capture ASCII word tokens (API names, English terms, numbers)
    for tok in re.findall(r'[a-zA-Z0-9_]+', text.lower()):
        tokens.add(tok)

    return tokens


def retrieve_demos(query: str, train_items: list, top_k: int = 3) -> list:
    """
    Retrieve the most relevant demo examples from the training set for a given
    query using character-level overlap (works for Chinese and English).

    Returns a list of up to `top_k` items with unique actions.
    """
    query_tokens = _tokenize(query)

    scored = []
    for item in train_items:
        item_query = clean_think_tags(item.get("query", ""))
        item_tokens = _tokenize(item_query)
        overlap = len(query_tokens & item_tokens)
        if overlap > 0:
            scored.append((overlap, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    seen_actions = set()
    demos = []
    for _, item in scored:
        action = item.get("action", "")
        if action not in seen_actions:
            demos.append(item)
            seen_actions.add(action)
        if len(demos) >= top_k:
            break

    return demos


# ═════════════════════════════════════════════════════════════════════════════
# Prompt building  (setting=ICL, retrieve_mode=filtered, retrieve_type=tool_doc)
# ═════════════════════════════════════════════════════════════════════════════

def build_icl_prompt(
    query: str,
    demo_items: list,
    all_api_names: list,
    tool_description: dict,
    prompt_template: str,
    tool_errata: dict = None,
) -> str:
    """
    Construct the full ICL prompt.

    retrieve_mode = "filtered"
        → Show descriptions only for APIs that appear in the demo examples.
          api_names list in the template still shows ALL allowed API names so the
          model knows the full menu (mirrors icl_runner2.py behaviour exactly).

    retrieve_type = "tool_doc"
        → Include full JSON descriptions (not just names).

    setting = "ICL"
        → Inject demo examples in the prompt.

    tool_errata (optional)
        → A dict of {api_name: rule_string} loaded from results/tool_errata.json.
          Rules for APIs that appear in the demo examples are injected between
          the API-description block and the demo examples, so the model is
          reminded of known pitfalls before it sees the examples.
    """
    # ── collect API names referenced by the demos ──────────────────────────
    demo_api_names = list({ex["action"] for ex in demo_items})

    if demo_api_names:
        filtered_descriptions = "\n\n".join([
            f"API_name: {name}\nDescription:\n"
            f"{json.dumps(tool_description[name], indent=2, ensure_ascii=False)}"
            for name in demo_api_names
            if name in tool_description
        ])
    else:
        # Fallback: show all allowed API descriptions
        filtered_descriptions = "\n\n".join([
            f"API_name: {name}\nDescription:\n"
            f"{json.dumps(tool_description[name], indent=2, ensure_ascii=False)}"
            for name in all_api_names
            if name in tool_description
        ])

    prompt_base = prompt_template.format(
        api_descriptions=filtered_descriptions,
        api_names="\n".join(all_api_names),
    )

    # ── build tool-errata block (inject between desc block and demos) ───────
    errata_text = ""
    if tool_errata:
        # Determine which APIs to show rules for:
        #   - If we have demos, only show rules for the APIs in those demos.
        #   - If no demos, show rules for all APIs that have an entry.
        target_apis = demo_api_names if demo_api_names else list(tool_errata.keys())
        relevant_rules = [
            (name, tool_errata[name])
            for name in target_apis
            if name in tool_errata
        ]
        if relevant_rules:
            errata_text = (
                "\n\nYou have previously learned the following API-usage rules "
                "from past failure analysis. Apply them carefully when calling these APIs:\n"
            )
            for name, rule in relevant_rules:
                # rule is stored as a plain string in tool_errata.json
                rule_str = rule["rule"] if isinstance(rule, dict) and "rule" in rule else str(rule)
                errata_text += f"- For *{name}*: {rule_str}\n"
            errata_text += "Keep these rules in mind throughout your reasoning.\n"

    # ── build demo block ────────────────────────────────────────────────────
    if demo_items:
        demo_text = "\n\n---\n".join([
            f"User Query: {clean_think_tags(ex['query'])}\n"
            f"Action: {ex['action']}\n"
            f"Action Input:\n{format_action_input(ex['action_input'])}"
            for ex in demo_items
        ])

        prompt_ = (
            prompt_base
            + errata_text
            + "\n\nBelow are some examples:\n\n"
            + demo_text
            + "\n\nNow it's your turn.\n\nUser Query: "
            + query
        )
    else:
        prompt_ = prompt_base + errata_text + "\n\nUser Query: " + query

    return prompt_


# ── Server error detection ────────────────────────────────────────────────────
# Ollama 雲端 API 有時會把錯誤文字直接回傳在 response 裡而不是拋出例外
_SERVER_ERROR_PATTERNS = [
    "error: there was a problem",
    "flagged for looping content",
    "ollama cloud api failed",
    "model output error",
    "retries remaining:",
]

def is_server_error(text: str) -> bool:
    """True 如果模型輸出是 Ollama 雲端 API 的錯誤訊息而非正常回應。"""
    low = text.lower()
    return any(pat in low for pat in _SERVER_ERROR_PATTERNS)


# ═════════════════════════════════════════════════════════════════════════════
# Single-query runner
# ═════════════════════════════════════════════════════════════════════════════

def run_query(
    query: str,
    train_items: list,
    allowed_apis: set,
    tool_description: dict,
    tool_registry: dict,
    prompt_template: str,
    model_ckpt: str,
    tool_errata: dict = None,
    if_visualize: bool = True,
    max_turns: int = 3,
    top_k_demos: int = 3,
):
    """
    Run a single user query through the ICL pipeline and print the final answer.

    tool_errata : dict, optional
        Loaded from results/tool_errata.json.  Maps API name → usage rule string.
        Rules for APIs that appear in the retrieved demos are injected into the
        prompt so the model is aware of known pitfalls.
    """
    # ── retrieve demos ──────────────────────────────────────────────────────
    demo_items = retrieve_demos(query, train_items, top_k=top_k_demos)

    # ── build allowed API name list (intersection of dataset & description) ─
    all_api_names = [
        name for name in allowed_apis
        if name in tool_description and name in tool_registry
    ]

    # ── build prompt ────────────────────────────────────────────────────────
    prompt_ = build_icl_prompt(
        query=query,
        demo_items=demo_items,
        all_api_names=all_api_names,
        tool_description=tool_description,
        prompt_template=prompt_template,
        tool_errata=tool_errata,
    )

    print("\n" + "=" * 60)
    print(f"📋 [ICL] 使用 {len(demo_items)} 個示範範例，限制 {len(all_api_names)} 個 API")
    if demo_items:
        demo_apis = list({d['action'] for d in demo_items})
        print(f"🔍 [Filtered] 展示給模型的 API 描述：{demo_apis}")
    print("=" * 60)

    # ── 印出完整 Prompt （後端發展用）────────────────────────────────────
    print("\n" + "▶" * 3 + " FULL PROMPT " + "▶" * 3)
    print(prompt_)
    print("◀" * 3 + " END PROMPT " + "◀" * 3 + "\n")

    # ── first model call ────────────────────────────────────────────────────
    messages = [{"role": "system", "content": "You are a helpful assistant. Always respond in Traditional Chinese (繁體中文)."}]
    try:
        messages = chat_my(messages, prompt_, visualize=if_visualize, model=model_ckpt)
    except Exception as e:
        err_msg = str(e)
        print(f"\n⚠️ [Error] 首次呼叫出錯：{err_msg}")
        return f"抓取回應時發生錯誤，請重新詢問。（錯誤：{err_msg[:200]}）"

    # 檢查是否收到伺服器錯誤文字（Ollama loop detection 等）
    first_resp = messages[-1]["content"]
    if is_server_error(first_resp):
        print(f"\n⚠️ [Server Error] 首次呼叫收到錯誤回應：{first_resp[:200]}")
        return "伺服器暫時無法處理此請求（可能是模型輸出過長或重複），請稍後再試。"

    model_output = ""
    last_obs = None
    last_tool = None

    # ── ReAct loop ─────────────────────────────────────────────────────────
    for turn in range(max_turns):
        temp = messages[-1]["content"]

        # 印出模型原始輸出（含 think tags）
        print(f"\n🧠 [Turn {turn + 1}] 模型原始回應：")
        print("-" * 50)
        print(temp)
        print("-" * 50)

        # 檢查是否收到伺服器錯誤文字
        if is_server_error(temp):
            print(f"\n⚠️ [Server Error] Turn {turn + 1} 收到錯誤回應")
            model_output = (
                f"根據查詢結果，請參考以下資料：\n{str(last_obs)[:800]}"
                if last_obs else "伺服器暫時無法處理此請求，請稍後再試。"
            )
            break

        # ── 優先檢查 Final Answer（在 parse_response 之前）────────────────
        # 情況：模型在同一回應裡同時輸出 Action 和 Final Answer。
        # parse_response 只認 Action（finish=False），會忽略 Final Answer
        # 並繼續呼叫工具，導致後續 obs_prompt 覆蓋掉正確答案。
        # 因此先做字串掃描，找到就直接 break。
        if "Final Answer:" in temp:
            raw_ans = temp.split("Final Answer:")[-1].strip()
            model_output = clean_think_tags(raw_ans)
            print(f"\n✅ [Parse] 在模型回應中直接偵測到 Final Answer，跳過後續工具呼叫")
            break

        # Strip any observation the model might have hallucinated
        if "Observation:" in temp and "Final Answer:" not in temp:
            temp = temp.split("Observation:")[0].strip()
            messages[-1]["content"] = temp

        # Parse the model's response
        parsed = parse_response(
            temp,
            all_api_names,
            api_descriptions="",
            check_API_name=False,
        )

        # ── Final Answer reached ────────────────────────────────────────────
        if parsed.get("finish", False):
            model_output = parsed.get("final_ans", temp)
            break

        api_name = parsed.get("action")
        action_input_raw = parsed.get("action_input", "{}")

        # ── Validate the chosen API against the whitelist ───────────────────
        if api_name and api_name in tool_registry and api_name in allowed_apis:
            args_dict = safe_json_loads(action_input_raw)

            print(f"\n🔧 [Tool Call] {api_name}")
            print(f"   Input: {json.dumps(args_dict, ensure_ascii=False)[:200]}")

            obs = run_local_tool(api_name, args_dict, tool_registry)

            print(f"   Result: {obs[:300]}")

            last_obs = obs
            last_tool = api_name

            obs_prompt = (
                "Observation: " + obs
                + "\n如果你已有足夠的資訊回答使用者的問題，"
                "請立刻輸出 'Final Answer: ' 並以繁體中文給出最終回答。"
            )
            try:
                messages = chat_my(messages, obs_prompt, visualize=if_visualize, model=model_ckpt)
            except Exception as e:
                print(f"\n⚠️ [Loop Detection] 視察後呼叫出錯：{e}")
                # 有真實資料就用全部資料回答，不要就此崩潰
                model_output = (
                    f"根據查詢結果，請參考以下資料：\n{str(last_obs)[:800]}"
                    if last_obs else f"單元出錯，請重試。（錯誤：{str(e)[:200]}）"
                )
                break

        elif api_name and api_name not in allowed_apis:
            # Model tried to use an API not in the training data — block it
            block_msg = (
                f"API '{api_name}' 不在可用清單中，請只使用上方列出的 API。"
                f"請繼續以繁體中文回答使用者的問題。"
            )
            try:
                messages = chat_my(messages, block_msg, visualize=if_visualize, model=model_ckpt)
            except Exception as e:
                print(f"\n⚠️ [Loop Detection] 封鎖訊息後呼叫出錯：{e}")
                model_output = "模型嘗試使用不允許的 API ，請重新詢問。"
                break

        else:
            # parse_response 沒有抓到有效的 action
            # 如果輸出看起來像是 ReAct 中間步驟（含 Thought:/Action:）但沒有解析成功，
            # 強制要求模型給出最終答案，而不是把原始文字回傳給使用者
            if any(marker in temp for marker in ("Action:", "Thought:", "Action Input:")):
                print(f"\n⚠️ [Parse] 偵測到未完整解析的 ReAct 輸出，強制要求最終答案")
                try:
                    force_prompt = (
                        "你的上一個回應只有推理步驟，但沒有給出最終答案。"
                        "請直接給出使用者問題的最終答案，並以繁體中文回答。"
                        "只需輸出 'Final Answer: ' 後接你的回答即可。"
                    )
                    messages = chat_my(messages, force_prompt, visualize=if_visualize, model=model_ckpt)
                    forced = messages[-1]["content"]
                    if "Final Answer:" in forced:
                        model_output = forced.split("Final Answer:")[-1].strip()
                    else:
                        model_output = forced.strip()
                except Exception as e:
                    print(f"  強制最終答案失敗：{e}")
                    model_output = (
                        f"根據查詢結果，請參考以下資料：\n{str(last_obs)[:800]}"
                        if last_obs else "無法取得回應，請重新詢問。"
                    )
            else:
                # 真的是完整的回答，只是格式特殊
                model_output = temp
            break

    # ── Fallback if we exhausted turns without a Final Answer ──────────────
    if not model_output:
        # ── 先檢查最後一條訊息是否已包含 Final Answer ──────────────────────
        # 情況：最後一輪 obs_prompt 呼叫 chat_my 後，模型的回應（第 N+1 條）
        # 已含 Final Answer，但迴圈因 max_turns 耗盡而未讀取到它。
        last_content = clean_think_tags(messages[-1]["content"]) if messages else ""
        if "Final Answer:" in last_content:
            model_output = last_content.split("Final Answer:")[-1].strip()
            print(f"\n✅ [Fallback] 從最後一條訊息直接取得 Final Answer（迴圈超限但已有答案）")
        else:
            # 真正的 fallback：模型尚未給出最終答案，再呼叫一次
            try:
                fallback_prompt = (
                    "根據先前的查詢結果，請以繁體中文給出使用者問題的最終答案。"
                    "只需輸出最終答案即可，請勿使用英文。"
                )
                messages = chat_my(messages, fallback_prompt, visualize=if_visualize, model=model_ckpt)
                temp = messages[-1]["content"]
                if "Final Answer:" in temp:
                    model_output = temp.split("Final Answer:")[-1].strip()
                else:
                    model_output = temp.strip()
            except Exception:
                if last_tool:
                    model_output = (
                        f"已為您執行查詢 ({last_tool})，以下是系統回傳資料：\n{str(last_obs)[:800]}"
                    )
                else:
                    model_output = messages[-1]["content"]

    print("\n" + "─" * 60)
    print("💬 最終回答：")
    print(model_output)
    print("─" * 60)

    return model_output


# ═════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═════════════════════════════════════════════════════════════════════════════

def main(
    model_ckpt: str = "llama3.1:8b-instruct-fp16",
    train_data_path: str = "results/ste/tool_data_train.json",
    tool_desc_path: str = "tool_metadata/tool_description.json",
    tool_reg_path: str = "tool_metadata/tool_registry.json",
    prompt_path: str = "prompts/prompt_template.txt",
    tool_errata_path: str = "results/tool_errata.json",
    top_k_demos: int = 3,
    max_turns: int = 3,
    if_visualize: bool = True,
):
    """
    Interactive ICL runner for the NCHU Course Advisor.

    Fixed configuration:
        setting       = ICL
        retrieve_mode = filtered
        retrieve_type = tool_doc

    Usage:
        python icl_runner.py
        python icl_runner.py --model_ckpt llama3.1:8b-instruct-fp16
        python icl_runner.py --top_k_demos 5
        python icl_runner.py --tool_errata_path results/tool_errata.json
    """
    # ── change working directory to project root ────────────────────────────
    os.chdir(BASE_DIR)
    sys.stdout.reconfigure(encoding="utf-8")

    # ── load resources ──────────────────────────────────────────────────────
    print("📂 載入資源中…")

    if not os.path.exists(train_data_path):
        raise FileNotFoundError(f"找不到訓練資料：{train_data_path}")
    train_items, allowed_apis = load_train_data(train_data_path)
    print(f"✅ 已載入 {len(train_items)} 筆訓練資料，共 {len(allowed_apis)} 種 API")

    with open(tool_desc_path, "r", encoding="utf-8") as f:
        tool_description = json.load(f)

    with open(tool_reg_path, "r", encoding="utf-8") as f:
        tool_registry = json.load(f)

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read().strip()

    # ── load tool errata (optional) ─────────────────────────────────────────
    tool_errata = {}
    if os.path.exists(tool_errata_path):
        try:
            with open(tool_errata_path, "r", encoding="utf-8") as f:
                tool_errata = json.load(f)
            print(f"[OK] 已載入 {len(tool_errata)} 條 API 使用規則 (tool_errata)")
        except Exception as e:
            print(f"[WARN] 無法載入 tool_errata：{e}，將跳過規則注入。")
    else:
        print(f"[INFO] 未找到 {tool_errata_path}，不注入 API 使用規則。")

    # ── show available APIs (intersection of train set & description) ───────
    valid_api_names = [
        name for name in allowed_apis
        if name in tool_description and name in tool_registry
    ]
    print(f"🧩 可用 API 數量：{len(valid_api_names)}")
    print(f"🤖 使用模型：{model_ckpt}")
    print(f"📖 每次查詢注入示範數：{top_k_demos}")
    print()

    # ── interactive loop ────────────────────────────────────────────────────
    print("🚀 進入互動模式（ICL | filtered | tool_doc）")
    print("   輸入 'exit' 或 'quit' 結束，直接按 Enter 跳過。")

    while True:
        print()
        try:
            user_input = input("請輸入您的查詢：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 結束互動模式。")
            break

        if user_input.lower() in {"exit", "quit", "q"}:
            print("👋 結束互動模式。")
            break

        if not user_input:
            continue

        try:
            run_query(
                query=user_input,
                train_items=train_items,
                allowed_apis=allowed_apis,
                tool_description=tool_description,
                tool_registry=tool_registry,
                prompt_template=prompt_template,
                model_ckpt=model_ckpt,
                tool_errata=tool_errata,
                if_visualize=if_visualize,
                max_turns=max_turns,
                top_k_demos=top_k_demos,
            )
        except Exception as e:
            print(f"\n❌ 執行時發生錯誤：{e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Support optional CLI overrides via python-fire (if available),
    # otherwise fall back to plain argparse.
    try:
        import fire
        fire.Fire(main)
    except ImportError:
        import argparse
        parser = argparse.ArgumentParser(description="NCHU Course Advisor ICL Runner")
        parser.add_argument("--model_ckpt",    default="llama3.1:8b-instruct-fp16")
        parser.add_argument("--train_data_path", default="results/ste/tool_data_train.json")
        parser.add_argument("--tool_desc_path",  default="tool_metadata/tool_description.json")
        parser.add_argument("--tool_reg_path",   default="tool_metadata/tool_registry.json")
        parser.add_argument("--prompt_path",     default="prompts/prompt_template.txt")
        parser.add_argument("--tool_errata_path", default="results/tool_errata.json")
        parser.add_argument("--top_k_demos", type=int, default=3)
        parser.add_argument("--max_turns",   type=int, default=3)
        parser.add_argument("--if_visualize", action="store_true", default=True)
        args = parser.parse_args()
        main(**vars(args))
