#!/usr/bin/env python3
"""Quick inspection: list DB tables, counts and check GamerPower API."""
from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.request
import sys
from pathlib import Path


def _sqlite_path_from_url(database_url: str) -> str:
    """Extract sqlite file path from SQLAlchemy URL.

    Supports sqlite:///... and sqlite+aiosqlite:///... forms.
    """
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if database_url.startswith(prefix):
            return database_url.removeprefix(prefix)
    return "data/bot.db"


def _resolve_db_path(cli_db_path: str | None) -> str:
    if cli_db_path:
        return cli_db_path

    try:
        from bot.core.database import get_effective_database_url

        raw_path = _sqlite_path_from_url(get_effective_database_url())
        return str(Path(raw_path).expanduser().resolve())
    except Exception:
        return str(Path("data/bot.db").resolve())

def list_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]

def count_table(conn, table):
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]
    except Exception:
        return None

def check_api(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
            if isinstance(data, list):
                return len(data)
            return 0
    except Exception as exc:
        return f"ERROR: {exc}"

def main():
    parser = argparse.ArgumentParser(description="Inspect local DB tables and GamerPower API")
    parser.add_argument("--db-path", dest="db_path", help="Path to sqlite database file")
    args = parser.parse_args()

    db_path = _resolve_db_path(args.db_path)
    print("DB path:", db_path)
    try:
        conn = sqlite3.connect(db_path)
    except Exception as exc:
        print("Cannot open DB:", exc)
        sys.exit(2)

    tables = list_tables(conn)
    print("Tables:")
    for t in tables:
        print(" -", t)

    print("\nCounts:")
    for t in ("users", "games"):
        c = count_table(conn, t)
        print(f" {t}: {c}")

    # Attempt to read API URL from config if available
    try:
        from bot.core.config import settings
        url = settings.GAMERPOWER_API_URL
    except Exception:
        url = "https://www.gamerpower.com/api/giveaways?type=game&platform=pc,steam,epic-games-store,gog"

    print("\nChecking GamerPower API URL:")
    print(url)
    api_count = check_api(url)
    print("API items:", api_count)


if __name__ == '__main__':
    main()
