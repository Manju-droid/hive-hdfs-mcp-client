"""Live tests against the configured Hive MCP server."""

import asyncio

import pytest

from clients.mcp_client import SQLSafetyError, get_mcp_tools
from config.settings import Settings

pytestmark = pytest.mark.integration


def test_hive_mcp_discovery_and_banking_queries() -> None:
    async def exercise_server() -> None:
        tools = await get_mcp_tools(Settings.from_env())
        by_name = {tool.name: tool for tool in tools}
        required_tools = {
            "list_databases",
            "list_tables",
            "describe_table",
            "execute_query",
        }
        assert all(
            any(name.endswith(required) for name in by_name)
            for required in required_tools
        )

        def find_tool(suffix: str):
            return next(tool for name, tool in by_name.items() if name.endswith(suffix))

        with pytest.raises(SQLSafetyError):
            await find_tool("execute_query").ainvoke(
                {"sql": "DELETE FROM banking_transactions", "limit": 10}
            )

        databases = await find_tool("list_databases").ainvoke({})
        assert "default" in str(databases)

        tables = await find_tool("list_tables").ainvoke({"database": "default"})
        assert "banking_transactions" in str(tables)

        schema = await find_tool("describe_table").ainvoke(
            {"table": "banking_transactions", "database": "default"}
        )
        assert "transaction_id" in str(schema)
        assert "amount" in str(schema)

        count = await find_tool("execute_query").ainvoke(
            {
                "sql": "SELECT COUNT(*) AS transaction_count "
                "FROM banking_transactions",
                "limit": 1,
            }
        )
        assert "10" in str(count)

        flagged = await find_tool("execute_query").ainvoke(
            {
                "sql": (
                    "SELECT transaction_id, amount, status "
                    "FROM banking_transactions "
                    "WHERE country = 'Canada' AND status = 'FLAGGED' "
                    "ORDER BY transaction_id"
                ),
                "limit": 10,
            }
        )
        assert "TXN002" in str(flagged)
        assert "TXN005" in str(flagged)
        assert "TXN008" not in str(flagged)

        rows = await find_tool("execute_query").ainvoke(
            {
                "sql": (
                    "SELECT transaction_id, amount, status "
                    "FROM banking_transactions "
                    "WHERE country = 'Canada' ORDER BY transaction_id"
                ),
                "limit": 10,
            }
        )
        assert "TXN002" in str(rows)
        assert "TXN005" in str(rows)
        assert "TXN008" in str(rows)

        country_totals = await find_tool("execute_query").ainvoke(
            {
                "sql": (
                    "SELECT country, SUM(amount) AS total_amount "
                    "FROM banking_transactions GROUP BY country ORDER BY country"
                ),
                "limit": 100,
            }
        )
        assert "Canada" in str(country_totals)
        assert "total_amount" in str(country_totals)

    asyncio.run(exercise_server())
