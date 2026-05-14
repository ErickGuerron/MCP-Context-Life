"""
Session ID Resolver Module - Context-Life (CL)

RFC-002 P5: Server-side session ID derivation.

Session ID derivation:
- IF ENGRAM_SESSION_ID env var → use directly
- ELSE IF .context-session.id exists AND < 12h old → read from file
- ELSE → compute hash(cwd + timestamp), save to .context-session.id, use it

TTL is 12 hours (43200 seconds).
DISABLE_AUTOINVOKE=1 → returns None (no-op).
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

# TTL: 12 hours in seconds
_SESSION_TTL_SECONDS = 12 * 60 * 60  # 43200


def resolve(cwd: str | None = None) -> str | None:
    """
    Resolve the session ID using server-side derivation.

    Args:
        cwd: Working directory. Defaults to os.getcwd().

    Returns:
        Session ID string, or None if DISABLE_AUTOINVOKE=1.

    Raises:
        OSError: If file operations fail unexpectedly.
    """
    # Bypass: DISABLE_AUTOINVOKE=1
    if os.environ.get("DISABLE_AUTOINVOKE") == "1":
        return None

    workspace = Path(cwd) if cwd else Path.cwd()

    # Path 1: ENGRAM_SESSION_ID env var
    env_session_id = os.environ.get("ENGRAM_SESSION_ID")
    if env_session_id:
        return env_session_id

    # Path 2: .context-session.id exists and fresh
    session_file = workspace / ".context-session.id"
    if session_file.is_file():
        file_age = time.time() - session_file.stat().st_mtime
        if file_age < _SESSION_TTL_SECONDS:
            return session_file.read_text(encoding="utf-8").strip()

    # Path 3: compute new hash, save to file
    timestamp = time.time()
    hash_input = f"{workspace}:{timestamp}"
    session_id = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    session_file.write_text(session_id, encoding="utf-8")
    return session_id
