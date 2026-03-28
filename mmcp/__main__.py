"""
Context-Life (CL) — LLM Context Optimization MCP Server

Entry point with subcommands:
    context-life              → start MCP server (stdio)
    context-life serve        → start MCP server (stdio)
    context-life serve --http → start MCP server (HTTP)
    context-life info         → show system info
    context-life upgrade      → self-update from GitHub
    context-life version      → show version
    context-life help         → show help
    python -m mmcp            → from source (same behavior)
"""

import sys


def main():
    args = sys.argv[1:]

    # No args → default MCP server (stdio)
    if not args or (len(args) == 1 and args[0] == "serve"):
        from mmcp.server import mcp
        mcp.run(transport="stdio")
        return

    command = args[0].lower()

    if command == "serve" and "--http" in args:
        from mmcp.server import mcp
        from mmcp.cli import print_banner, CONSOLE
        print_banner()
        CONSOLE.print("  [bold green]▶[/] Starting HTTP server...\n")
        mcp.run(transport="streamable-http")

    elif command == "info":
        from mmcp.cli import show_info
        show_info()

    elif command == "upgrade":
        from mmcp.cli import do_upgrade
        do_upgrade()

    elif command == "version" or command == "--version" or command == "-v":
        from mmcp.cli import show_version
        show_version()

    elif command == "help" or command == "--help" or command == "-h":
        from mmcp.cli import show_help
        show_help()

    elif command == "--transport":
        # Legacy support: context-life --transport http
        from mmcp.server import mcp
        transport = args[1] if len(args) > 1 else "stdio"
        if transport == "http":
            from mmcp.cli import print_banner, CONSOLE
            print_banner()
            CONSOLE.print("  [bold green]▶[/] Starting HTTP server...\n")
            mcp.run(transport="streamable-http")
        else:
            mcp.run(transport="stdio")

    else:
        from mmcp.cli import show_help, CONSOLE
        CONSOLE.print(f"\n  [bold red]✗ Unknown command:[/] {command}\n")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
