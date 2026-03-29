import os
import re
import time
import urllib.parse
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
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


@mcp.tool()
def library_get_loan_history(user_id: str) -> List[Dict]:
    """Get a user's Alma loan history.

    Args:
        user_id (str): User identifier in the library system,  The `user_id` field is automatically provided by the backend.

    Returns:
        List[Dict]: Loan records with fields:
            Index, User Name, Department, User Group, User ID,
            Author, Barcode, Loan Date, Return Date, Title, email
    """
    base_url = "https://api-ap.hosted.exlibrisgroup.com/almaws/v1/analytics/reports"
    report_path = "/shared/National Chung Hsing University 886NCHU_INST/Reports/API/Patron_Loan_History_Records"
    report_path_encoded = urllib.parse.quote(report_path)

    api_key = os.getenv("ALMA_ANALYTICS_API_KEY")
    if not api_key:
        key_file = Path(__file__).with_name(".alma_analytics_api_key")
        if key_file.exists():
            api_key = key_file.read_text().strip()
    if not api_key:
        raise RuntimeError(
            "ALMA_ANALYTICS_API_KEY environment variable not set and .alma_analytics_api_key file missing"
        )

    filter_xml = f"""
<sawx:expr xsi:type="sawx:comparison" op="equal"
    xmlns:saw="com.siebel.analytics.web/report/v1.1"
    xmlns:sawx="com.siebel.analytics.web/expression/v1.1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <sawx:expr xsi:type="sawx:sqlExpression">"Borrower Details"."User Primary Identifier"</sawx:expr>
    <sawx:expr xsi:type="xsd:string">{user_id}</sawx:expr>
</sawx:expr>
"""
    encoded_filter = urllib.parse.quote(filter_xml)
    headers = {"Accept": "application/json"}

    records: List[Dict] = []
    resumption_token = None

    while True:
        if resumption_token:
            url = f"{base_url}?apikey={api_key}&resumptionToken={resumption_token}"
        else:
            url = f"{base_url}?path={report_path_encoded}&apikey={api_key}&limit=100&col_names=true&filter={encoded_filter}"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"API request failed: {response.status_code} - {response.text}")

        data = response.json()
        xml_str = data.get("anies", [None])[0]
        if not xml_str:
            break

        root = ET.fromstring(xml_str)
        ns = {"ns": "urn:schemas-microsoft-com:xml-analysis:rowset"}

        field_names = [
            "Index", "User Name", "Department", "User Group", "User ID",
            "Author", "Barcode", "Loan Date", "Return Date", "Title", "email",
        ]

        for row in root.find(".//ns:rowset", ns).findall("ns:Row", ns):
            record = {}
            for i, field in enumerate(field_names):
                value = row.find(f"ns:Column{i}", ns)
                record[field] = value.text if value is not None else None
            records.append(record)

        token_el = root.find(".//ResumptionToken")
        is_finished_el = root.find(".//IsFinished")
        if is_finished_el is not None and is_finished_el.text == "true":
            break

        if token_el is not None and token_el.text:
            resumption_token = token_el.text
        else:
            break

    return records


if __name__ == "__main__":
    mcp.run(transport="stdio")