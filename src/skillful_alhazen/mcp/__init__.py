"""
MCP (Model Context Protocol) server package for Alhazen.

This package provides TypeDB-backed knowledge graph operations
accessible to Claude and other LLM agents via MCP.

Install with: pip install skillful-alhazen[mcp]
Or for TypeDB only: pip install skillful-alhazen[typedb]
"""

try:
    from .typedb_client import TypeDBClient

    __all__ = ["TypeDBClient"]
except ImportError:
    # typedb-driver not installed
    TypeDBClient = None
    __all__ = []
