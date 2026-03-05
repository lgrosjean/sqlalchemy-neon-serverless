"""Tests for the Neon Serverless DBAPI 2.0 adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sqlalchemy_neon_serverless.dbapi import (
    Connection,
    DatabaseError,
    InterfaceError,
    _format_to_dollar,
    _serialize,
    connect,
)


def test_format_no_params():
    """Passes SQL through unchanged when there are no params."""
    sql, params = _format_to_dollar("SELECT 1", None)
    assert sql == "SELECT 1"
    assert params == []


def test_format_single_param():
    """Converts a single %s to $1."""
    sql, params = _format_to_dollar("SELECT * FROM t WHERE id = %s", ["abc"])
    assert sql == "SELECT * FROM t WHERE id = $1"
    assert params == ["abc"]


def test_format_multiple_params():
    """Converts multiple %s to $1, $2, $3."""
    sql, params = _format_to_dollar("INSERT INTO t (a, b, c) VALUES (%s, %s, %s)", [1, 2, 3])
    assert sql == "INSERT INTO t (a, b, c) VALUES ($1, $2, $3)"
    assert params == [1, 2, 3]


def test_serialize_datetime():
    """Serializes datetime to ISO format."""
    from datetime import UTC, datetime

    dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
    assert _serialize(dt) == "2025-01-15T12:00:00+00:00"


def test_serialize_nan():
    """Converts NaN to None."""
    assert _serialize(float("nan")) is None


def test_serialize_inf():
    """Converts Inf to None."""
    assert _serialize(float("inf")) is None


def test_serialize_dict():
    """Serializes dict to JSON string."""
    import json

    result = _serialize({"key": "value"})
    assert json.loads(result) == {"key": "value"}


def test_serialize_passthrough():
    """Passes through plain values unchanged."""
    assert _serialize("hello") == "hello"
    assert _serialize(42) == 42
    assert _serialize(None) is None


def _make_cursor(response_data: dict):
    """Create a cursor with a mocked HTTP client."""
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = response_data

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    conn = Connection(
        http_client=mock_client,
        endpoint="https://test.neon.tech/sql",
        connection_string="postgresql://user:pass@test.neon.tech/db",
    )
    return conn.cursor(), mock_client


def test_execute_sends_correct_request():
    """Sends POST with converted SQL and serialized params."""
    cursor, mock_client = _make_cursor({"fields": [], "rows": []})

    cursor.execute("SELECT * FROM t WHERE id = %s", ["abc"])

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[0][0] == "https://test.neon.tech/sql"
    body = call_kwargs[1]["json"]
    assert body["query"] == "SELECT * FROM t WHERE id = $1"
    assert body["params"] == ["abc"]


def test_fetchall_returns_tuples():
    """Returns rows as tuples from fetchall."""
    cursor, _ = _make_cursor(
        {
            "fields": [{"name": "id"}, {"name": "name"}],
            "rows": [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}],
        }
    )
    cursor.execute("SELECT * FROM t")

    rows = cursor.fetchall()
    assert rows == [("1", "Alice"), ("2", "Bob")]


def test_fetchone_iterates():
    """fetchone returns rows one at a time."""
    cursor, _ = _make_cursor(
        {
            "fields": [{"name": "id"}],
            "rows": [{"id": "1"}, {"id": "2"}],
        }
    )
    cursor.execute("SELECT * FROM t")

    assert cursor.fetchone() == ("1",)
    assert cursor.fetchone() == ("2",)
    assert cursor.fetchone() is None


def test_fetchmany():
    """fetchmany returns requested number of rows."""
    cursor, _ = _make_cursor(
        {
            "fields": [{"name": "id"}],
            "rows": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        }
    )
    cursor.execute("SELECT * FROM t")

    assert len(cursor.fetchmany(2)) == 2
    assert len(cursor.fetchmany(2)) == 1


def test_description_set():
    """description is set from response fields."""
    cursor, _ = _make_cursor(
        {
            "fields": [{"name": "id", "dataTypeID": 25}, {"name": "count", "dataTypeID": 23}],
            "rows": [],
        }
    )
    cursor.execute("SELECT id, count FROM t")

    assert cursor.description is not None
    assert len(cursor.description) == 2
    assert cursor.description[0][0] == "id"
    assert cursor.description[1][0] == "count"


def test_rowcount():
    """rowcount reflects number of returned rows."""
    cursor, _ = _make_cursor(
        {
            "fields": [{"name": "id"}],
            "rows": [{"id": "1"}, {"id": "2"}],
        }
    )
    cursor.execute("SELECT * FROM t")
    assert cursor.rowcount == 2


def test_execute_raises_on_http_error():
    """Raises DatabaseError on non-success HTTP response."""
    mock_response = MagicMock()
    mock_response.is_success = False
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    conn = Connection(
        http_client=mock_client,
        endpoint="https://test.neon.tech/sql",
        connection_string="postgresql://user:pass@test/db",
    )
    cursor = conn.cursor()

    with pytest.raises(DatabaseError, match="400"):
        cursor.execute("BAD SQL")


def test_array_row_format():
    """Handles Neon's array row format (legacy)."""
    cursor, _ = _make_cursor(
        {
            "fields": [{"name": "id"}, {"name": "name"}],
            "rows": [["1", "Alice"], ["2", "Bob"]],
        }
    )
    cursor.execute("SELECT * FROM t")

    rows = cursor.fetchall()
    assert rows == [("1", "Alice"), ("2", "Bob")]


def test_json_values_normalized():
    """Dict/list values are re-serialized as JSON strings."""
    cursor, _ = _make_cursor(
        {
            "fields": [{"name": "id"}, {"name": "data"}],
            "rows": [{"id": "1", "data": {"key": "value"}}],
        }
    )
    cursor.execute("SELECT * FROM t")

    row = cursor.fetchone()
    assert row is not None
    assert isinstance(row[1], str)  # JSON re-serialized as string


def test_connect_requires_endpoint():
    """Raises InterfaceError when required args are missing."""
    with pytest.raises(InterfaceError):
        connect()


def test_connect_returns_connection(mocker):
    """Returns a Connection with valid args."""
    mocker.patch("httpx.Client")
    conn = connect(
        endpoint="https://test.neon.tech/sql",
        connection_string="postgresql://user:pass@test/db",
    )
    assert isinstance(conn, Connection)
