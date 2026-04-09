#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides ASF (African Swine Fever) knowledge base functionality.

Implements a KnowledgeSearcher over the structured markdown report and exposes
several FastMCP tools for querying chapters, searching keywords, and extracting
information from the comprehensive ASF report.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


from mcp.server.fastmcp import FastMCP


class ASFKnowledgeSearcher:
    """Knowledge base for African Swine Fever comprehensive report."""
    
    def __init__(self, md_file_path: str = "非洲豬瘟防疫與知識報告.md"):
        self.md_file_path = md_file_path
        self.raw_content: str = ""
        self.chapters: Dict[str, Dict[str, Any]] = {}
        self.load_data()
        self.parse_structure()

    def load_data(self) -> None:
        try:
            md_path = Path(__file__).parent / self.md_file_path
            with open(md_path, 'r', encoding='utf-8') as f:
                self.raw_content = f.read()
        except FileNotFoundError:
            raise RuntimeError(f"找不到檔案: {md_path}")
        except Exception as e:
            raise RuntimeError(f"載入資料失敗: {e}")

    def parse_structure(self) -> None:
        """Parse markdown into structured chapters and sections."""
        # Split by main chapter headings (##)
        chapter_pattern = re.compile(r'^## \*\*(第[一二三四五六七八九]+章)：(.+?)\*\*$', re.MULTILINE)
        matches = list(chapter_pattern.finditer(self.raw_content))
        
        for i, match in enumerate(matches):
            chapter_num = match.group(1)
            chapter_title = match.group(2)
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(self.raw_content)
            content = self.raw_content[start_pos:end_pos].strip()
            
            # Extract sections (###)
            sections = self._extract_sections(content)
            
            self.chapters[chapter_num] = {
                'title': chapter_title,
                'full_title': f"{chapter_num}：{chapter_title}",
                'content': content,
                'sections': sections,
                'length': len(content)
            }

    def _extract_sections(self, content: str) -> List[Dict[str, str]]:
        """Extract subsections from chapter content."""
        section_pattern = re.compile(r'^### \*\*(.+?)\*\*$', re.MULTILINE)
        matches = list(section_pattern.finditer(content))
        sections = []
        
        for i, match in enumerate(matches):
            section_title = match.group(1)
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()
            
            sections.append({
                'title': section_title,
                'content': section_content,
                'preview': section_content[:300] + '...' if len(section_content) > 300 else section_content
            })
        
        return sections

    def list_chapters(self) -> Dict[str, Any]:
        """List all chapters with titles."""
        chapter_list = []
        for ch_num, ch_data in self.chapters.items():
            chapter_list.append({
                'chapter': ch_num,
                'title': ch_data['title'],
                'full_title': ch_data['full_title'],
                'sections_count': len(ch_data['sections']),
                'content_length': ch_data['length']
            })
        return {'total_chapters': len(chapter_list), 'chapters': chapter_list}

    def get_chapter(self, chapter_id: str) -> Dict[str, Any]:
        """Get full content of a specific chapter."""
        # Support both "第一章" and "1" formats
        if chapter_id.isdigit():
            num_map = {'1': '第一章', '2': '第二章', '3': '第三章', '4': '第四章',
                      '5': '第五章', '6': '第六章', '7': '第七章', '8': '第八章', '9': '第九章'}
            chapter_id = num_map.get(chapter_id, chapter_id)
        
        if chapter_id not in self.chapters:
            return {'found': False, 'message': f'找不到章節: {chapter_id}'}
        
        ch = self.chapters[chapter_id]
        return {
            'found': True,
            'chapter': chapter_id,
            'title': ch['title'],
            'full_title': ch['full_title'],
            'content': ch['content'],
            'sections': [{'title': s['title'], 'preview': s['preview']} for s in ch['sections']]
        }

    def search_knowledge(self, keyword: str, limit: int = 10, case_sensitive: bool = False) -> Dict[str, Any]:
        """Search for keyword across all chapters."""
        if not keyword or not keyword.strip():
            return {'results': [], 'total': 0, 'message': '請提供搜尋關鍵字'}

        search_term = keyword if case_sensitive else keyword.lower()
        results = []

        for ch_num, ch_data in self.chapters.items():
            content = ch_data['content'] if case_sensitive else ch_data['content'].lower()
            
            if search_term in content:
                # Find all occurrences and extract context
                occurrences = []
                start = 0
                while True:
                    pos = content.find(search_term, start)
                    if pos == -1:
                        break
                    
                    # Extract context (200 chars before and after)
                    ctx_start = max(0, pos - 200)
                    ctx_end = min(len(ch_data['content']), pos + len(keyword) + 200)
                    context = ch_data['content'][ctx_start:ctx_end]
                    
                    # Highlight the keyword
                    context = self._highlight(context, keyword, case_sensitive)
                    occurrences.append({
                        'position': pos,
                        'context': ('...' if ctx_start > 0 else '') + context + ('...' if ctx_end < len(ch_data['content']) else '')
                    })
                    
                    start = pos + len(search_term)
                    if len(occurrences) >= 3:  # Limit to 3 occurrences per chapter
                        break
                
                results.append({
                    'chapter': ch_num,
                    'title': ch_data['full_title'],
                    'occurrences_count': content.count(search_term),
                    'sample_contexts': occurrences[:3]
                })

        results.sort(key=lambda x: x['occurrences_count'], reverse=True)
        return {
            'results': results[:limit],
            'total_chapters_matched': len(results),
            'keyword': keyword,
            'showing': min(limit, len(results))
        }

    def _highlight(self, text: str, term: str, case_sensitive: bool) -> str:
        """Highlight search term in text."""
        if not case_sensitive:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            return pattern.sub(lambda m: f"**{m.group()}**", text)
        else:
            return text.replace(term, f"**{term}**")

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics about the knowledge base."""
        total_chars = sum(ch['length'] for ch in self.chapters.values())
        total_sections = sum(len(ch['sections']) for ch in self.chapters.values())
        
        # Extract key terms count (simplified)
        full_text = self.raw_content.lower()
        key_terms = {
            '非洲豬瘟': full_text.count('非洲豬瘟'),
            '病毒': full_text.count('病毒'),
            '疫苗': full_text.count('疫苗'),
            '生物安全': full_text.count('生物安全'),
            '防疫': full_text.count('防疫'),
            '台灣': full_text.count('台灣'),
            '豬隻': full_text.count('豬隻')
        }
        
        return {
            'total_chapters': len(self.chapters),
            'total_sections': total_sections,
            'total_characters': total_chars,
            'average_chapter_length': total_chars // len(self.chapters) if self.chapters else 0,
            'key_terms_frequency': key_terms
        }

    def get_toc(self) -> Dict[str, Any]:
        """Get detailed table of contents."""
        toc = []
        for ch_num, ch_data in self.chapters.items():
            sections = [{'title': s['title']} for s in ch_data['sections']]
            toc.append({
                'chapter': ch_num,
                'title': ch_data['title'],
                'full_title': ch_data['full_title'],
                'sections': sections
            })
        return {'table_of_contents': toc}

    def get_references(self) -> Dict[str, Any]:
        """Extract references/citations from the report."""
        # Find the references section
        ref_pattern = re.compile(r'#### \*\*引用的著作\*\*(.+?)(?=^##|\Z)', re.MULTILINE | re.DOTALL)
        match = ref_pattern.search(self.raw_content)
        
        if not match:
            return {'found': False, 'message': '找不到參考文獻'}
        
        ref_text = match.group(1).strip()
        # Parse individual references
        refs = []
        for line in ref_text.split('\n'):
            line = line.strip()
            if line and re.match(r'^\d+\.', line):
                refs.append(line)
        
        return {
            'found': True,
            'total_references': len(refs),
            'references': refs
        }


# 初始化搜尋器與 MCP
searcher = ASFKnowledgeSearcher()
mcp = FastMCP("asf_knowledge")


@mcp.tool()
def list_chapters() -> str:
    """列出所有章節標題與簡介。"""
    try:
        result = searcher.list_chapters()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_chapter(chapter_id: str) -> str:
    """取得特定章節的完整內容。
    
    Args:
        chapter_id: 章節編號，可以是 "第一章" 或 "1"
    """
    try:
        result = searcher.get_chapter(chapter_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def search_knowledge(keyword: str, limit: int = 10, case_sensitive: bool = False) -> str:
    """搜尋關鍵字並返回相關章節與上下文。
    
    Args:
        keyword: 搜尋關鍵字
        limit: 最多返回幾個章節
        case_sensitive: 是否區分大小寫
    """
    try:
        result = searcher.search_knowledge(keyword=keyword, limit=limit, case_sensitive=case_sensitive)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_toc() -> str:
    """取得完整的目錄結構（包含所有章節與小節）。"""
    try:
        result = searcher.get_toc()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_statistics() -> str:
    """取得知識庫的統計資訊（總字數、章節數、關鍵詞出現頻率等）。"""
    try:
        result = searcher.get_statistics()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_references() -> str:
    """取得報告中的參考文獻列表。"""
    try:
        result = searcher.get_references()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
