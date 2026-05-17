"""Minimal entry point for pyinstaller standalone executable.

This module is the single file that pyinstaller packages into context-life.exe.
It forwards all calls to the real mmcp main function via subprocess so that
the actual CLI logic stays in the package without pyinstaller complications.
"""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run the real mmcp module via python -m, forwarding all arguments."""
    result = subprocess.run(
        [sys.executable, "-m", "mmcp", *sys.argv[1:]],
        cwd=Path(sys.executable).parent,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
