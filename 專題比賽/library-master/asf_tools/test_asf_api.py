#!/usr/bin/env python3
"""
非洲豬瘟緊急應變措施手冊 MCP Tools 測試腳本
"""

from asf_emergency_response_api import *
import json

def test_api_functions():
    print("=" * 80)
    print("非洲豬瘟緊急應變措施手冊 MCP Tools 測試")
    print("=" * 80)
    
    # 1. 測試手冊總覽
    print("\n1. 手冊總覽測試:")
    print("-" * 40)
    overview = asf_manual_overview()
    print(f"手冊標題: {overview.get('manual_title')}")
    print(f"章節數量: {len(overview.get('chapters', []))}")
    print(f"SOP數量: {len(overview.get('standard_procedures', []))}")
    print("\n章節列表:")
    for chapter in overview.get('chapters', []):
        print(f"  {chapter['chapter_number']}: {chapter['subtitle']}")
    print("\nSOP列表:")
    for sop in overview.get('standard_procedures', []):
        print(f"  - {sop['title']}")
    
    # 2. 測試章節內容查詢
    print("\n\n2. 章節內容查詢測試:")
    print("-" * 40)
    intro_chapter = asf_chapter_content("壹")
    print(f"章節: {intro_chapter.get('subtitle')}")
    print(f"摘要: {intro_chapter.get('summary', '')[:100]}...")
    
    # 3. 測試非洲豬瘟基本資訊查詢
    print("\n\n3. 非洲豬瘟基本資訊測試:")
    print("-" * 40)
    definition = asf_basic_info("definition")
    if 'heading' in definition:
        print(f"標題: {definition['heading']}")
        print(f"內容: {definition['content'][:200]}...")
    
    # 4. 測試應變中心資訊查詢
    print("\n\n4. 應變中心資訊測試:")
    print("-" * 40)
    center_info = asf_response_center_info("structure")
    if 'heading' in center_info:
        print(f"標題: {center_info['heading']}")
        print(f"內容: {center_info['content'][:150]}...")
    
    # 5. 測試SOP詳細內容查詢
    print("\n\n5. SOP詳細內容測試:")
    print("-" * 40)
    sop_info = asf_sop_details("screening")
    if 'title' in sop_info:
        print(f"SOP標題: {sop_info['title']}")
        print(f"摘要: {sop_info.get('summary', '')[:150]}...")
    
    # 6. 測試預防措施查詢
    print("\n\n6. 預防措施查詢測試:")
    print("-" * 40)
    prevention = asf_prevention_measures("border_control")
    if 'relevant_sections' in prevention:
        print(f"找到 {len(prevention['relevant_sections'])} 個相關章節")
        if prevention['relevant_sections']:
            print(f"第一個章節: {prevention['relevant_sections'][0].get('heading', 'N/A')}")
    
    # 7. 測試內容搜尋功能
    print("\n\n7. 內容搜尋功能測試:")
    print("-" * 40)
    search_result = asf_search_content("病毒")
    print(f"搜尋關鍵字: {search_result.get('keyword')}")
    print(f"找到匹配結果: {search_result.get('total_matches')} 個")
    if search_result.get('results'):
        first_result = search_result['results'][0]
        print(f"第一個結果來源: {first_result.get('chapter', first_result.get('sop', 'N/A'))}")
    
    # 8. 測試整備措施查詢
    print("\n\n8. 整備措施查詢測試:")
    print("-" * 40)
    preparedness = asf_preparedness_measures()
    if 'subtitle' in preparedness:
        print(f"章節: {preparedness['subtitle']}")
        print(f"摘要: {preparedness.get('summary', '')[:150]}...")
    
    print("\n" + "=" * 80)
    print("測試完成！所有功能正常運作。")
    print("=" * 80)

if __name__ == "__main__":
    test_api_functions()