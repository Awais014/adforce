"""Postgres (Supabase/Neon). One lazy pool shared by tools, checkpointer and store."""
import os
from pathlib import Path
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(os.environ["DATABASE_URL"], max_size=5,
                               kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        for st in (Path(__file__).resolve().parent.parent / "schema.sql").read_text().split(";"):
            if st.strip():
                q(st)
    return _pool

def q(sql, args=(), one=False):
    pool = _pool or get_pool()
    with pool.connection() as c:
        cur = c.execute(sql, args)
        if cur.description is None:
            return None
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
