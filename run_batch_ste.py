import os
import json
import ste_runner

# 這是您指定要重新執行 STE 的 API 清單
TARGET_APIS = [
    "nchu_course_teachers_search_by_department",
    "nchu_cross_program_get_program_courses",
    "nchu_cross_program_get_stats",
    "nchu_cross_program_get_weekly_content",
    "nchu_cross_program_search_by_program",
    "nchu_cross_program_search_by_keyword",
    "nchu_cross_program_search_by_teacher",
    "nchu_cross_program_search_by_time",
    "nchu_education_get_all_departments",
    "nchu_education_get_all_programs",
    "nchu_education_get_all_teachers",
    "nchu_education_get_detail",
    "nchu_education_get_program_courses",
    "nchu_education_get_stats",
    "nchu_education_get_weekly_content",
    "nchu_education_search_across_semesters",
    "nchu_education_search_by_department",
    "nchu_education_search_by_keyword",
    "nchu_education_search_by_program",
    "nchu_education_search_by_teacher",
    "nchu_education_search_by_time",
    "nchu_education_search_syllabus",
    "nchu_ge_course_search_by_sdg",
    "rule_list_all",
    "rule_search_by_query",
    "nchu_course_teachers_get_courses",
    "nchu_course_teachers_get_detail",
    "nchu_course_teachers_search",
    "nchu_course_teachers_search_by_name",
    "nchu_ge_course_get_teacher_courses",
    "nchu_ge_course_get_teacher_history",
    "nchu_ge_course_search_by_teacher",
    "nchu_course_get_weekly_content",
    "nchu_course_search_across_semesters",
    "nchu_course_search_by_assessment_method",
    "nchu_course_search_by_keyword",
    "nchu_cross_program_get_detail",
    "nchu_ge_course_get_weekly_content"
]

def main():
    print(f"準備執行 {len(TARGET_APIS)} 個指定的 API...")
    
    # 檢查這些 API 是否存在於原始的 tool_registry.json 中
    missing = [api for api in TARGET_APIS if api not in ste_runner.TOOL_REGISTRY]
    if missing:
        print(f"⚠️ 以下 API 不在原始的 tool_registry 中，將被略過: {missing}")
    
    # 在記憶體中動態過濾 TOOL_REGISTRY，這樣就不會動到實際檔案
    filtered_registry = {k: v for k, v in ste_runner.TOOL_REGISTRY.items() if k in TARGET_APIS}
    
    if not filtered_registry:
        print("❌ 沒有找到任何可執行的 API！")
        return
        
    print(f"✅ 成功過濾出 {len(filtered_registry)} 個 API 準備執行。")
    
    # 覆蓋 ste_runner 記憶體中的 TOOL_REGISTRY
    ste_runner.TOOL_REGISTRY = filtered_registry
    
    # 執行 ste_runner 的主程式
    # 參數可依據需求調整，這裡先使用您的預設值
    ste_runner.main(
        model_ckpt="qwen3:32b",
        num_episodes=5,
        num_stm_slots=2,
        max_turn=5,
        dir_write="results/ste/"
    )

if __name__ == "__main__":
    main()
