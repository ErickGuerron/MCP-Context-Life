"""
Context-Life (CL) — LLM Context Optimization MCP Server

Entry point for running the server:
    context-life                    (stdio, for MCP clients)
    context-life --transport http   (HTTP, for development)
    python -m mmcp                  (from source)
"""

import sys

from mmcp.server import mcp


def main():
    transport = "stdio"

    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    if transport == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
