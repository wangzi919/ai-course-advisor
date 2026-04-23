import sys
from pathlib import Path
import json

# Set stdout to utf-8 to avoid encoding errors with emojis
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add current directory to path
PROJECT_ROOT = Path("c:/Users/User/OneDrive/Desktop/course_advisor_main")
sys.path.insert(0, str(PROJECT_ROOT))

from teacher_tools.teacher_search_api import nchu_teacher_get_detail

def test_teacher_get_detail():
    teacher_name = "范耀中"
    print(f"Testing nchu_teacher_get_detail with name: {teacher_name}")
    try:
        result_json = nchu_teacher_get_detail(teacher_name=teacher_name)
        result = json.loads(result_json)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_teacher_get_detail()
