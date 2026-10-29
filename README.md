# Hive HDFS MCP Client

A Python 3.12 proof of concept that connects a LangGraph conversational agent to
the existing Hive MCP server over stdio. The current configuration defines a
single `hive` server; the MCP server mapping is intentionally centralized so an
`hdfs` server can be added later without changing the agent interface.
The agent uses the current `langchain.agents.create_agent` API, which runs on
LangGraph.

The client does not install, rebuild, or modify the Hive MCP server, HiveServer2,
Hadoop, or any separate MongoDB project.

## Requirements

- macOS or another platform supported by Python 3.12
- Python 3.12
- The existing Hive MCP server executable
- A running HiveServer2 reachable at the configured host and port
- A Groq API key to run the natural-language agent
- Read-only database permissions for the account used by the Hive MCP server

## Install

From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `GROQ_API_KEY`. Confirm `HIVE_MCP_COMMAND` points to the
existing server executable. The default assumes the server is installed at
`~/Documents/spark-sql-mcp-server`.

The Groq model defaults to `openai/gpt-oss-120b`; set `GROQ_MODEL` to another
model enabled for the configured Groq account if needed.
No API key or password is included in this repository.

## Run

Activate the virtual environment and start the interactive agent:

```bash
source .venv/bin/activate
python -m agents.hive_agent
```

The agent discovers MCP tools at startup. It keeps conversational follow-ups
within that CLI process; restarting the process starts a fresh session. Enter
`exit` or `quit` to end the session.

## SQL safeguards

Calls to `execute_query` are parsed with SQLGlot in Hive dialect. The client
rejects anything other than a single read-only SELECT query, including
modification statements (including nested statements) and multi-statement
input, and imposes the configured top-level result limit. The limit can be set
using `MAX_RESULT_ROWS` (1-500). MCP operations and agent responses are bounded
by `MCP_TIMEOUT_SECONDS` and `AGENT_TIMEOUT_SECONDS`. Metadata operations should
use the dedicated MCP metadata tools.

These client-side controls are defense in depth, not a security boundary.
They cannot guarantee that every database expression or server-side function is
side-effect free, and they do not replace database-level read-only permissions.
Configure suitable read-only permissions independently; this client never
changes Hive permissions or database settings. Tool output is treated as
untrusted data, and the agent has no shell-execution tool.

## Tests

Run unit tests:

```bash
pytest
```

Run the integration test against the live Hive MCP server and HiveServer2:

```bash
pytest -m integration -o addopts=''
```

The integration test discovers all four tools, verifies destructive SQL is
blocked before reaching the server, checks metadata and transaction count, and
runs the Canada transaction and country-total queries. It requires the
configured Hive service to be available.

## Troubleshooting

- **MCP executable not found / spawn failure:** verify
  `HIVE_MCP_COMMAND` is an executable absolute or home-relative path.
- **HiveServer2 connection errors:** verify HiveServer2 is running and reachable
  at `SPARK_HOST:SPARK_PORT`; check `SPARK_DATABASE` and `SPARK_AUTH`.
- **Missing Groq key:** add `GROQ_API_KEY` to `.env`. The integration test does
  not require Groq, but the interactive agent does.
- **Groq model or API errors:** set `GROQ_MODEL` to an available model for the
  configured account and verify the API key/account quota.
- **Query rejected:** only one parseable read-only SELECT query is accepted by
  the SQL tool. Use `list_databases`, `list_tables`, or `describe_table` for
  metadata requests.
