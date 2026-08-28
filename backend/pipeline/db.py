"""DB 연결 헬퍼."""
from __future__ import annotations

import os

import psycopg

DEFAULT_URL = "postgresql://roadwatch:roadwatch@localhost:15432/roadwatch"


def dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def connect() -> psycopg.Connection:
    return psycopg.connect(dsn(), autocommit=False)
