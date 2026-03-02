#!/usr/bin/env python3
"""Quick inspection: list DB tables, counts and check GamerPower API."""
import json
import sqlite3
import urllib.request
import sys

DB_PATH = "/app/data/bot.db"

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
    print("DB path:", DB_PATH)
    try:
        conn = sqlite3.connect(DB_PATH)
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
