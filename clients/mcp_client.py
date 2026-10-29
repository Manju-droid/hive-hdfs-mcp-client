"""MCP connections and read-only Hive tool safeguards."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeAlias

import sqlglot
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from langgraph.types import Command
from mcp.types import CallToolResult
from sqlglot import exp
from sqlglot.errors import ParseError

from config.settings import Settings

READ_ONLY_HIVE_TOOLS = frozenset(
    {"list_databases", "list_tables", "describe_table", "execute_query"}
)
MCPResult: TypeAlias = CallToolResult | ToolMessage | Command


class SQLSafetyError(ValueError):
    """Raised when SQL falls outside the supported read-only query subset."""


def validate_and_bound_sql(sql: str, max_rows: int) -> str:
    """Allow one read-only query and cap its top-level result count."""
    if not sql.strip():
        raise SQLSafetyError("SQL query must not be empty.")
    if max_rows < 1:
        raise ValueError("max_rows must be greater than zero.")

    try:
        statements = sqlglot.parse(sql, read="hive")
    except ParseError as exc:
        raise SQLSafetyError(f"SQL could not be parsed safely: {exc}") from exc

    if len(statements) != 1 or statements[0] is None:
        raise SQLSafetyError("Exactly one SQL statement is allowed.")

    statement = statements[0]
    if not isinstance(statement, exp.Query) or statement.find(exp.Select) is None:
        raise SQLSafetyError("Only read-only SELECT queries are allowed.")
    unsafe_nodes = (exp.DML, exp.DDL, exp.Command, exp.Into, exp.Lock)
    if any(isinstance(node, unsafe_nodes) for node in statement.walk()):
        raise SQLSafetyError("SQL modification and command clauses are not allowed.")

    existing_limit = statement.args.get("limit")
    if existing_limit is not None:
        limit_expression = existing_limit.args.get("expression")
        if (
            isinstance(limit_expression, exp.Literal)
            and limit_expression.is_int
            and 0 <= int(limit_expression.this) <= max_rows
        ):
            return statement.sql(dialect="hive")

    statement.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return statement.sql(dialect="hive")


def _cap_execute_query_arguments(
    request: MCPToolCallRequest,
    max_rows: int,
) -> MCPToolCallRequest:
    sql = request.args.get("sql")
    if not isinstance(sql, str):
        raise SQLSafetyError("The execute_query tool requires a SQL string.")

    arguments = {**request.args, "sql": validate_and_bound_sql(sql, max_rows)}
    if "limit" in arguments:
        requested_limit = arguments["limit"]
        if isinstance(requested_limit, bool) or not isinstance(requested_limit, int):
            raise SQLSafetyError("The result limit must be an integer.")
        arguments["limit"] = min(max(requested_limit, 1), max_rows)
    return request.override(args=arguments)


def _raise_for_tool_error(result: MCPResult) -> None:
    if not isinstance(result, CallToolResult):
        return
    for content in result.content:
        text = getattr(content, "text", None)
        if isinstance(text, str) and text.lstrip().lower().startswith("error:"):
            raise RuntimeError(f"Hive MCP tool failed: {text.strip()}")


def _tool_interceptor(
    settings: Settings,
) -> Callable[
    [
        MCPToolCallRequest,
        Callable[[MCPToolCallRequest], Awaitable[MCPResult]],
    ],
    Awaitable[MCPResult],
]:
    async def intercept(
        request: MCPToolCallRequest,
        handler: Callable[[MCPToolCallRequest], Awaitable[MCPResult]],
    ) -> MCPResult:
        if request.server_name == "hive":
            if request.name not in READ_ONLY_HIVE_TOOLS:
                raise SQLSafetyError(f"Hive tool is not allowed: {request.name}")
            if request.name == "execute_query":
                request = _cap_execute_query_arguments(
                    request,
                    settings.max_result_rows,
                )

        result = await asyncio.wait_for(
            handler(request),
            timeout=settings.mcp_timeout_seconds,
        )
        _raise_for_tool_error(result)
        return result

    return intercept


async def get_mcp_tools(settings: Settings) -> list[BaseTool]:
    """Discover tools from configured MCP servers, with bounded calls."""
    client = MultiServerMCPClient(
        settings.mcp_servers,
        tool_interceptors=[_tool_interceptor(settings)],
        handle_tool_errors=False,
    )
    return await asyncio.wait_for(
        client.get_tools(),
        timeout=settings.mcp_timeout_seconds,
    )
