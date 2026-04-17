import sys, os, json, random
course_advisor_path = r'C:\Users\User\OneDrive\Desktop\course advisor'
sys.path.insert(0, course_advisor_path)
from local_tool_runner import run_local_tool

apis = [
    'nchu_course_search_by_keyword', 'nchu_course_search_by_teacher',
    'nchu_ge_course_search_by_sdg', 'nchu_ge_course_search_by_domain',
    'nchu_ge_course_search_by_type', 'nchu_course_time_format_help',
    'nchu_teacher_search_by_name', 'library_activities_search',
    'get_library_hours', 'check_library_hours_update',
    'school_calendar_get_today', 'school_calendar_get_upcoming'
]

with open(os.path.join(course_advisor_path, 'tool_metadata', 'tool_registry.json'), 'r', encoding='utf-8') as f:
    TOOL_REGISTRY = json.load(f)

demo_examples = []
for api in apis:
    try:
        data_path = os.path.join(course_advisor_path, 'results', 'ste', api, 'qwen3-32b_20260408-003522.json')
        with open(data_path, 'r', encoding='utf-8') as f:
            ste_data = json.load(f)
        
        valid_sessions = [s for s in ste_data if s.get('reflection') == 'Yes']
        random.shuffle(valid_sessions)
        
        for session in valid_sessions:
            action_input = {}
            chains = session.get('chains', [])
            final_ans = ""
            for i in range(len(chains) - 2, -1, -1):
                step = chains[i]
                parsed = step.get('parsed', {})
                if parsed.get('parse_successful', False) and parsed.get('action') == api:
                    inp = parsed.get('action_input', {})
                    if isinstance(inp, str):
                        try: inp = json.loads(inp)
                        except: inp = {}
                    action_input = inp
                    break
            
            # get final answer
            for i in range(len(chains) - 1, -1, -1):
                ans = chains[i].get('parsed', {}).get('final_ans', '')
                if ans:
                    final_ans = ans
                    break
            
            # Try calling tool to make sure it doesn't give error
            obs = run_local_tool(api, action_input, TOOL_REGISTRY)
            if isinstance(obs, str) and 'error' in obs.lower() and '{' in obs:
                try:
                    j = json.loads(obs)
                    if 'error' in j: continue
                except: pass
            
            # Passed!
            demo_examples.append({
                "api": api,
                "query": session['query'],
                "action": api,
                "action_input": action_input,
                "final_ans": final_ans,
                "observation": obs
            })
            break
            
    except Exception as e:
        print("Failed to get", api, e)

with open(r'c:\Users\User\Downloads\專題比賽\server\LLMs_in_the_Imaginarium\Exploitation\valid_demos.json', 'w', encoding='utf-8') as f:
    json.dump(demo_examples, f, ensure_ascii=False, indent=2)

print("Generated", len(demo_examples), "demos")
