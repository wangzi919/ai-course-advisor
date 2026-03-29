#!/usr/bin/env python3
"""執行院學士介紹頁面爬蟲（跨領域學習資訊網）"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.cibp_intro_scraper import CibpIntroScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def main():
    scraper = CibpIntroScraper()

    if "--force" in sys.argv:
        result = scraper.force_update()
    else:
        result = scraper.run()

    if result:
        print(f"Updated: {result}")
    else:
        print("Cache is fresh, no update needed. Use --force to force update.")


if __name__ == "__main__":
    main()
