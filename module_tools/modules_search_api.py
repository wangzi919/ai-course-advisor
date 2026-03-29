from pathlib import Path
import json
from typing import Dict
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nchu_course_modules")


def _load_modules_data() -> Dict:
    """Load modules data from JSON file in the parent directory.

    Returns:
        Dict: Dictionary containing module data.
    
    Raises:
        FileNotFoundError: If the JSON file does not exist.
    """
    parent_dir = Path(__file__).parent.parent
    json_file = parent_dir / "data/modules/modules_data.json"

    if not json_file.exists():
        raise FileNotFoundError(f"Modules data file not found: {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


MODULES_DATA = _load_modules_data()


@mcp.tool()
def modules_list_all() -> list[str]:
    """Return the list of available course module names.

    Returns:
        List[str]: Names of all available modules.
    """
    return list(MODULES_DATA.keys())


@mcp.tool()
def modules_get_detail(name: str) -> Dict:
    """Return detailed information for a specific module.

    Args:
        name (str): Module name.

    Returns:
        Dict: Module details, or None if not found.
    """
    return MODULES_DATA.get(name)


RULES_TEXT = """國立中興大學跨領域模組規定：
學生修習領域模組之規定：(一)申請修習程序：擬申請領域模組者應於本校當學期註冊日起二週內填具修習領域模
組申請表，經領域模組召集人簽章同意後送註冊組核備。(二)課程認定及學分採計：1、併採事前申請或事後認可制，學生於修業期間內，所修領域模組之課程均得納入
領域模組資格認定。惟學生不得以修習領域模組為由，申請延長修業年限。2、不同領域模組中相同名稱課程或經開設教學單位核定之等同課程，可同時認列為
不同領域模組要求；惟畢業學分只採計一次。(三)證明書核發程序：凡修滿領域模組規定之科目與學分者，應填具領域模組證明書申請表及備齊成績證明，於離校時經領域模組召集人及註冊組查核無誤後，始得核發領域模組證明書。
"""


@mcp.tool()
def modules_get_rules() -> str:
    """Return the rules and regulations for course modules at NCHU.

    Returns:
        str: The course module rules text.
    """
    return RULES_TEXT


if __name__ == "__main__":
    mcp.run(transport="stdio")