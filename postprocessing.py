# === postprocessing.py ===
import os
import json
import random
from copy import deepcopy
from my_llm import chat_my


def main(
    input_path: str = "results/ste/gpt_20251203-220811.json",
    filter_model_ckpt: str = "qwen3:32b",
    paraphrase_model_ckpt: str = "qwen3:32b",
    target_num_train_per_API: int = 150, #平均每個api產出量目標
    num_para_train_max: int = 6, #每筆最多改寫幾次
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
    print(f"🔍 Filtering data from {len(data_dict)} APIs")

    for api_name, sessions in data_dict.items():
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
    dataset_paraphrased = {}
    print("\n🌀 Starting paraphrasing...")

    for api_name, examples in dataset.items():
        if not examples:
            continue

        num_para = min(
            round(target_num_train_per_API / (len(examples) + 0.001)) - 1,
            num_para_train_max,
        )

        para_list = []
        for ex in examples:
            base_query = ex["query"]
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

            para_list.append(ex_list)
        dataset_paraphrased[api_name] = para_list

    # === 組成最終訓練集 ===
    tool_data_train = []
    for api_name, para_group in dataset_paraphrased.items():
        for ex_list in para_group:
            if not ex_list:
                continue
            seed = ex_list[0]
            tool_data_train.append(seed)
            for i in range(1, len(ex_list)):
                tmp = deepcopy(seed)
                tmp["query"] = ex_list[i]["query"]
                tool_data_train.append(tmp)

    random.shuffle(tool_data_train)

    if paraphrase_model_ckpt == "gpt-oss:120b":
        save_file_name = "gpt_tool_data_train.json"
    elif paraphrase_model_ckpt == "llama3.1:8b-instruct-fp16":
        save_file_name = "llama_tool_data_train.json"
    else:
        save_file_name = "tool_data_train.json"
    out_path = os.path.join(dir_write, save_file_name)

    with open(out_path, "a", encoding="utf-8") as f:
        json.dump(tool_data_train, f, indent=2, ensure_ascii=False)

    print(f"\n📦 Saved {len(tool_data_train)} examples to {out_path}")


if __name__ == "__main__":
    main()
