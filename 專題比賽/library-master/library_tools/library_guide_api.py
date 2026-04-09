#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastMCP tool that provides NCHU library guide/manual functionality."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from mcp.server.fastmcp import FastMCP


class LibraryGuideManager:
    """Manager for NCHU library guide/manual."""

    def __init__(self):
        """
        Initialize the library guide manager.
        """
        self.parent_dir = Path(__file__).parent.parent
        self.data_file_path = self.parent_dir / \
            "data/library/nchu_library_guides.json"
        self.manual_data: Dict = {}
        self.load_data()

    def load_data(self) -> bool:
        """Load library guide data from JSON file.

        Returns:
            bool: True if data loaded successfully, False otherwise.
        """
        try:
            if self.data_file_path.exists():
                with open(self.data_file_path, "r", encoding="utf-8") as f:
                    self.manual_data = json.load(f)
                print(
                    f"✓ Loaded library guide: {self.manual_data.get('title', 'Unknown')}")
                return True
            else:
                print(f"✗ Data file not found: {self.data_file_path}")
                return False
        except Exception as e:
            print(f"✗ Failed to load data: {e}")
            return False

    def get_manual_title(self) -> Dict[str, Any]:
        """Get the title of the library guide.

        Returns:
            Dict[str, Any]: Dictionary containing the manual title.
        """
        return {"title": self.manual_data.get("title", "")}

    def list_manual_sections(self) -> Dict[str, Any]:
        """List all first-level sections of the library guide.

        Returns:
            Dict[str, Any]: Dictionary containing sections list with metadata.
        """
        sections = []
        for section in self.manual_data.get("sections", []):
            sections.append({
                "heading": section["heading"],
                "level": section["level"],
                "subsections_count": len(section["subsections"]),
                "has_direct_content": len(section["content"]) > 0
            })

        return {
            "total_sections": len(sections),
            "sections": sections
        }

    def get_manual_section(self, heading: str) -> Dict[str, Any]:
        """Get specific section content by heading.

        Args:
            heading (str): Section heading (first-level).

        Returns:
            Dict[str, Any]: Complete section content including subsections.
        """
        for section in self.manual_data.get("sections", []):
            if section["heading"] == heading:
                return {"section": section}

        return {"error": f"找不到章節：{heading}"}

    def search_manual(self, keyword: str) -> Dict[str, Any]:
        """Search for content containing the keyword in the library guide.

        Args:
            keyword (str): Search keyword.

        Returns:
            Dict[str, Any]: Search results with section locations and content.
        """
        results = []

        def search_in_item(item: dict, keyword_lower: str) -> bool:
            """Check if item contains the keyword."""
            if item["type"] == "paragraph":
                return keyword_lower in item["text"].lower()
            elif item["type"] == "table":
                for header in item.get("headers", []):
                    if keyword_lower in header.lower():
                        return True
                for row in item.get("data", []):
                    for cell in row:
                        if keyword_lower in str(cell).lower():
                            return True
            return False

        keyword_lower = keyword.lower()

        for section in self.manual_data.get("sections", []):
            for item in section.get("content", []):
                if search_in_item(item, keyword_lower):
                    results.append({
                        "section": section["heading"],
                        "level": 1,
                        "content_type": item["type"],
                        "content": item
                    })

            for subsection in section.get("subsections", []):
                for item in subsection.get("content", []):
                    if search_in_item(item, keyword_lower):
                        results.append({
                            "section": section["heading"],
                            "subsection": subsection["heading"],
                            "level": 2,
                            "content_type": item["type"],
                            "content": item
                        })

        return {
            "keyword": keyword,
            "total_results": len(results),
            "results": results
        }

    def get_manual_tables(self) -> Dict[str, Any]:
        """Get all tables in the library guide.

        Returns:
            Dict[str, Any]: All tables with their locations and content.
        """
        tables = []

        for section in self.manual_data.get("sections", []):
            for item in section.get("content", []):
                if item["type"] == "table":
                    tables.append({
                        "section": section["heading"],
                        "table": item
                    })

            for subsection in section.get("subsections", []):
                for item in subsection.get("content", []):
                    if item["type"] == "table":
                        tables.append({
                            "section": section["heading"],
                            "subsection": subsection["heading"],
                            "table": item
                        })

        return {
            "total_tables": len(tables),
            "tables": tables
        }

    def get_guide_stats(self) -> Dict[str, Any]:
        """Get statistics of the library guide.

        Returns:
            Dict[str, Any]: Dictionary containing guide statistics.
        """
        metadata = self.manual_data.get("metadata", {})
        sections = self.manual_data.get("sections", [])

        subsections_count = sum(len(s["subsections"]) for s in sections)

        return {
            "title": self.manual_data.get("title", ""),
            "total_sections": len(sections),
            "total_subsections": subsections_count,
            "total_paragraphs": metadata.get("total_paragraphs", 0),
            "total_tables": metadata.get("total_tables", 0)
        }


manager = LibraryGuideManager()
mcp = FastMCP("nchu_library_guide")


@mcp.tool()
def library_guide_get_title() -> str:
    """Get the title of the library guide."""
    try:
        result = manager.get_manual_title()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_guide_list_sections() -> str:
    """List all first-level sections of the library guide."""
    try:
        result = manager.list_manual_sections()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_guide_get_section(heading: str) -> str:
    """
    Get specific section content by heading.

    Args:
        heading: Section heading (first-level), e.g., "借閱服務SO sweet"
    """
    try:
        result = manager.get_manual_section(heading)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_guide_search(keyword: str) -> str:
    """
    Search for content containing the keyword in the library guide.

    Args:
        keyword: Search keyword
    """
    try:
        result = manager.search_manual(keyword)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_guide_get_tables() -> str:
    """Get all tables in the library guide."""
    try:
        result = manager.get_manual_tables()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


@mcp.tool()
def library_guide_stats() -> str:
    """Get statistics of the library guide."""
    try:
        result = manager.get_guide_stats()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
