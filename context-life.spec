# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all_submodules, collect_submodules, collect_data_files

# -----------------------------------------------------------------------
# Hidden imports — modules that PyInstaller cannot detect automatically
# -----------------------------------------------------------------------

hidden_imports = [
    # Core dependencies that have dynamic imports or C extensions
    "tiktoken",
    "tiktoken.core",
    "tiktoken.registry",
    "tiktoken.core_encodings",

    # LanceDB and its native dependencies
    "lancedb",
    "lancedb.table",
    "lancedb.embeddings",
    "lancedb.query",
    "pyarrow",
    "pyarrow.core",
    "pyarrow._compute",
    "pyarrow._fs",

    # Sentence-transformers
    "sentence_transformers",
    "sentence_transformers.models",
    "sentence_transformers.model_card",
    "transformers",
    "transformers.modeling_utils",
    "transformers.models",
    "transformers.models.auto",
    "transformers.models.auto.configuration_auto",
    "transformers.models.auto.modeling_auto",
    "tokenizers",
    "tokenizers.implementations",

    # Rich CLI library
    "rich",
    "rich.console",
    "rich.table",
    "rich.progress",
    "rich.panel",
    "rich.text",
    "rich.syntax",
    "rich.theme",

    # MCP server
    "mcp",
    "mcp.server",
    "mcp.types",
    "mcp.protocol",
    "mcp.transport",

    # Psutil
    "psutil",

    # Core mmcp modules that might be lazily imported
    "mmcp",
    "mmcp.__init__",
    "mmcp.presentation",
    "mmcp.presentation.mcp",
    "mmcp.presentation.cli",
    "mmcp.application",
    "mmcp.application.ports",
    "mmcp.application.features",
    "mmcp.infrastructure",
    "mmcp.infrastructure.environment",
    "mmcp.infrastructure.persistence",
    "mmcp.infrastructure.tokens",
    "mmcp.infrastructure.knowledge",
    "mmcp.infrastructure.context",
    "mmcp.infrastructure.telemetry",
    "mmcp.domain",
    "mmcp.orchestration",
]

# -----------------------------------------------------------------------
# Collect all submodules for packages with complex hierarchies
# -----------------------------------------------------------------------

hidden_imports += collect_submodules("tiktoken")
hidden_imports += collect_submodules("lancedb")
hidden_imports += collect_submodules("pyarrow")
hidden_imports += collect_submodules("sentence_transformers")
hidden_imports += collect_submodules("transformers")
hidden_imports += collect_submodules("tokenizers")
hidden_imports += collect_submodules("rich")
hidden_imports += collect_submodules("mcp")

# -----------------------------------------------------------------------
# Data files — non-Python assets needed at runtime
# -----------------------------------------------------------------------

datas = [
    # tiktoken vocabulary files
    ("C:/Users/erick/AppData/Local/Temp/pypoetry/*/site-packages/tiktoken/*.json", "tiktoken"),
]

# -----------------------------------------------------------------------
# Excluded modules — binaries that should NOT be included
# -----------------------------------------------------------------------

excludes = [
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "sklearn",
    "PIL",
    "cv2",
    "torch",
]

# -----------------------------------------------------------------------
# PyInstaller specification
# -----------------------------------------------------------------------

a = Analysis(
    ["mmcp/__main__.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="context-life",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)