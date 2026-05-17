"""Print the version from pyproject.toml for CI scripts."""
from pathlib import Path
import re
import sys

content = Path("pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
if not match:
    sys.exit(1)
print(match.group(1))