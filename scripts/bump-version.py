#!/usr/bin/env python3
"""
bump-version.py — Synchronize version across all version files in the project.

Single source of truth: pyproject.toml (version field)
Files updated automatically:
  - mmcp/__init__.py        → __version__
  - bucket/context-life.json → scoop manifest version + URLs
  - README.md               → version badge + example commands

Usage:
    python scripts/bump-version.py [version]
    python scripts/bump-version.py 0.8.0        # set specific version
    python scripts/bump-version.py              # read from pyproject.toml
    python scripts/bump-version.py --check      # verify all files in sync
    python scripts/bump-version.py --dry-run    # show what would change
    python scripts/bump-version.py --tag-msg    # print tag message from latest tag (for CI)

Single-source-of-truth: pyproject.toml is the ONLY file you edit manually.
All other version references are derived from it.
"""

import re
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).parent.parent


def get_version_from_pyproject() -> str:
    """Read version from pyproject.toml (source of truth)."""
    pyproject = ROOT / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        raise SystemExit("ERROR: Could not find version in pyproject.toml")
    return match.group(1)


def set_version_in_pyproject(version: str) -> None:
    """Update version in pyproject.toml."""
    pyproject = ROOT / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^version\s*=\s*["\'][^"\']+["\']',
        f'version = "{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    pyproject.write_text(new_content, encoding="utf-8")
    print(f"  [OK] pyproject.toml -> {version}")


def update_mmcp_init(version: str) -> None:
    """Update __version__ in mmcp/__init__.py."""
    init_file = ROOT / "mmcp" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^(__version__\s*=\s*)["\'][^"\']+["\']',
        f'\\1"{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    init_file.write_text(new_content, encoding="utf-8")
    print(f"  [OK] mmcp/__init__.py -> {version}")


def update_scoop_manifest(version: str) -> None:
    """Update version in bucket/context-life.json (Scoop manifest)."""
    manifest = ROOT / "bucket" / "context-life.json"
    if not manifest.exists():
        print("[SKIP] bucket/context-life.json not found — skipping")
        return

    content = manifest.read_text(encoding="utf-8")

    # Update version field
    content = re.sub(
        r'"version":\s*"[^"]+"',
        f'"version": "{version}"',
        content,
        count=1,
    )

    # Update URLs (replace version in URL paths for .exe release artifact)
    static_content, autoupdate_marker, autoupdate_content = content.partition('"autoupdate": {')
    static_content = re.sub(
        r"https://github\.com/[^/]+/[^/]+/releases/download/v[^/]+/context-life\.exe",
        f"https://github.com/ErickGuerron/MCP-Context-Life/releases/download/v{version}/context-life.exe",
        static_content,
    )
    autoupdate_content = re.sub(
        r"https://github\.com/[^/]+/[^/]+/releases/download/v[^/]+/context-life\.exe",
        "https://github.com/ErickGuerron/MCP-Context-Life/releases/download/v$version/context-life.exe",
        autoupdate_content,
    )
    content = static_content + autoupdate_marker + autoupdate_content

    manifest.write_text(content, encoding="utf-8")
    print(f"  [OK] bucket/context-life.json -> {version}")


def update_readme(version: str) -> None:
    """Update version badge and example commands in README.md."""
    readme = ROOT / "README.md"
    if not readme.exists():
        print("[SKIP] README.md not found — skipping")
        return

    content = readme.read_text(encoding="utf-8")

    # Update version badge
    content = re.sub(
        r"img\.shields\.io/badge/version-[0-9]+\.[0-9]+\.[0-9]+-[a-z]+",
        f"img.shields.io/badge/version-{version}-blue",
        content,
        count=1,
    )

    # Update example commands (context-life upgrade --version vX.Y.Z)
    content = re.sub(
        r"context-life upgrade --version v[0-9]+\.[0-9]+\.[0-9]+",
        f"context-life upgrade --version v{version}",
        content,
    )

    readme.write_text(content, encoding="utf-8")
    print(f"  [OK] README.md -> {version}")


def check_versions() -> bool:
    """Verify all files are in sync with pyproject.toml."""
    expected = get_version_from_pyproject()
    files = {
        "pyproject.toml": (ROOT / "pyproject.toml", r'version\s*=\s*["\']([^"\']+)["\']'),
        "mmcp/__init__.py": (ROOT / "mmcp" / "__init__.py", r'__version__\s*=\s*["\']([^"\']+)["\']'),
        "bucket/context-life.json": (
            ROOT / "bucket" / "context-life.json",
            r'"version":\s*"([^"]+)"',
        ),
        "README.md badge": (
            ROOT / "README.md",
            r"badge/version-([0-9]+\.[0-9]+\.[0-9]+)-",
        ),
    }

    all_ok = True
    print(f"\n[*] Checking version sync (expected: {expected})\n")
    for name, (path, pattern) in files.items():
        if not path.exists():
            print(f"  [OK] {name}: file not found")
            all_ok = False
            continue

        content = path.read_text(encoding="utf-8")
        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            print(f"  [MISMATCH] {name}: pattern not found")
            all_ok = False
            continue

        found = match.group(1) if len(match.groups()) > 0 else match.group(0)
        status = "[OK]" if found == expected else "[MISMATCH]"
        print(f"  {status} {name}: {found}")
        if found != expected:
            all_ok = False

    manifest = ROOT / "bucket" / "context-life.json"
    if manifest.exists():
        content = manifest.read_text(encoding="utf-8")
        static_content, _, autoupdate_content = content.partition('"autoupdate": {')
        # Check exe URL and hash (the primary release artifact)
        exe_url_match = re.search(
            r"\"url\":\s*\"https://github\.com/[^/]+/[^/]+/releases/download/v([0-9.]+)/context-life\.exe\"",
            static_content,
        )
        if exe_url_match:
            status = "[OK]" if exe_url_match.group(1) == expected else "[MISMATCH]"
            print(f"  {status} bucket/context-life.json exe URL: v{exe_url_match.group(1)}")
            if exe_url_match.group(1) != expected:
                all_ok = False
        else:
            print("  [MISMATCH] bucket/context-life.json exe URL: pattern not found")
            all_ok = False

        hashes = re.findall(r'"hash":\s*"([0-9a-fA-F]{64})"', static_content)
        if hashes:
            zero_hash = "0" * 64
            for index, hash_value in enumerate(hashes, start=1):
                status = "[OK]" if hash_value.lower() != zero_hash else "[MISMATCH]"
                print(f"  {status} bucket/context-life.json hash #{index}: {hash_value.lower()}")
                if hash_value.lower() == zero_hash:
                    all_ok = False

        autoupdate_urls = re.findall(
            r"https://github\.com/[^/]+/[^/]+/releases/download/v\$version/context-life\.exe",
            autoupdate_content,
        )
        if len(autoupdate_urls) != 2:
            print("  [MISMATCH] bucket/context-life.json autoupdate URLs must keep $version placeholders")
            all_ok = False

    return all_ok


def get_tag_annotation(tag: str) -> str:
    """Get annotation message from a git tag."""

    def read_tag_contents(ref: str) -> str:
        result = subprocess.run(
            [
                "git",
                "tag",
                "--list",
                ref,
                "--format=%(contents:subject)%0a%(contents:body)",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return ""

    try:
        exact = read_tag_contents(tag)
        if exact:
            return exact

        latest = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if latest.returncode == 0:
            fallback_tag = latest.stdout.strip()
            if fallback_tag and fallback_tag != tag:
                fallback = read_tag_contents(fallback_tag)
                if fallback:
                    return fallback
    except Exception:
        pass
    return ""


def main() -> None:
    parser = ArgumentParser(description="Bump version across all project files")
    parser.add_argument(
        "version",
        nargs="?",
        help="Version to set (e.g. 0.8.0). If omitted, reads from pyproject.toml.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify all files are in sync without making changes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files.",
    )
    parser.add_argument(
        "--tag-msg",
        metavar="TAG",
        help="Print tag annotation and exit. Use in CI to get tag message.",
    )
    parser.add_argument(
        "--save-tag-msg",
        metavar="FILE",
        help="Save tag annotation to a file (for PR passing).",
    )
    args = parser.parse_args()

    # --check mode: just verify
    if args.check:
        ok = check_versions()
        sys.exit(0 if ok else 1)

    # --tag-msg mode: print tag annotation and exit
    if args.tag_msg:
        msg = get_tag_annotation(args.tag_msg)
        print(msg)
        sys.exit(0)

    # Determine version
    version = args.version.lstrip("v") if args.version else get_version_from_pyproject()

    print(f"\n[*] Bumping version to: {version}\n")

    if args.dry_run:
        print("  (dry-run: no changes made)\n")
        sys.exit(0)

    # Update all files
    set_version_in_pyproject(version)
    update_mmcp_init(version)
    update_scoop_manifest(version)
    update_readme(version)

    print(f"\n[OK] Version bumped to {version}\n")

    # Save tag message to file if requested
    if args.save_tag_msg:
        tag = f"v{version}"
        msg = get_tag_annotation(tag)
        Path(args.save_tag_msg).write_text(msg, encoding="utf-8")
        print(f"  [OK] Tag message saved to {args.save_tag_msg}")

    # Verify
    ok = check_versions()
    if not ok:
        print("\n[FAIL] WARNING: Files are out of sync after bump!")
        sys.exit(1)


if __name__ == "__main__":
    main()
