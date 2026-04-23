# === react_parser.py ===
# 解析模型的 ReAct 格式輸出（Thought / Action / Action Input / Final Answer）
import numpy as np
from difflib import get_close_matches
from typing import List, Dict, Any


def find_reverse(str_a: str, ch: str) -> int:
    """從字串尾端往前找字元，回傳位置，找不到回傳 -1。"""
    assert type(str_a) == type(ch) == str
    for i in range(len(str_a) - 1, -1, -1):
        if str_a[i] == ch:
            return i
    return -1


def random_choose(l: list, num: int) -> list:
    """從 list 中隨機取 num 個元素，不重複。"""
    if len(l) <= num:
        return l
    inds = np.random.choice(len(l), num, replace=False).tolist()
    return [l[i] for i in inds]


def strip_end(a: str, b: str) -> str:
    """移除字串尾端的指定子字串（重複移除直到不再以 b 結尾）。"""
    while a.endswith(b):
        a = a[:len(a) - len(b)]
    return a


def parse_response(
    response: str,
    API_name_list: List[str],
    api_descriptions: str = "",
    proc_thought: bool = False,
    proc_toolken: bool = False,
    check_API_name: bool = True,
    ground_API: bool = False,
) -> Dict[str, Any]:
    """
    解析模型輸出的 ReAct 格式回應。

    期望格式：
        Thought: ...
        Action: tool_name
        Action Input: {"param": "value"}

    或完成時：
        Thought: ...
        Final Answer: ...

    Args:
        response: 模型原始輸出文字
        API_name_list: 合法工具名稱列表
        api_descriptions: 工具描述（用於錯誤訊息）
        proc_thought: 是否驗證並擷取 Thought 內容
        proc_toolken: 是否處理 toolken 格式的 action 名稱
        check_API_name: 是否驗證 Action 名稱合法性
        ground_API: 找不到 API 時是否用 difflib 近似比對

    Returns:
        dict 包含：
            parse_successful (bool)
            finish (bool)
            action (str)
            action_input (str)
            final_ans (str)
            thought (str)
            parse_error_msg (str)
            API_name_list (list)
            api_descriptions (str)
    """
    item = dict()
    item['API_name_list'] = API_name_list
    item['api_descriptions'] = api_descriptions
    item['parse_successful'] = True

    # 檢查是否為 Final Answer
    if "Final Answer:" in response:
        temp = response.split("Final Answer:")
        response, final_ans = temp[0].strip(), temp[1].strip()
        if "Action Input:" not in response:
            item['final_ans'] = final_ans
            item['finish'] = True
            return item

    item['finish'] = False

    # 必須包含 Action Input:
    if "Action Input:" not in response:
        item['parse_successful'] = False
        item['parse_error_msg'] = (
            "If you have already got enough information for the final answer, say \"Final Answer:\" followed by your answer. "
            "Otherwise, please specify your API call via \"Action:\" and API arguments via \"Action Input:\" followed by a json string. "
            "If there are no arguments, use \"Action Input: {}\". Do NOT start your response with \"Observation:\"; there is no need to repeat it."
        )
        return item

    if response.count("Action Input:") > 1:
        item['parse_successful'] = False
        item['parse_error_msg'] = "Please use only one \"Action Input:\" in your response."
        return item

    # 分割 Action 和 Action Input
    action, action_input = response.split("Action Input:")
    action = strip_end(action.strip(), "\\n").strip()
    action_input = strip_end(action_input.strip(), "\\n").strip()

    # 取得 Action
    if "Action:" not in action:
        item['parse_successful'] = False
        item['parse_error_msg'] = (
            "Please specify the API name you would like to call via \"Action:\" followed by the name. "
            "Remember that you should only call one API at a time, and the API name should be one of the following: {}. "
            "If you have already got the final answer, say \"Final Answer:\" followed by your final answer."
        ).format(", ".join(API_name_list))
        return item

    if action.count("Action:") > 1:
        item['parse_successful'] = False
        item['parse_error_msg'] = "Please use only one \"Action:\" in your response."
        return item

    # 分割 Thought 和 Action
    thought, action = action.split("Action:")
    thought = strip_end(thought.strip(), "\\n").strip()
    action = strip_end(action.strip(), "\\n").strip()

    if proc_toolken:
        action = action.replace("<tool_", "").strip("<>")

    # 驗證 API 名稱
    if check_API_name and (action not in API_name_list):
        if ground_API:
            matches = get_close_matches(action, API_name_list, n=1, cutoff=0.001)
            if matches:
                action = matches[0]
            else:
                item['parse_successful'] = False
                item['parse_error_msg'] = "Please only use exactly one of the following APIs: {}.".format(
                    ", ".join(API_name_list))
                return item
        else:
            item['parse_successful'] = False
            item['parse_error_msg'] = "Please only use exactly one of the following APIs: {}.".format(
                ", ".join(API_name_list))
            return item

    # 驗證 Thought 格式
    if proc_thought:
        if "Thought:" not in thought:
            if thought.strip():
                # 自動修復：如果模型有輸出內容但沒加關鍵字，幫它補上
                thought = "Thought: " + thought
            else:
                item['parse_successful'] = False
                item['parse_error_msg'] = "Your thought should begin with \"Thought:\"."
                return item

        if thought.count("Thought:") > 1:
            item['parse_successful'] = False
            item['parse_error_msg'] = "Please use only one \"Thought:\" in your response."
            return item

        thought = thought.split("Thought:")[-1].strip()

    # 解析 Action Input（找到 { ... } 括號範圍）
    left_bracket_pos = action_input.find('{')
    if left_bracket_pos == -1:
        item['parse_successful'] = False
        item['parse_error_msg'] = "the Action Input is in json string format, and should begin with \"{\""
        return item

    right_bracket_pos = find_reverse(action_input, '}')
    if right_bracket_pos == -1:
        item['parse_successful'] = False
        item['parse_error_msg'] = "the Action Input is in json string format, and should end with \"}\". Do NOT say anything else after \"}\""
        return item

    if left_bracket_pos >= right_bracket_pos:
        item['parse_successful'] = False
        item['parse_error_msg'] = "Your action input cannot be parsed as a json string. Please try again."
        return item

    # 只保留 {} 內的內容
    action_input = action_input[left_bracket_pos: right_bracket_pos + 1]
    action_input = "{" + action_input.strip("{}") + "}"

    if action_input.startswith("{{"):
        item['parse_successful'] = False
        item['parse_error_msg'] = "the Action Input is in json string format, and should begin with only one \"{\", not two or more."
        return item
    if action_input.endswith("}}"):
        item['parse_successful'] = False
        item['parse_error_msg'] = "the Action Input is in json string format, and should end with only one \"}\". Do NOT say anything else after \"}\""
        return item

    action_input = action_input.strip()

    item['parse_successful'] = True
    if proc_thought:
        item['thought'] = thought
    item['action'] = action
    item['action_input'] = action_input
    return item


if __name__ == '__main__':
    print()