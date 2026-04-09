#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides ASF notices/announcements search functionality.

非洲豬瘟宣導資訊查詢工具，提供防疫檢疫須知、邊境管制措施、案例處置等宣導文件搜尋。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP


class ASFFNoticesSearcher:
    def __init__(self, json_file_path: str = "../data/asf/asf_notices.json"):
        """
        初始化非洲豬瘟宣導資訊搜尋器
        
        Args:
            json_file_path: JSON 檔案路徑
        """
        self.json_file_path = json_file_path
        self.notices: List[Dict[str, Any]] = []
        self.load_data()

    def load_data(self) -> None:
        """載入宣導資訊資料"""
        try:
            json_path = Path(__file__).parent / self.json_file_path
            with open(json_path, 'r', encoding='utf-8') as f:
                self.notices = json.load(f)
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {json_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 格式錯誤: {e}")
        except Exception as e:
            raise RuntimeError(f"載入資料失敗: {e}")

    def search_notices(
        self,
        keyword: str,
        limit: int = 10,
        case_sensitive: bool = False,
        search_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        搜尋宣導資訊
        
        Args:
            keyword: 搜尋關鍵字
            limit: 回傳結果數量限制
            case_sensitive: 是否區分大小寫
            search_fields: 要搜尋的欄位列表 (title, content)
        
        Returns:
            搜尋結果字典
        """
        if search_fields is None:
            search_fields = ['title', 'content']
        
        if not keyword or not keyword.strip():
            return {
                'results': [],
                'total': 0,
                'message': '請提供搜尋關鍵字'
            }
        
        search_term = keyword if case_sensitive else keyword.lower()
        matching_notices = []
        
        for notice in self.notices:
            match_info = self._search_in_notice(
                notice, search_term, search_fields, case_sensitive
            )
            
            if match_info['is_match']:
                matching_notices.append({
                    'notice': self._format_notice_result(notice),
                    'relevance_score': match_info['score'],
                    'matched_fields': match_info['matched_fields'],
                    'matched_content': match_info['matched_content']
                })
        
        # 按相關度排序
        matching_notices.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # 限制結果數量
        limited_results = matching_notices[:limit]
        
        return {
            'results': limited_results,
            'total': len(matching_notices),
            'keyword': keyword,
            'search_fields': search_fields,
            'showing': len(limited_results)
        }

    def _search_in_notice(
        self,
        notice: Dict[str, Any],
        search_term: str,
        search_fields: List[str],
        case_sensitive: bool
    ) -> Dict[str, Any]:
        """在單一宣導資訊中搜尋"""
        score = 0
        matched_fields = []
        matched_content = {}
        
        # 搜尋標題
        if 'title' in search_fields:
            title = notice.get('title', '')
            match = self._check_match(title, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 3  # 標題權重較高
                matched_fields.append('title')
                matched_content['title'] = self._highlight_matches(
                    title, search_term, case_sensitive, max_length=500
                )
        
        # 搜尋內容
        if 'content' in search_fields:
            content = notice.get('content', '')
            match = self._check_match(content, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 2
                matched_fields.append('content')
                matched_content['content'] = self._highlight_matches(
                    content, search_term, case_sensitive, max_length=800
                )
        
        return {
            'is_match': score > 0,
            'score': score,
            'matched_fields': matched_fields,
            'matched_content': matched_content
        }

    def _check_match(self, text: str, search_term: str, case_sensitive: bool) -> Dict[str, Any]:
        """檢查文字匹配"""
        if not text or not search_term:
            return {'is_match': False, 'score': 0}
        
        text_to_search = text if case_sensitive else text.lower()
        
        if search_term in text_to_search:
            # 計算相關度分數
            match_ratio = len(search_term) / len(text_to_search)
            score = min(match_ratio * 10, 5) + 1
            return {'is_match': True, 'score': score}
        
        return {'is_match': False, 'score': 0}

    def _highlight_matches(
        self,
        text: str,
        search_term: str,
        case_sensitive: bool,
        max_length: int = 800
    ) -> str:
        """高亮匹配內容"""
        if not text or not search_term:
            return text
        
        # 限制文字長度
        if len(text) > max_length:
            # 找到搜尋詞的位置
            search_pos = (
                text.lower().find(search_term.lower())
                if not case_sensitive
                else text.find(search_term)
            )
            if search_pos != -1:
                # 以搜尋詞為中心截取文字
                start = max(0, search_pos - max_length // 3)
                end = min(len(text), start + max_length)
                text = text[start:end]
                if start > 0:
                    text = "..." + text
                if end < len(text):
                    text = text + "..."
        
        if case_sensitive:
            return text.replace(search_term, f"**{search_term}**")
        else:
            # 不區分大小寫的替換
            pattern = re.compile(re.escape(search_term), re.IGNORECASE)
            return pattern.sub(lambda m: f"**{m.group()}**", text)

    def _format_notice_result(self, notice: Dict[str, Any], include_full_content: bool = False) -> Dict[str, Any]:
        """格式化宣導資訊結果"""
        metadata = notice.get('metadata', {})
        
        result = {
            'title': notice.get('title', ''),
            'url': metadata.get('url', ''),
            'timestamp': metadata.get('timestamp', '')
        }
        
        # 如果需要完整內容才包含
        if include_full_content:
            result['content'] = notice.get('content', '')
        
        return result

    def get_notice_by_title(self, title: str, exact_match: bool = False) -> Dict[str, Any]:
        """
        根據標題獲取宣導資訊
        
        Args:
            title: 標題關鍵字
            exact_match: 是否精確匹配
        
        Returns:
            匹配的宣導資訊
        """
        for notice in self.notices:
            notice_title = notice.get('title', '')
            
            is_match = False
            if exact_match:
                is_match = notice_title == title
            else:
                is_match = title in notice_title
            
            if is_match:
                return {
                    'found': True,
                    'notice': {
                        'title': notice.get('title', ''),
                        'content': notice.get('content', ''),
                        'url': notice.get('metadata', {}).get('url', ''),
                        'timestamp': notice.get('metadata', {}).get('timestamp', '')
                    }
                }
        
        return {
            'found': False,
            'message': f'找不到標題包含「{title}」的宣導資訊'
        }

    def get_all_notices(self, include_content: bool = False) -> Dict[str, Any]:
        """
        獲取所有宣導資訊列表
        
        Args:
            include_content: 是否包含完整內容
        
        Returns:
            所有宣導資訊
        """
        all_notices = []
        for notice in self.notices:
            item = {
                'title': notice.get('title', ''),
                'url': notice.get('metadata', {}).get('url', ''),
                'timestamp': notice.get('metadata', {}).get('timestamp', '')
            }
            if include_content:
                item['content'] = notice.get('content', '')
            all_notices.append(item)
        
        return {
            'total': len(all_notices),
            'notices': all_notices
        }

    def get_stats(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        if not self.notices:
            return {'message': '宣導資訊資料未載入'}
        
        stats = {
            '總宣導資訊數': len(self.notices),
            '有內容的資訊數': sum(1 for n in self.notices if n.get('content', '').strip()),
            '空內容的資訊數': sum(1 for n in self.notices if not n.get('content', '').strip())
        }
        
        return stats

    def get_border_control_info(self) -> Dict[str, Any]:
        """獲取邊境管制相關資訊（專門查詢功能）"""
        results = self.search_notices(
            keyword='邊境',
            limit=20,
            search_fields=['title', 'content']
        )
        
        border_notices = []
        for item in results['results']:
            notice_data = item['notice']
            # 從原始資料中找到完整內容
            for notice in self.notices:
                if notice.get('title') == notice_data.get('title'):
                    border_notices.append({
                        'title': notice.get('title'),
                        'content': notice.get('content'),
                        'url': notice.get('metadata', {}).get('url'),
                        'timestamp': notice.get('metadata', {}).get('timestamp')
                    })
                    break
        
        return {
            'total': len(border_notices),
            'border_control_info': border_notices
        }

    def get_biosecurity_measures(self) -> Dict[str, Any]:
        """獲取生物安全措施相關資訊"""
        results = self.search_notices(
            keyword='生物安全',
            limit=20,
            search_fields=['title', 'content']
        )
        
        biosecurity_notices = []
        for item in results['results']:
            notice_data = item['notice']
            for notice in self.notices:
                if notice.get('title') == notice_data.get('title'):
                    biosecurity_notices.append({
                        'title': notice.get('title'),
                        'content': notice.get('content'),
                        'url': notice.get('metadata', {}).get('url'),
                        'timestamp': notice.get('metadata', {}).get('timestamp')
                    })
                    break
        
        return {
            'total': len(biosecurity_notices),
            'biosecurity_measures': biosecurity_notices
        }


# 初始化全域搜尋器
searcher = ASFFNoticesSearcher()

mcp = FastMCP("asf_notices_search")


@mcp.tool()
def search_notices(
    keyword: str,
    limit: int = 10,
    search_fields: str | None = None,
    case_sensitive: bool = False
) -> str:
    """Search for ASF notices/announcements (搜尋非洲豬瘟宣導資訊).
    
    Args:
        keyword: Search keyword (搜尋關鍵字)
        limit: Maximum number of results to return (default: 10)
        search_fields: Comma-separated fields to search in: title,content (default: all)
        case_sensitive: Whether search is case sensitive (default: False)
    
    Returns:
        JSON string containing search results
    """
    try:
        fields = None
        if search_fields:
            fields = [field.strip() for field in search_fields.split(',')]
        
        results = searcher.search_notices(
            keyword=keyword,
            limit=limit,
            search_fields=fields,
            case_sensitive=case_sensitive
        )
        
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'搜尋宣導資訊時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_all_notices(include_content: bool = False) -> str:
    """Get all ASF notices (獲取所有非洲豬瘟宣導資訊).
    
    Args:
        include_content: Whether to include full content (default: False)
    
    Returns:
        JSON string containing all notices
    """
    try:
        results = searcher.get_all_notices(include_content=include_content)
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取宣導資訊列表時發生錯誤: {str(e)}',
            'notices': []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_notice_by_title(title: str, exact_match: bool = False) -> str:
    """Get a specific notice by its title (根據標題獲取特定宣導資訊).
    
    Args:
        title: Notice title or keyword (宣導資訊標題或關鍵字)
        exact_match: Whether to use exact match (default: False)
    
    Returns:
        JSON string containing the notice details
    """
    try:
        result = searcher.get_notice_by_title(title, exact_match)
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取宣導資訊時發生錯誤: {str(e)}',
            'found': False
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_notices_stats() -> str:
    """Get statistics about the ASF notices database (獲取宣導資訊統計).
    
    Returns:
        JSON string containing database statistics
    """
    try:
        stats = searcher.get_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取統計資訊時發生錯誤: {str(e)}',
            'message': '無法獲取統計資訊'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_border_control_info() -> str:
    """Get border control related information (獲取邊境管制相關資訊).
    
    Returns:
        JSON string containing border control information
    """
    try:
        results = searcher.get_border_control_info()
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取邊境管制資訊時發生錯誤: {str(e)}',
            'border_control_info': []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_biosecurity_measures() -> str:
    """Get biosecurity measures information (獲取生物安全措施資訊).
    
    Returns:
        JSON string containing biosecurity measures
    """
    try:
        results = searcher.get_biosecurity_measures()
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取生物安全措施資訊時發生錯誤: {str(e)}',
            'biosecurity_measures': []
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
