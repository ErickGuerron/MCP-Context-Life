"""Update Scoop manifest with the real exe hash after build."""

import re
import sys
from pathlib import Path


def update_scoop_manifest(exe_hash: str, version: str, repo: str = "ErickGuerron/MCP-Context-Life") -> None:
    manifest = Path("bucket/context-life.json")
    content = manifest.read_text(encoding="utf-8")

    # Update version at root level
    content = re.sub(
        r'"version":\s*"[^"]*"',
        f'"version": "{version}"',
        content,
    )

    # Update url at root level
    old_url_pattern = re.compile(r'"url":\s*"https://github\.com/[^/]+/[^/]+/releases/download/[^/]+/[^"]*"')
    new_url = f'"url": "https://github.com/{repo}/releases/download/v{version}/context-life.exe"'
    content = old_url_pattern.sub(new_url, content)

    # Update hash at root level
    content = re.sub(
        r'"hash":\s*"[^"]*"',
        f'"hash": "{exe_hash}"',
        content,
    )

    # Update architecture amd64 hash - find the amd64 block and replace its hash
    amd64_pattern = re.compile(r'("amd64":\s*\{[^}]+?"hash":\s*)"[^"]*"')
    content = amd64_pattern.sub(rf'\1"{exe_hash}"', content)

    # Update architecture arm64 hash
    arm64_pattern = re.compile(r'("arm64":\s*\{[^}]+?"hash":\s*)"[^"]*"')
    content = arm64_pattern.sub(rf'\1"{exe_hash}"', content)

    manifest.write_text(content, encoding="utf-8")
    print(f"Updated bucket with hash for v{version}")
    print(f"Hash: {exe_hash}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <exe_hash> <version>")
        sys.exit(1)
    update_scoop_manifest(sys.argv[1], sys.argv[2])
