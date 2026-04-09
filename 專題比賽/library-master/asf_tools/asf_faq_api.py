#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides African Swine Fever FAQ search functionality."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Any

from mcp.server.fastmcp import FastMCP


class ASFFAQSearcher:
    def __init__(self, json_file_path="../data/asf/asf_faqs.json"):
        """
        初始化非洲豬瘟FAQ搜尋器
        
        Args:
            json_file_path: JSON 檔案路徑
        """
        self.json_file_path = json_file_path
        self.faqs = []
        self.load_data()
    
    def load_data(self):
        """載入FAQ資料"""
        try:
            json_path = Path(__file__).parent / self.json_file_path
            with open(json_path, 'r', encoding='utf-8') as f:
                self.faqs = json.load(f)
            
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {json_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 格式錯誤: {e}")
        except Exception as e:
            raise RuntimeError(f"載入資料失敗: {e}")
    
    def search_faqs(self, 
                    keyword, 
                    limit=10,
                    search_fields=None,
                    case_sensitive=False):
        """
        搜尋FAQ
        
        Args:
            keyword: 搜尋關鍵字
            limit: 回傳結果數量限制
            search_fields: 要搜尋的欄位列表 (title, content, classification)
            case_sensitive: 是否區分大小寫
        
        Returns:
            搜尋結果字典
        """
        if search_fields is None:
            search_fields = ['title', 'content', 'classification']
        
        if not keyword.strip():
            return {
                'results': [],
                'total': 0,
                'message': '請提供搜尋關鍵字'
            }
        
        search_term = keyword if case_sensitive else keyword.lower()
        matching_faqs = []
        
        for faq in self.faqs:
            match_info = self._search_in_faq(
                faq, search_term, search_fields, case_sensitive
            )
            
            if match_info['is_match']:
                matching_faqs.append({
                    'faq': self._format_faq_result(faq),
                    'relevance_score': match_info['score'],
                    'matched_fields': match_info['matched_fields'],
                    'matched_content': match_info['matched_content']
                })
        
        # 按相關度排序
        matching_faqs.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # 限制結果數量
        limited_results = matching_faqs[:limit]
        
        return {
            'results': limited_results,
            'total': len(matching_faqs),
            'keyword': keyword,
            'search_fields': search_fields,
            'showing': len(limited_results)
        }
    
    def _search_in_faq(self, faq, search_term, 
                       search_fields, case_sensitive):
        """在單一FAQ中搜尋"""
        score = 0
        matched_fields = []
        matched_content = {}
        
        # 搜尋標題
        if 'title' in search_fields:
            title = faq.get('title', '')
            match = self._check_match(title, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 3  # 標題權重較高
                matched_fields.append('title')
                matched_content['title'] = self._highlight_matches(
                    title, search_term, case_sensitive, max_length=500
                )
        
        # 搜尋內容
        if 'content' in search_fields:
            content = faq.get('content', '')
            match = self._check_match(content, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 2
                matched_fields.append('content')
                matched_content['content'] = self._highlight_matches(
                    content, search_term, case_sensitive, max_length=500
                )
        
        # 搜尋分類
        if 'classification' in search_fields:
            classification = faq.get('metadata', {}).get('classification', '')
            match = self._check_match(classification, search_term, case_sensitive)
            if match['is_match']:
                score += match['score'] * 2.5  # 分類權重較高
                matched_fields.append('classification')
                matched_content['classification'] = classification
        
        return {
            'is_match': score > 0,
            'score': score,
            'matched_fields': matched_fields,
            'matched_content': matched_content
        }
    
    def _check_match(self, text, search_term, case_sensitive):
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
    
    def _highlight_matches(self, text, search_term, case_sensitive, max_length=500):
        """高亮匹配內容"""
        if not text or not search_term:
            return text
        
        # 限制文字長度
        if len(text) > max_length:
            # 找到搜尋詞的位置
            search_pos = text.lower().find(search_term.lower()) if not case_sensitive else text.find(search_term)
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
    
    def _format_faq_result(self, faq, include_full_content=False):
        """格式化FAQ結果"""
        metadata = faq.get('metadata', {})
        
        result = {
            'title': faq.get('title', ''),
            'classification': metadata.get('classification', ''),
            'url': metadata.get('url', '')
        }
        
        # 如果需要完整內容才包含
        if include_full_content:
            result['content'] = faq.get('content', '')
            result['timestamp'] = metadata.get('timestamp', '')
        
        return result
    
    def search_by_classification(self, classification, limit=20):
        """按分類搜尋FAQ"""
        matching_faqs = []
        
        for faq in self.faqs:
            faq_classification = faq.get('metadata', {}).get('classification', '')
            
            if classification in faq_classification:
                matching_faqs.append({
                    'faq': self._format_faq_result(faq, include_full_content=True),
                    'relevance_score': 5,
                    'matched_fields': ['classification'],
                    'matched_content': {'classification': faq_classification}
                })
        
        return {
            'results': matching_faqs[:limit],
            'total': len(matching_faqs),
            'classification': classification
        }
    
    def get_all_classifications(self):
        """
        獲取所有分類及其FAQ數量
        
        Returns:
            分類統計資訊
        """
        classification_stats = {}
        classification_faqs = {}
        
        for faq in self.faqs:
            classification = faq.get('metadata', {}).get('classification', '未分類')
            
            if classification not in classification_stats:
                classification_stats[classification] = 0
                classification_faqs[classification] = []
            
            classification_stats[classification] += 1
            classification_faqs[classification].append({
                'title': faq.get('title', ''),
                'url': faq.get('metadata', {}).get('url', '')
            })
        
        # 按FAQ數量排序
        sorted_classifications = sorted(
            classification_stats.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return {
            'total_classifications': len(classification_stats),
            'classification_stats': dict(sorted_classifications),
            'classification_faqs': classification_faqs
        }
    
    def get_stats(self):
        """獲取統計資訊"""
        if not self.faqs:
            return {'message': 'FAQ資料未載入'}
        
        stats = {
            '總FAQ數': len(self.faqs),
            '分類統計': {}
        }
        
        # 統計分類分布
        for faq in self.faqs:
            classification = faq.get('metadata', {}).get('classification', '未分類')
            stats['分類統計'][classification] = stats['分類統計'].get(classification, 0) + 1
        
        return stats
    
    def get_faq_by_title(self, title, exact_match=False):
        """
        根據標題獲取FAQ
        
        Args:
            title: 標題關鍵字
            exact_match: 是否精確匹配
        
        Returns:
            匹配的FAQ
        """
        for faq in self.faqs:
            faq_title = faq.get('title', '')
            
            is_match = False
            if exact_match:
                is_match = faq_title == title
            else:
                is_match = title in faq_title
            
            if is_match:
                return {
                    'found': True,
                    'faq': {
                        'title': faq.get('title', ''),
                        'content': faq.get('content', ''),
                        'classification': faq.get('metadata', {}).get('classification', ''),
                        'url': faq.get('metadata', {}).get('url', ''),
                        'timestamp': faq.get('metadata', {}).get('timestamp', '')
                    }
                }
        
        return {
            'found': False,
            'message': f'找不到標題包含「{title}」的FAQ'
        }


# 初始化全域搜尋器
searcher = ASFFAQSearcher()

mcp = FastMCP("asf_faq_search")


@mcp.tool()
def search_asf_faqs(
    keyword: str, 
    limit: int = 10, 
    search_fields: str | None = None, 
    case_sensitive: bool = False
) -> str:
    """Search for African Swine Fever FAQs.
    
    Args:
        keyword: Search keyword (搜尋關鍵字)
        limit: Maximum number of results to return (default: 10)
        search_fields: Comma-separated fields to search in: title,content,classification (default: all)
        case_sensitive: Whether search is case sensitive (default: False)
    
    Returns:
        JSON string containing search results
    """
    try:
        fields = None
        if search_fields:
            fields = [field.strip() for field in search_fields.split(',')]
        
        results = searcher.search_faqs(
            keyword=keyword,
            limit=limit,
            search_fields=fields,
            case_sensitive=case_sensitive
        )
        
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'搜尋FAQ時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def search_by_classification(classification: str, limit: int = 20) -> str:
    """Search FAQs by classification.
    
    Args:
        classification: Classification to search for (分類名稱，例如：認識非洲豬瘟、入境檢疫、肉品檢疫等)
        limit: Maximum number of results to return (default: 20)
    
    Returns:
        JSON string containing search results
    """
    try:
        results = searcher.search_by_classification(classification, limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'按分類搜尋FAQ時發生錯誤: {str(e)}',
            'results': [],
            'total': 0
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_all_classifications() -> str:
    """Get all FAQ classifications and their statistics.
    
    Returns:
        JSON string containing all classifications and their FAQ counts
    """
    try:
        results = searcher.get_all_classifications()
        return json.dumps(results, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取分類列表時發生錯誤: {str(e)}',
            'message': '無法獲取分類列表'
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_asf_faq_stats() -> str:
    """Get statistics about the African Swine Fever FAQ database.
    
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
def get_faq_by_title(title: str, exact_match: bool = False) -> str:
    """Get a specific FAQ by its title.
    
    Args:
        title: FAQ title or keyword (FAQ標題或關鍵字)
        exact_match: Whether to use exact match (default: False)
    
    Returns:
        JSON string containing the FAQ details
    """
    try:
        result = searcher.get_faq_by_title(title, exact_match)
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取FAQ時發生錯誤: {str(e)}',
            'found': False
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_prevention_guidelines() -> str:
    """Get prevention guidelines for African Swine Fever (防疫指南).
    
    Returns:
        JSON string containing prevention guidelines
    """
    try:
        # 搜尋與防疫相關的FAQ
        results = searcher.search_faqs(
            keyword='防範',
            limit=20,
            search_fields=['title', 'content', 'classification']
        )
        
        prevention_faqs = []
        for item in results['results']:
            faq_data = item['faq']
            # 從原始資料中找到完整內容
            for faq in searcher.faqs:
                if faq.get('title') == faq_data.get('title'):
                    prevention_faqs.append({
                        'title': faq.get('title'),
                        'content': faq.get('content'),
                        'classification': faq.get('metadata', {}).get('classification'),
                        'url': faq.get('metadata', {}).get('url')
                    })
                    break
        
        return json.dumps({
            'total': len(prevention_faqs),
            'guidelines': prevention_faqs
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取防疫指南時發生錯誤: {str(e)}',
            'guidelines': []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_border_quarantine_info() -> str:
    """Get information about border quarantine measures (入境檢疫資訊).
    
    Returns:
        JSON string containing border quarantine information
    """
    try:
        results = searcher.search_by_classification('入境檢疫', limit=50)
        
        quarantine_faqs = []
        for item in results['results']:
            faq_data = item['faq']
            quarantine_faqs.append(faq_data)
        
        return json.dumps({
            'total': len(quarantine_faqs),
            'quarantine_info': quarantine_faqs
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取入境檢疫資訊時發生錯誤: {str(e)}',
            'quarantine_info': []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_meat_product_regulations() -> str:
    """Get regulations about meat products (肉品檢疫規定).
    
    Returns:
        JSON string containing meat product regulations
    """
    try:
        results = searcher.search_by_classification('肉品檢疫', limit=50)
        
        meat_faqs = []
        for item in results['results']:
            faq_data = item['faq']
            meat_faqs.append(faq_data)
        
        return json.dumps({
            'total': len(meat_faqs),
            'regulations': meat_faqs
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'獲取肉品檢疫規定時發生錯誤: {str(e)}',
            'regulations': []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def search_penalty_info(keyword: str = "罰") -> str:
    """Search for penalty and legal information (罰則資訊).
    
    Args:
        keyword: Keyword related to penalties (default: "罰")
    
    Returns:
        JSON string containing penalty information
    """
    try:
        # 搜尋包含罰則的FAQ
        results = searcher.search_faqs(
            keyword=keyword,
            limit=20,
            search_fields=['title', 'content']
        )
        
        # 同時搜尋相關法規分類
        law_results = searcher.search_by_classification('相關法規', limit=20)
        
        penalty_faqs = []
        
        # 合併結果
        for item in results['results']:
            faq_data = item['faq']
            for faq in searcher.faqs:
                if faq.get('title') == faq_data.get('title'):
                    penalty_faqs.append({
                        'title': faq.get('title'),
                        'content': faq.get('content'),
                        'classification': faq.get('metadata', {}).get('classification'),
                        'url': faq.get('metadata', {}).get('url')
                    })
                    break
        
        for item in law_results['results']:
            faq_data = item['faq']
            # 避免重複
            if not any(f['title'] == faq_data.get('title') for f in penalty_faqs):
                penalty_faqs.append(faq_data)
        
        return json.dumps({
            'total': len(penalty_faqs),
            'penalty_info': penalty_faqs
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            'error': f'搜尋罰則資訊時發生錯誤: {str(e)}',
            'penalty_info': []
        }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
