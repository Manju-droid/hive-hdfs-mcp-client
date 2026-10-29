"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_mcp_adapters.sessions import Connection

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    hive_mcp_command: str
    spark_host: str
    spark_port: int
    spark_database: str
    spark_auth: str
    groq_api_key: str | None
    groq_model: str
    max_result_rows: int
    mcp_timeout_seconds: int
    agent_timeout_seconds: int

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        try:
            spark_port = int(os.getenv("SPARK_PORT", "10000"))
            max_result_rows = int(os.getenv("MAX_RESULT_ROWS", "100"))
            mcp_timeout_seconds = int(os.getenv("MCP_TIMEOUT_SECONDS", "30"))
            agent_timeout_seconds = int(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))
        except ValueError as exc:
            raise ValueError(
                "SPARK_PORT, MAX_RESULT_ROWS, MCP_TIMEOUT_SECONDS, and "
                "AGENT_TIMEOUT_SECONDS must be integers."
            ) from exc

        if not 1 <= spark_port <= 65535:
            raise ValueError("SPARK_PORT must be between 1 and 65535.")
        if not 1 <= max_result_rows <= 500:
            raise ValueError("MAX_RESULT_ROWS must be between 1 and 500.")
        if mcp_timeout_seconds < 1:
            raise ValueError("MCP_TIMEOUT_SECONDS must be at least 1.")
        if agent_timeout_seconds < 1:
            raise ValueError("AGENT_TIMEOUT_SECONDS must be at least 1.")

        default_command = (
            Path.home()
            / "Documents"
            / "spark-sql-mcp-server"
            / ".venv"
            / "bin"
            / "spark-sql-mcp-server"
        )
        command = Path(
            os.getenv("HIVE_MCP_COMMAND", str(default_command))
        ).expanduser()

        return cls(
            hive_mcp_command=str(command),
            spark_host=os.getenv("SPARK_HOST", "localhost"),
            spark_port=spark_port,
            spark_database=os.getenv("SPARK_DATABASE", "default"),
            spark_auth=os.getenv("SPARK_AUTH", "NONE"),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            max_result_rows=max_result_rows,
            mcp_timeout_seconds=mcp_timeout_seconds,
            agent_timeout_seconds=agent_timeout_seconds,
        )

    @property
    def mcp_servers(self) -> dict[str, Connection]:
        quiet_logging_path = str(PROJECT_ROOT / "clients" / "mcp_server_logging")
        inherited_pythonpath = os.getenv("PYTHONPATH")
        pythonpath = os.pathsep.join(
            path for path in (quiet_logging_path, inherited_pythonpath) if path
        )
        return {
            "hive": {
                "transport": "stdio",
                "command": self.hive_mcp_command,
                "args": [],
                "env": {
                    "SPARK_HOST": self.spark_host,
                    "SPARK_PORT": str(self.spark_port),
                    "SPARK_DATABASE": self.spark_database,
                    "SPARK_AUTH": self.spark_auth,
                    "PYTHONPATH": pythonpath,
                },
            }
        }
