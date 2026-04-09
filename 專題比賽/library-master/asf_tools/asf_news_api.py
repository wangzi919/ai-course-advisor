#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides ASF news search functionality.

Implements a NewsSearcher over `asf_news.json` and exposes several FastMCP
tools similar to `course_search_api.py` and `asf_faq_api.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP


class ASFFNewsSearcher:
    def __init__(self, json_file_path: str = "../data/asf/asf_news.json"):
        self.json_file_path = json_file_path
        self.news: List[Dict[str, Any]] = []
        self.load_data()

    def load_data(self) -> None:
        try:
            json_path = Path(__file__).parent / self.json_file_path
            with open(json_path, 'r', encoding='utf-8') as f:
                self.news = json.load(f)
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {json_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 格式錯誤: {e}")
        except Exception as e:
            raise RuntimeError(f"載入資料失敗: {e}")

    def search_news(self, keyword: str, limit: int = 10, case_sensitive: bool = False,
                    search_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        if search_fields is None:
            search_fields = ['title', 'content', 'metadata.url']

        if not keyword or not keyword.strip():
            return {'results': [], 'total': 0, 'message': '請提供搜尋關鍵字'}

        search_term = keyword if case_sensitive else keyword.lower()
        results = []

        for item in self.news:
            score = 0.0
            matched_fields = []
            matched_content = {}

            # title
            if 'title' in search_fields:
                title = item.get('title', '')
                match = self._check_match(title, search_term, case_sensitive)
                if match['is_match']:
                    score += match['score'] * 3
                    matched_fields.append('title')
                    matched_content['title'] = self._highlight(title, search_term, case_sensitive)

            # content
            if 'content' in search_fields:
                content = item.get('content', '')
                match = self._check_match(content, search_term, case_sensitive)
                if match['is_match']:
                    score += match['score'] * 2
                    matched_fields.append('content')
                    matched_content['content'] = self._highlight(content, search_term, case_sensitive)

            # metadata fields (url, timestamp, classification)
            meta = item.get('metadata', {})
            if 'classification' in search_fields:
                cls = meta.get('classification', '')
                match = self._check_match(cls, search_term, case_sensitive)
                if match['is_match']:
                    score += match['score'] * 2
                    matched_fields.append('classification')
                    matched_content['classification'] = cls

            if 'url' in search_fields or 'metadata.url' in search_fields:
                url = meta.get('url', '')
                match = self._check_match(url, search_term, case_sensitive)
                if match['is_match']:
                    score += match['score'] * 1.5
                    if 'url' not in matched_fields:
                        matched_fields.append('url')
                    matched_content['url'] = url

            if score > 0:
                results.append({
                    'news': {
                        'title': item.get('title', ''),
                        'url': meta.get('url', ''),
                        'timestamp': meta.get('timestamp', ''),
                    },
                    'relevance_score': score,
                    'matched_fields': matched_fields,
                    'matched_content': matched_content
                })

        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return {
            'results': results[:limit],
            'total': len(results),
            'keyword': keyword,
            'showing': min(limit, len(results))
        }

    def _check_match(self, text: str, search_term: str, case_sensitive: bool) -> Dict[str, Any]:
        if not text:
            return {'is_match': False, 'score': 0}
        hay = text if case_sensitive else text.lower()
        if search_term in hay:
            match_ratio = len(search_term) / max(len(hay), 1)
            score = min(match_ratio * 10, 5) + 1
            return {'is_match': True, 'score': score}
        return {'is_match': False, 'score': 0}

    def _highlight(self, text: str, term: str, case_sensitive: bool, maxlen: int = 400) -> str:
        if not text:
            return text
        if not case_sensitive:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            repl = lambda m: f"**{m.group()}**"
            out = pattern.sub(repl, text)
        else:
            out = text.replace(term, f"**{term}**")

        if len(out) > maxlen:
            pos = (out.lower() if not case_sensitive else out).find(term.lower() if not case_sensitive else term)
            if pos != -1:
                start = max(0, pos - maxlen // 3)
                end = min(len(out), start + maxlen)
                out = ("..." if start > 0 else "") + out[start:end] + ("..." if end < len(out) else "")
        return out

    def get_latest(self, limit: int = 5) -> Dict[str, Any]:
        # assume metadata.timestamp in YYYY-MM-DD or similar; sort by string desc
        sorted_news = sorted(self.news, key=lambda x: x.get('metadata', {}).get('timestamp', ''), reverse=True)
        latest = []
        for item in sorted_news[:limit]:
            latest.append({
                'title': item.get('title', ''),
                'url': item.get('metadata', {}).get('url', ''),
                'timestamp': item.get('metadata', {}).get('timestamp', ''),
                'snippet': (item.get('content') or '')[:300]
            })
        return {'total': len(latest), 'latest': latest}

    def get_news_by_title(self, title: str, exact: bool = False) -> Dict[str, Any]:
        for item in self.news:
            t = item.get('title', '')
            if (exact and t == title) or (not exact and title in t):
                return {'found': True, 'news': item}
        return {'found': False, 'message': f'找不到標題包含: {title}'}

    def get_stats(self) -> Dict[str, Any]:
        total = len(self.news)
        # build per-month counts if timestamps exist
        by_month: Dict[str, int] = {}
        for item in self.news:
            ts = item.get('metadata', {}).get('timestamp', '')
            if ts:
                key = ts[:7]  # YYYY-MM
            else:
                key = 'unknown'
            by_month[key] = by_month.get(key, 0) + 1
        return {'total_news': total, 'by_month': dict(sorted(by_month.items(), reverse=True))}


# 初始化搜尋器與 MCP
searcher = ASFFNewsSearcher()
mcp = FastMCP("asf_news_search")


@mcp.tool()
def search_news(keyword: str, limit: int = 10, case_sensitive: bool = False, search_fields: Optional[str] = None) -> str:
    try:
        fields = None
        if search_fields:
            fields = [f.strip() for f in search_fields.split(',')]
        results = searcher.search_news(keyword=keyword, limit=limit, case_sensitive=case_sensitive, search_fields=fields)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_latest_news(limit: int = 5) -> str:
    try:
        results = searcher.get_latest(limit=limit)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_news_stats() -> str:
    try:
        stats = searcher.get_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_news_by_title(title: str, exact: bool = False) -> str:
    try:
        res = searcher.get_news_by_title(title, exact)
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
