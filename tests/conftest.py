from pathlib import Path

import pytest

from mmcp.infrastructure.environment.config import get_config, reset_config, reset_telemetry_service
from mmcp.infrastructure.environment.orchestrator_detector import reset_detection, reset_tool_pattern_tracker


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path):
    """
    Ensure every test uses a temporary config/data directory
    so that we don't pollute the real production session.db or LanceDB.
    Also reset detection cache for clean test isolation.
    """
    reset_config()
    reset_telemetry_service()
    reset_detection()
    reset_tool_pattern_tracker()
    cfg = get_config()

    # Isolate data directory
    cfg.data_dir = str(tmp_path / "cl_data")
    cfg.cache_db_path = str(tmp_path / "cl_data" / "session.db")

    yield cfg

    reset_config()
