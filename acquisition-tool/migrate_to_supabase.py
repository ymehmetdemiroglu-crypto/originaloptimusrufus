"""One-shot migration: copy all rows from local SQLite → Supabase.

Safe to re-run: upserts on primary key so duplicates are overwritten, not doubled.

Usage:
    python migrate_to_supabase.py
"""
import sqlite3
from pathlib import Path

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

DB_PATH = "data/prospects.db"
BATCH_SIZE = 100


def _fix_timestamps(d: dict, cols: list[str]) -> dict:
    for col in cols:
        v = d.get(col)
        if v and isinstance(v, str):
            d[col] = v.replace(" ", "T")
    return d


def _fix_prospects_row(row: dict) -> dict:
    d = _fix_timestamps(dict(row), [
        "messaged_at", "last_followup", "next_followup", "created_at", "updated_at"
    ])
    raw = d.get("has_a_plus")
    d["has_a_plus"] = bool(raw) if raw is not None else None
    return d


def _fix_brands_row(row: dict) -> dict:
    return _fix_timestamps(dict(row), ["replied_at", "created_at", "updated_at"])


def _fix_step_emails_row(row: dict) -> dict:
    return _fix_timestamps(dict(row), ["created_at"])


def _chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def migrate_table(client, conn, table: str, pk_conflict: str, fix_fn):
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    total = len(rows)
    print(f"\n=== {table}: {total} rows ===")
    if total == 0:
        return

    upserted = 0
    errors = 0
    for batch in _chunk(rows, BATCH_SIZE):
        payload = [fix_fn(dict(r)) for r in batch]
        try:
            client.table(table).upsert(payload, on_conflict=pk_conflict).execute()
            upserted += len(batch)
            print(f"  upserted {upserted}/{total}", end="\r")
        except Exception as e:
            errors += len(batch)
            print(f"\n  ERROR on batch of {len(batch)}: {e}")

    print(f"\n  done — upserted={upserted}  errors={errors}")


def main():
    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"SQLite not found at {db_path}")
        return

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE_URL / SUPABASE_KEY not set in .env")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    migrate_table(client, conn, "prospects",        "id",                _fix_prospects_row)
    migrate_table(client, conn, "brands",           "brand_key",         _fix_brands_row)
    migrate_table(client, conn, "brand_step_emails","brand_key,step_num",_fix_step_emails_row)

    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
