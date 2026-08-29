"""DB 커넥션 풀.

DSN 규약은 pipeline.db 와 같다 — 같은 DATABASE_URL 을 읽으므로 파이프라인과
API 가 항상 같은 DB 를 본다. 파이프라인은 배치라 매번 새 커넥션을 열지만,
API 는 요청마다 열면 느리므로 풀을 쓴다.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from pipeline.db import dsn

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(dsn(), min_size=1, max_size=8, open=True,
                               kwargs={"row_factory": dict_row})
    return _pool


@contextmanager
def cursor(commit: bool = False) -> Iterator:
    """조회는 그대로, 쓰기는 commit=True."""
    with pool().connection() as conn:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
