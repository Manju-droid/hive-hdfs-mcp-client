"""Suppress informational logs from the spawned MCP server, not its errors."""

import logging

logging.disable(logging.INFO)
