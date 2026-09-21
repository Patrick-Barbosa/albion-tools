"""
Pacote Albion Online Market Intelligence MCP.
"""

try:
    from .server import mcp_server, main
    __all__ = ["mcp_server", "main"]
except ImportError:
    mcp_server = None
    main = None
    __all__ = []
