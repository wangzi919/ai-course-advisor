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
            + "\n\nBelow are some examples:\n\n"
            + demo_text
            + "\n\nNow it's your turn.\n\nUser Query: "
            + query
        )
    else:
        prompt_ = prompt_base + "\n\nUser Query: " + query

    return prompt_


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
    if_visualize: bool = True,
    max_turns: int = 3,
    top_k_demos: int = 3,
):
    """
    Run a single user query through the ICL pipeline and print the final answer.
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
    )

    print("\n" + "=" * 60)
    print(f"📋 [ICL] 使用 {len(demo_items)} 個示範範例，限制 {len(all_api_names)} 個 API")
    if demo_items:
        demo_apis = list({d['action'] for d in demo_items})
        print(f"🔍 [Filtered] 展示給模型的 API 描述：{demo_apis}")
    print("=" * 60)

    # ── first model call ────────────────────────────────────────────────────
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    messages = chat_my(messages, prompt_, visualize=if_visualize, model=model_ckpt)

    model_output = ""
    last_obs = None
    last_tool = None

    # ── ReAct loop ─────────────────────────────────────────────────────────
    for turn in range(max_turns):
        temp = messages[-1]["content"]

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
                + "\nIf you have enough information to answer the user query, "
                "output 'Final Answer: ' followed by your final response directly."
            )
            messages = chat_my(messages, obs_prompt, visualize=if_visualize, model=model_ckpt)

        elif api_name and api_name not in allowed_apis:
            # Model tried to use an API not in the training data — block it
            block_msg = (
                f"The API '{api_name}' is not available. "
                f"Please use only the APIs listed above."
            )
            messages = chat_my(messages, block_msg, visualize=if_visualize, model=model_ckpt)

        else:
            # No valid action parsed — treat current output as final
            model_output = temp
            break

    # ── Fallback if we exhausted turns without a Final Answer ──────────────
    if not model_output:
        try:
            fallback_prompt = (
                "Based on the previous observations, please provide the final answer "
                "to the user's query. Output only the final answer directly."
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
        parser.add_argument("--top_k_demos", type=int, default=3)
        parser.add_argument("--max_turns",   type=int, default=3)
        parser.add_argument("--if_visualize", action="store_true", default=True)
        args = parser.parse_args()
        main(**vars(args))
