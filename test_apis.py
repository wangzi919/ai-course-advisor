import json
import sys
import importlib
import traceback
from unittest.mock import MagicMock

sys.path.append('.')

# Mock MCP
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.server'] = MagicMock()
sys.modules['mcp.server.fastmcp'] = MagicMock()

with open('tool_metadata/tool_registry.json', 'r', encoding='utf-8') as f:
    registry = json.load(f)

modules_to_test = set(info['module'] for info in registry.values())

success = []
failed = []

for mod_path in modules_to_test:
    mod_name = mod_path.replace('.py', '').replace('/', '.')
    try:
        importlib.import_module(mod_name)
        success.append(mod_path)
    except Exception as e:
        failed.append((mod_path, str(e)))

print(f"Total modules: {len(modules_to_test)}")
print(f"Success: {len(success)}")
if failed:
    print("Failed modules:")
    for m, err in failed:
        print(f" - {m}: {err}")
else:
    print("All imported successfully.")
