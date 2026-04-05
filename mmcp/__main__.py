"""
Context-Life (CL) — LLM Context Optimization MCP Server

Entry point with subcommands:
    context-life              → start MCP server (stdio)
    context-life serve        → start MCP server (stdio)
    context-life serve --http → start MCP server (HTTP)
    context-life tui          → open the stateful terminal menu (Config / Metrics)
    context-life info         → show system info + config
    context-life doctor       → run environment diagnostics
    context-life warmup interactive → choose warmup mode interactively
    context-life upgrade      → upgrade to latest GitHub release
    context-life upgrade --version <tag> → install specific version
    context-life upgrade --dry-run      → check without installing
    context-life version      → show version
    context-life help         → show help
    python -m mmcp            → from source (same behavior)
"""

import sys


def main():
    args = sys.argv[1:]

    # No args → default MCP server (stdio)
    if not args or (len(args) == 1 and args[0] == "serve"):
        from mmcp.server import initialize_runtime, mcp

        initialize_runtime()
        mcp.run(transport="stdio")
        return

    command = args[0].lower()

    if command == "serve" and "--http" in args:
        from mmcp.cli import CONSOLE, print_banner
        from mmcp.server import initialize_runtime, mcp

        initialize_runtime()
        print_banner()
        CONSOLE.print("  [bold green]▶[/] Starting HTTP server...\n")
        mcp.run(transport="streamable-http")

    elif command == "info":
        from mmcp.cli import show_info

        show_info()

    elif command == "doctor":
        from mmcp.cli import do_doctor

        do_doctor()

    elif command == "warmup":
        from mmcp.cli import do_rag_warmup_command

        do_rag_warmup_command(args[1:])

    elif command == "prewarm":
        from mmcp.cli import prewarm_rag_now_cli

        prewarm_rag_now_cli()

    elif command == "upgrade":
        from mmcp.cli import do_upgrade

        # Parse upgrade flags
        target_version = None
        dry_run = "--dry-run" in args

        if "--version" in args:
            idx = args.index("--version")
            if idx + 1 < len(args):
                target_version = args[idx + 1]

        do_upgrade(target_version=target_version, dry_run=dry_run)

    elif command in ("version", "--version", "-v"):
        from mmcp.cli import show_version

        show_version()

    elif command in ("help", "--help", "-h"):
        from mmcp.cli import show_help

        show_help()

    elif command == "tui":
        from mmcp.cli import do_tui

        do_tui()

    elif command == "--transport":
        # Legacy support: context-life --transport http
        from mmcp.server import initialize_runtime, mcp

        transport = args[1] if len(args) > 1 else "stdio"
        initialize_runtime()
        if transport == "http":
            from mmcp.cli import CONSOLE, print_banner

            print_banner()
            CONSOLE.print("  [bold green]▶[/] Starting HTTP server...\n")
            mcp.run(transport="streamable-http")
        else:
            mcp.run(transport="stdio")

    else:
        from mmcp.cli import CONSOLE, show_help

        CONSOLE.print(f"\n  [bold red]✗ Unknown command:[/] {command}\n")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
