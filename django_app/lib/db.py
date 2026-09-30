"""Database helpers using Django ORM and django.db."""

from typing import Any, List, Dict
from django.db import connection
from lib.logs import get_logger, logged

logger = get_logger(__name__)


@logged
def check_db_connection() -> bool:
    """Verify that PostgreSQL database is reachable via Django connection."""
    logger.debug("Checking PostgreSQL connection")
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
        row = cursor.fetchone()
        result = bool(row and row[0] == 1)
        logger.debug("PostgreSQL connection checked connected=%s", result)
        return result


@logged
def get_db_version() -> str:
    """Return PostgreSQL server version."""
    logger.debug("Requesting PostgreSQL version")
    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        row = cursor.fetchone()
        logger.debug("PostgreSQL version request completed")
        return row[0] if row else ""


@logged
def execute_query(sql: str, params: list | None = None) -> List[Dict[str, Any]]:
    """Execute raw SQL query and return rows as list of dictionaries."""
    logger.debug("Executing PostgreSQL query params_count=%s", len(params or []))
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        if cursor.description is None:
            logger.debug("PostgreSQL query completed rows=0")
            return []
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        logger.debug("PostgreSQL query completed rows=%s", len(rows))
        return rows
