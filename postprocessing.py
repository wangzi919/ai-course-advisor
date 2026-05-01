# === postprocessing.py ===
import os
import json
import random
from copy import deepcopy
from my_llm import chat_my


def main(
    input_path: str = "results/ste/combined_results.json",
    filter_model_ckpt: str = "qwen3:32b",
    paraphrase_model_ckpt: str = "qwen3:32b",
    target_num_train_per_API: int = 50, #平均每個api產出量目標
    num_para_train_max: int = 4, #每筆最多改寫幾次
    dir_write: str = "results/ste/",
):
    os.makedirs(dir_write, exist_ok=True)

    # === 讀入探索資料 ===
    with open(input_path, "r", encoding="utf-8") as f:
        data_dict = json.load(f)

    # === 載入 filter prompt ===
    with open("prompts/prompt_filtering.txt", "r", encoding="utf-8") as f:
        prompt_filtering_template = f.read().strip()

    dataset = {}
    
    TARGET_APIS = {
        # ── 一般課程 ──────────────────────────────────
        "nchu_course_search_by_keyword",
        "nchu_course_search_by_department",
        "nchu_course_search_selectable_courses",
        "nchu_course_search_by_time",
        "nchu_course_get_detail",
        "nchu_course_get_weekly_content",
        "nchu_course_search_by_assessment_method",
        "nchu_course_search_by_teaching_method",
        "nchu_course_search_syllabus",
        "nchu_course_get_teacher_history",
        "nchu_course_get_teacher_courses",

        # ── 通識課程 ──────────────────────────────────
        "nchu_ge_course_search_by_domain",
        "nchu_ge_course_search_by_keyword",
        "nchu_ge_course_search_by_time",
        "nchu_ge_course_get_detail",
        "nchu_ge_course_search_by_teacher",       # NEW
        "nchu_ge_course_get_teacher_courses",     # NEW

        # ── 教師查詢 ──────────────────────────────────
        "nchu_teacher_search_by_name",
        "nchu_teacher_get_detail",                # NEW
        "nchu_teacher_search_by_research_area",   # NEW

        # ── 跨域學程 ──────────────────────────────────
        "nchu_cross_program_search_by_program",
        "nchu_cross_program_search_by_keyword",   # NEW
        "nchu_cross_program_get_program_courses", # NEW

        # ── 行事曆 ────────────────────────────────────
        "school_calendar_get_holidays",
        "school_calendar_get_exams",              # NEW
        "school_calendar_get_registration",
        "school_calendar_search",
        "school_calendar_get_today",              # NEW
        "school_calendar_get_month",              # NEW

        # ── 圖書館 ────────────────────────────────────
        "get_library_hours",
        "get_24hour_spaces",
        "library_search_books",
        "search_library_space",                   # NEW

        # ── 其他 ──────────────────────────────────────
        "rule_search_by_query",
        "modules_get_detail",
    }


    print(f"🔍 Filtering data from {len(data_dict)} APIs (Targeting {len(TARGET_APIS)} specific APIs)")

    for api_name, sessions in data_dict.items():
        if api_name not in TARGET_APIS:
            continue

        examples = []
        print(f"\n=== Processing {api_name} ===")

        # 你的 ste_runner 結構是 all_sessions → item["chains"]
        for item in sessions:
            # 跳過沒成功推理的樣本
            if item.get("reflection", "No") == "No":
                continue

            chains = item.get("chains", [])
            if not chains:
                continue

            last_step = chains[-1]["parsed"]
            if not last_step.get("finish", False):
                continue

            # 取得最後成功的 API 呼叫
            last_action = None
            observation = ""
            for i in range(len(chains) - 2, -1, -1):  # 從倒數第二個元素開始往前找
                step = chains[i]
                parsed = step.get("parsed", {})
                if parsed.get("parse_successful", False):
                    last_action = parsed
                    observation = step.get("observation", "")
                    break
            if not last_action:
                continue

            # === 用 LLM 過濾 ===
            prompt_criticize = prompt_filtering_template.format(
                api_descriptions=last_action.get("api_descriptions", ""),
                query=item.get("query", ""),
                chains=json.dumps(chains, ensure_ascii=False, indent=2),
                final_ans=last_step.get("final_ans", ""),
            )

            #太慢先關掉
            #judgment = call_ollama(filter_model_ckpt, prompt_criticize).strip()
            judgment = "Yes"
            item["judgment"] = judgment

            if "No" in judgment:
                continue

            # === 儲存合格範例 ===
            examples.append({
                "query": item["query"],
                "action": last_action.get("action", api_name),
                "action_input": last_action.get("action_input", {}),
                "observation": observation,
                "final_ans": last_step.get("final_ans", ""),
            })

        dataset[api_name] = examples
        print(f"✅ {api_name}: kept {len(examples)} examples")

    # === Paraphrase ===
    print("\n🌀 Starting paraphrasing...")

    # 先決定輸出的檔名，以便即時寫入
    if paraphrase_model_ckpt == "gpt-oss:120b":
        save_file_name = "gpt_tool_data_train.json"
    elif paraphrase_model_ckpt == "llama3.1:8b-instruct-fp16":
        save_file_name = "llama_tool_data_train.json"
    else:
        save_file_name = "tool_data_train.json"
    out_path = os.path.join(dir_write, save_file_name)

    # === 讀取現有資料以進行「接續」 (Merge/Append 模式) ===
    tool_data_train = []
    processed_queries = set()
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    tool_data_train = content
                else:
                    print(f"⚠️ 檔案格式非列表，將從頭開始。")
            # 建立已經處理過的 query 集合，避免重複加入完全一樣的樣本
            for item in tool_data_train:
                processed_queries.add(item.get("query", ""))
            print(f"📥 已載入舊有資料：共 {len(tool_data_train)} 筆資料，新資料將接續在其後。")
        except Exception as e:
            print(f"⚠️ 無法讀取舊檔 ({e})，將建立新檔案。")

    for api_name, examples in dataset.items():
        if not examples:
            continue

        num_para = min(
            round(target_num_train_per_API / (len(examples) + 0.001)) - 1,
            num_para_train_max,
        )

        for ex in examples:
            base_query = ex["query"]
            # 如果這個 query 已經處理過，就跳過
            if base_query in processed_queries:
                continue

            ex_list = [ex]

            messages = [
                {"role": "system", "content": "You are a helpful assistant."}
            ]

            # 第一次改寫
            para_prompt = f"""Below is a user query. Rephrase it in a different way but keep the meaning.
Original query:
{base_query}

Only output the **paraphrase itself**, nothing else.
Your paraphrase:"""
            messages = chat_my(messages, para_prompt, model=paraphrase_model_ckpt)
            ex_list.append({"query": messages[-1]['content']})

            # 其他改寫版本
            for _ in range(num_para - 1):
                follow_prompt = "Try paraphrasing it again in a new way (avoid being too similar):"
                messages = chat_my(messages, follow_prompt, model=paraphrase_model_ckpt)
                ex_list.append({"query": messages[-1]['content']})

            # === 即時加進最終訓練集並存檔 ===
            seed = ex_list[0]
            tool_data_train.append(seed)
            processed_queries.add(seed["query"])
            
            for i in range(1, len(ex_list)):
                tmp = deepcopy(seed)
                tmp["query"] = ex_list[i]["query"]
                tool_data_train.append(tmp)
                processed_queries.add(tmp["query"])

            # 每次更新都直接以覆寫("w")模式存回檔案，保持 JSON 格式正確
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(tool_data_train, f, indent=2, ensure_ascii=False)
            
            print(f"💾 即時存檔：目前累積 {len(tool_data_train)} 筆資料寫入 {out_path}")

    # 全部完成後，最後打亂順序再存一次
    random.shuffle(tool_data_train)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tool_data_train, f, indent=2, ensure_ascii=False)

    print(f"\n📦 Finished! Final data shuffled. Total {len(tool_data_train)} examples saved to {out_path}")


if __name__ == "__main__":
    main()