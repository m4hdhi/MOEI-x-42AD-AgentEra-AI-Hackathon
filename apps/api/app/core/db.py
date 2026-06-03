"""Thin sync psycopg pool. Used by /crm, /notifications, /activity, /exec routes.

Sync (not async) intentionally — these are short queries and FastAPI's sync wrapper handles them
on the thread pool. Keeps the code simple.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _conn_str() -> str:
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://hassan:hassan_dev@localhost:5432/hassan")
    return url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")


@lru_cache(maxsize=1)
def get_pool() -> ConnectionPool:
    # Larger pool — FastAPI under load + the background dispatcher both need connections
    pool = ConnectionPool(_conn_str(), min_size=2, max_size=20, open=True, timeout=10)
    return pool


@contextmanager
def db_cursor():
    pool = get_pool()
    with pool.connection() as conn:
        conn.row_factory = dict_row
        with conn.cursor() as cur:
            yield cur
            conn.commit()
