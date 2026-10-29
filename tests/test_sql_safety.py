"""Tests for client-side SQL validation and result limits."""

import pytest

from clients.mcp_client import SQLSafetyError, validate_and_bound_sql


def test_accepts_select_and_caps_unbounded_results() -> None:
    bounded = validate_and_bound_sql(
        "SELECT transaction_id FROM banking_transactions",
        max_rows=50,
    )
    assert bounded.endswith("LIMIT 50")


def test_preserves_smaller_limit() -> None:
    bounded = validate_and_bound_sql(
        "SELECT transaction_id FROM banking_transactions LIMIT 10",
        max_rows=50,
    )
    assert bounded.endswith("LIMIT 10")


def test_caps_larger_limit() -> None:
    bounded = validate_and_bound_sql(
        "SELECT transaction_id FROM banking_transactions LIMIT 1000",
        max_rows=50,
    )
    assert bounded.endswith("LIMIT 50")


def test_accepts_read_only_cte() -> None:
    bounded = validate_and_bound_sql(
        "WITH flagged AS (SELECT * FROM banking_transactions) "
        "SELECT * FROM flagged",
        max_rows=50,
    )
    assert bounded.endswith("LIMIT 50")


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO banking_transactions VALUES ('x', 'y', 1, 'z', 'a')",
        "UPDATE banking_transactions SET status = 'x'",
        "DELETE FROM banking_transactions",
        "DROP TABLE banking_transactions",
        "ALTER TABLE banking_transactions ADD COLUMNS (new_col STRING)",
        "CREATE TABLE another_table (id INT)",
        "TRUNCATE TABLE banking_transactions",
        "SELECT * FROM banking_transactions; DROP TABLE banking_transactions",
        "WITH removed AS (DELETE FROM banking_transactions RETURNING *) "
        "SELECT * FROM removed",
    ],
)
def test_rejects_modification_and_multiple_statements(sql: str) -> None:
    with pytest.raises(SQLSafetyError):
        validate_and_bound_sql(sql, max_rows=50)


def test_rejects_empty_or_non_query_input() -> None:
    for sql in ("", "SHOW TABLES", "EXPLAIN SELECT 1"):
        with pytest.raises(SQLSafetyError):
            validate_and_bound_sql(sql, max_rows=50)
