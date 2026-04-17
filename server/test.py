import sys, os, json, random
course_advisor_path = r'C:\Users\User\OneDrive\Desktop\course advisor'
sys.path.insert(0, course_advisor_path)
try:
    from local_tool_runner import run_local_tool
except Exception as e:
    open('test.log', 'w', encoding='utf-8').write(str(e))
    sys.exit(1)

with open(os.path.join(course_advisor_path, 'tool_metadata', 'tool_registry.json'), 'r', encoding='utf-8') as f:
    TOOL_REGISTRY = json.load(f)

apis = [
    'nchu_course_search_by_keyword', 'nchu_course_search_by_teacher',
    'nchu_ge_course_search_by_sdg', 'nchu_ge_course_search_by_domain',
    'nchu_ge_course_search_by_type', 'nchu_course_time_format_help',
    'nchu_teacher_search_by_name', 'library_activities_search',
    'get_library_hours', 'check_library_hours_update',
    'school_calendar_get_today', 'school_calendar_get_upcoming'
]

results = []
for api in apis:
    try:
        data_path = os.path.join(course_advisor_path, 'results', 'ste', api, 'qwen3-32b_20260408-003522.json')
        with open(data_path, 'r', encoding='utf-8') as f:
            ste_data = json.load(f)
        
        valid_sessions = [s for s in ste_data if s.get('reflection') == 'Yes']
        if not valid_sessions:
            results.append(f'{api} 測試失敗: 沒有成功的歷史記錄')
            continue
            
        session = random.choice(valid_sessions)
        action_input = {}
        chains = session.get('chains', [])
        for i in range(len(chains) - 2, -1, -1):
            step = chains[i]
            parsed = step.get('parsed', {})
            if parsed.get('parse_successful', False) and parsed.get('action') == api:
                inp = parsed.get('action_input', {})
                if isinstance(inp, str):
                    try:
                        inp = json.loads(inp)
                    except:
                        inp = {}
                action_input = inp
                break
                
        obs = run_local_tool(api, action_input, TOOL_REGISTRY)
        
        obs_str = str(obs)
        if len(obs_str) > 100:
            obs_str = obs_str[:100] + '...'
            
        results.append(f'[OK] {api} | 參數: {action_input} | 回傳長度: {len(str(obs))}字元 | 預覽: {obs_str}')
    except Exception as e:
        results.append(f'[FAIL] {api} | 錯誤: {e}')

with open('test_results.log', 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
