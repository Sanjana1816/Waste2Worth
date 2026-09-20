"""Add columns that were introduced after the database was first created.

    python -m scripts.migrate

Safe to run as often as you like: it only adds what's missing, and never drops or rewrites data.
(New *tables* are created automatically at startup; only new *columns* need this.)
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import engine, init_db

# table -> column -> SQL type (kept simple: every added column is nullable)
COLUMNS = {
    "pool": {"confirmed_at": "TIMESTAMP", "delivered_at": "TIMESTAMP"},
    "poolitem": {"picked_up_at": "TIMESTAMP"},
}


def main() -> None:
    init_db()                       # creates any brand-new tables first
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    added = 0
    with engine.begin() as conn:
        for table, columns in COLUMNS.items():
            if table not in tables:
                print(f"  {table}: table not present yet, skipped")
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for column, sql_type in columns.items():
                if column in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {sql_type}'))
                print(f"  {table}.{column} added")
                added += 1
    print(f"Done. {added} column{'s' if added != 1 else ''} added." if added else "Done. Already up to date.")


if __name__ == "__main__":
    main()
