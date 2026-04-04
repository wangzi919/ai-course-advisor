import re
import time
import urllib.parse
import requests
from typing import List, Dict
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nchu_library")


@mcp.tool()
def library_search_books(query: str) -> List[Dict]:
    """Search books from NCHU Library using the Primo API.

    Args:
        query (str): The search keyword (supports Chinese characters).

    Returns:
        List[Dict]: Each dictionary contains:
            - 'title': Book title
            - 'creator': Main author or contributor (cleaned)
            - 'link': Alma detail page link
            - 'error': Optional, if request fails
    """
    total_count: int = 10
    page_size: int = 10
    base_url = "https://nchu.primo.exlibrisgroup.com/primaws/rest/pub/pnxs"
    encoded_query = urllib.parse.quote(query)
    results: List[Dict] = []

    for offset in range(0, total_count, page_size):
        url = (
            f"{base_url}?acTriggered=false&blendFacetsSeparately=false"
            f"&came_from=pagination_1_2&citationTrailFilterByAvailability=true"
            f"&disableCache=false&getMore=0&inst=886NCHU_INST&isCDSearch=false"
            f"&lang=zh-tw&limit={page_size}&newspapersActive=false&newspapersSearch=false"
            f"&offset={offset}&otbRanking=false&pcAvailability=false"
            f"&q=any,contains,{encoded_query}&qExclude=&qInclude="
            f"&rapido=false&refEntryActive=false&rtaLinks=true"
            f"&scope=MyInst_and_CI&searchInFulltextUserSelection=false"
            f"&skipDelivery=Y&sort=rank&tab=Everything&vid=886NCHU_INST:886NCHU_INST"
        )

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            for doc in data.get("docs", []):
                display = doc.get("pnx", {}).get("display", {})
                links = doc.get("pnx", {}).get("links", {})

                title = display.get("title", [""])[0]
                creator_list = display.get("creator") or display.get("contributor", [""])
                creator = creator_list[0] if creator_list else ""
                creator_clean = re.sub(r"\$\$Q.*", "", creator).strip()

                record_id = doc.get("pnx", {}).get("control", {}).get("recordid", [""])[0]
                alma_link = f"https://nchu.primo.exlibrisgroup.com/discovery/fulldisplay?docid={record_id}&context=PC&vid=886NCHU_INST:886NCHU_INST&lang=zh-tw"

                if not record_id and links.get("linktorsrc"):
                    for link_data in links.get("linktorsrc", []):
                        match = re.search(r"\$\$U(.*?)\$\$", link_data)
                        if match:
                            alma_link = match.group(1)
                            break

                results.append({
                    "title": title.strip(),
                    "creator": creator_clean,
                    "link": alma_link
                })

            time.sleep(1)

        except Exception as e:
            results.append({"error": str(e), "offset": offset})

    return results


if __name__ == "__main__":
    mcp.run(transport="stdio")