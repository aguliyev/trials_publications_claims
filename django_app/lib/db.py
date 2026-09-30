"""Database helpers using Django ORM and django.db."""

from typing import Any, List, Dict
from django.db import connection


def check_db_connection() -> bool:
    """Verify that PostgreSQL database is reachable via Django connection."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
        row = cursor.fetchone()
        return bool(row and row[0] == 1)


def get_db_version() -> str:
    """Return PostgreSQL server version."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        row = cursor.fetchone()
        return row[0] if row else ""


def execute_query(sql: str, params: list | None = None) -> List[Dict[str, Any]]:
    """Execute raw SQL query and return rows as list of dictionaries."""
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
