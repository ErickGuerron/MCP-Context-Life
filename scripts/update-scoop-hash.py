"""Update Scoop manifest with the real exe hash after build."""

import re
import sys
from pathlib import Path


def update_scoop_manifest(exe_hash: str, version: str) -> None:
    manifest = Path("bucket/context-life.json")
    content = manifest.read_text(encoding="utf-8")

    content = re.sub(
        r'"hash":\s*"[0-9a-fA-F]{64}"',
        f'"hash": "{exe_hash}"',
        content,
    )

    manifest.write_text(content, encoding="utf-8")
    print(f"Updated bucket with hash for v{version}")
    print(f"Hash: {exe_hash}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <exe_hash> <version>")
        sys.exit(1)
    update_scoop_manifest(sys.argv[1], sys.argv[2])
