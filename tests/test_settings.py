"""Tests for environment-backed MCP configuration."""

from config.settings import Settings


def test_settings_configure_hive_stdio_transport() -> None:
    settings = Settings(
        hive_mcp_command="/opt/hive-server",
        spark_host="localhost",
        spark_port=10000,
        spark_database="default",
        spark_auth="NONE",
        groq_api_key=None,
        groq_model="llama-3.3-70b-versatile",
        max_result_rows=100,
        mcp_timeout_seconds=30,
        agent_timeout_seconds=120,
    )

    config = settings.mcp_servers
    assert set(config) == {"hive"}
    assert config["hive"]["transport"] == "stdio"
    assert config["hive"]["command"] == "/opt/hive-server"
    assert config["hive"]["env"]["SPARK_HOST"] == "localhost"
    assert config["hive"]["env"]["SPARK_PORT"] == "10000"
