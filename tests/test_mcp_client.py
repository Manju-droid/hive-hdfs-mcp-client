"""Tests for MCP tool-call safeguards and timeouts."""

import asyncio

import pytest
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from mcp.types import CallToolResult, TextContent

from clients.mcp_client import SQLSafetyError, _tool_interceptor
from config.settings import Settings


def make_settings(
    *,
    max_result_rows: int = 50,
    mcp_timeout_seconds: int = 1,
) -> Settings:
    return Settings(
        hive_mcp_command="/path/to/hive-server",
        spark_host="localhost",
        spark_port=10000,
        spark_database="default",
        spark_auth="NONE",
        groq_api_key=None,
        groq_model="llama-3.3-70b-versatile",
        max_result_rows=max_result_rows,
        mcp_timeout_seconds=mcp_timeout_seconds,
        agent_timeout_seconds=120,
    )


def test_interceptor_bounds_hive_query_before_call() -> None:
    async def exercise() -> None:
        settings = make_settings()
        request = MCPToolCallRequest(
            name="execute_query",
            args={
                "sql": "SELECT * FROM banking_transactions LIMIT 1000",
                "limit": 1000,
            },
            server_name="hive",
        )
        captured_request = None

        async def handler(call: MCPToolCallRequest) -> CallToolResult:
            nonlocal captured_request
            captured_request = call
            return CallToolResult(
                content=[TextContent(type="text", text="query complete")],
            )

        await _tool_interceptor(settings)(request, handler)
        assert captured_request is not None
        assert captured_request.args["sql"].endswith("LIMIT 50")
        assert captured_request.args["limit"] == 50

    asyncio.run(exercise())


def test_interceptor_rejects_modification_before_call() -> None:
    async def exercise() -> None:
        request = MCPToolCallRequest(
            name="execute_query",
            args={"sql": "DELETE FROM banking_transactions"},
            server_name="hive",
        )

        async def handler(_: MCPToolCallRequest) -> CallToolResult:
            pytest.fail("Unsafe SQL must not reach the MCP server.")

        with pytest.raises(SQLSafetyError):
            await _tool_interceptor(make_settings())(request, handler)

    asyncio.run(exercise())


def test_interceptor_rejects_unknown_hive_tools() -> None:
    async def exercise() -> None:
        request = MCPToolCallRequest(
            name="drop_table",
            args={},
            server_name="hive",
        )

        async def handler(_: MCPToolCallRequest) -> CallToolResult:
            pytest.fail("Unknown Hive tools must not reach the MCP server.")

        with pytest.raises(SQLSafetyError, match="Hive tool is not allowed"):
            await _tool_interceptor(make_settings())(request, handler)

    asyncio.run(exercise())


def test_interceptor_raises_server_error_content() -> None:
    async def exercise() -> None:
        request = MCPToolCallRequest(
            name="execute_query",
            args={"sql": "SELECT * FROM banking_transactions"},
            server_name="hive",
        )

        async def handler(_: MCPToolCallRequest) -> CallToolResult:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: query failed")],
            )

        with pytest.raises(RuntimeError, match="Hive MCP tool failed"):
            await _tool_interceptor(make_settings())(request, handler)

    asyncio.run(exercise())


def test_interceptor_times_out_tool_call() -> None:
    async def exercise() -> None:
        request = MCPToolCallRequest(
            name="list_tables",
            args={},
            server_name="hive",
        )

        async def handler(_: MCPToolCallRequest) -> CallToolResult:
            await asyncio.sleep(2)
            return CallToolResult(content=[])

        with pytest.raises(TimeoutError):
            await _tool_interceptor(make_settings())(request, handler)

    asyncio.run(exercise())
