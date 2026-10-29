"""Tests for quiet MCP subprocess logging without swallowing warnings."""

import os
import subprocess
import sys

from config.settings import Settings


def test_mcp_subprocess_hides_info_but_keeps_warnings_off_stdout() -> None:
    pythonpath = Settings.from_env().mcp_servers["hive"]["env"]["PYTHONPATH"]
    environment = {**os.environ, "PYTHONPATH": pythonpath}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import logging; "
                "print('protocol stdout'); "
                "logging.info('internal info'); "
                "logging.warning('visible warning')"
            ),
        ],
        capture_output=True,
        check=True,
        env=environment,
        text=True,
    )

    assert result.stdout == "protocol stdout\n"
    assert "internal info" not in result.stderr
    assert "visible warning" in result.stderr
