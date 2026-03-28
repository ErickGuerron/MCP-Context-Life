import os
from pathlib import Path

import pytest

from mmcp.config import get_config, reset_config


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path):
    """
    Ensure every test uses a temporary config/data directory
    so that we don't pollute the real production session.db or LanceDB.
    """
    reset_config()
    cfg = get_config()
    
    # Isolate data directory
    cfg.data_dir = str(tmp_path / "cl_data")
    cfg.cache_db_path = str(tmp_path / "cl_data" / "session.db")
    
    yield cfg
    
    reset_config()
