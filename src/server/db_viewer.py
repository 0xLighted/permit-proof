"""
PermitProof - Stage 2 Database Viewer & Navigator CLI
An interactive and CLI inspection tool to navigate, browse, and inspect
every SQLite table in the PermitProof database.
"""

import sys
import os
import argparse
import datetime
import json
import shutil

from server.db import db


def _format_val(k: str, v: any, max_len: int = 24) -> str:
    if v is None:
        return "-"
    # Format timestamps
    if any(t in k.lower() for t in ("_at", "timestamp", "expires")) and isinstance(v, (int, float)) and v > 1000000000:
        dt = datetime.datetime.fromtimestamp(v, tz=datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    # Truncate hashes and long strings
    s = str(v)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def print_table_view(table_name: str, rows: list, columns: list, page: int, total_rows: int, page_size: int):
    term_width = shutil.get_terminal_size((100, 24)).columns
    print("\n" + "=" * min(term_width, 100))
    print(f"  TABLE: {table_name} (Page {page + 1}, showing {len(rows)} of {total_rows} rows)")
    print("=" * min(term_width, 100))

    if not rows:
        print("  (Table is currently empty)")
        print("-" * min(term_width, 100))
        return

    # Calculate optimal column widths
    col_widths = {}
    for col in columns:
        col_widths[col] = min(max(len(col), 8), 26)

    # Print Header
    header_str = " #  " + " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
    print(header_str[:term_width])
    print("-" * min(term_width, len(header_str) + 4))

    # Print Rows
    for idx, row in enumerate(rows, start=1):
        line = f"{idx:<3} " + " | ".join(f"{_format_val(col, row.get(col), col_widths[col]):<{col_widths[col]}}" for col in columns)
        print(line[:term_width])

    print("-" * min(term_width, 100))


def inspect_row_detail(table_name: str, row: dict):
    print("\n" + "=" * 80)
    print(f"  INSPECT ROW - {table_name}")
    print("=" * 80)
    for k, v in row.items():
        if any(t in k.lower() for t in ("_at", "timestamp", "expires")) and isinstance(v, (int, float)) and v > 1000000000:
            dt = datetime.datetime.fromtimestamp(v, tz=datetime.timezone.utc)
            readable = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"  {k:<22}: {v}  ({readable})")
        elif "json" in k.lower() and isinstance(v, str):
            try:
                parsed = json.loads(v)
                formatted = json.dumps(parsed, indent=4)
                print(f"  {k:<22}:\n{formatted}")
            except Exception:
                print(f"  {k:<22}: {v}")
        else:
            print(f"  {k:<22}: {v}")
    print("=" * 80)
    input("\nPress Enter to return...")


def view_table_interactive(table_name: str):
    page = 0
    page_size = 10
    columns = db.get_table_columns(table_name)

    while True:
        total = db.get_table_count(table_name)
        offset = page * page_size
        rows = db.get_table_rows(table_name, limit=page_size, offset=offset)

        print_table_view(table_name, rows, columns, page, total, page_size)

        max_page = max(0, (total - 1) // page_size)
        actions = []
        if page > 0:
            actions.append("[p] Previous page")
        if page < max_page:
            actions.append("[n] Next page")
        if rows:
            actions.append("[1-9] Inspect row")
        actions.append("[b] Back to tables")
        actions.append("[r] Refresh")

        print("Actions: " + " | ".join(actions))
        choice = input("Enter action or row number: ").strip().lower()

        if choice == "b":
            break
        elif choice == "n" and page < max_page:
            page += 1
        elif choice == "p" and page > 0:
            page -= 1
        elif choice == "r":
            continue
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(rows):
                inspect_row_detail(table_name, rows[idx - 1])
            else:
                print("[-] Invalid row index.")


def interactive_navigator():
    db.init_schema()
    while True:
        tables = db.get_table_names()
        print("\n" + "=" * 70)
        print("  PERMITPROOF DATABASE TABLE NAVIGATOR (SQLite)")
        print(f"  Database file: {db.db_path}")
        print("=" * 70)

        for i, tbl in enumerate(tables, start=1):
            count = db.get_table_count(tbl)
            print(f"  [{i}] {tbl:<20} ({count} rows)")

        print("-" * 70)
        print("  [s] Seed default fixtures (Alice, Jasmine, Alpha Room)")
        print("  [q] Quit navigator")
        print("-" * 70)

        choice = input("Select table number or name: ").strip().lower()

        if choice == "q":
            print("Exiting navigator.")
            break
        elif choice == "s":
            from server.seed import seed_database
            seed_database()
            continue

        selected_table = None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(tables):
                selected_table = tables[idx - 1]
        elif choice in tables:
            selected_table = choice

        if selected_table:
            view_table_interactive(selected_table)
        else:
            print("[-] Unknown table selection.")


def main():
    parser = argparse.ArgumentParser(description="PermitProof SQLite Database Viewer & Navigator")
    parser.add_argument("table", nargs="?", help="Table name to dump directly (e.g. users, jobs, audit_events)")
    parser.add_argument("--limit", type=int, default=50, help="Max rows to dump")
    parser.add_argument("--offset", type=int, default=0, help="Row offset")
    parser.add_argument("--all", action="store_true", help="Dump summary of all tables")
    args = parser.parse_args()

    db.init_schema()

    if args.all:
        tables = db.get_table_names()
        print(f"\nPermitProof SQLite Tables ({db.db_path}):")
        for t in tables:
            cnt = db.get_table_count(t)
            print(f"  - {t:<20}: {cnt} rows")
        print()
        return

    if args.table:
        table_name = args.table.lower()
        if table_name not in db.get_table_names():
            print(f"[-] Error: Table '{table_name}' does not exist.")
            print(f"Available tables: {', '.join(db.get_table_names())}")
            return
        cols = db.get_table_columns(table_name)
        rows = db.get_table_rows(table_name, limit=args.limit, offset=args.offset)
        total = db.get_table_count(table_name)
        print_table_view(table_name, rows, cols, 0, total, args.limit)
        return

    # Default: Interactive TUI / Navigator
    interactive_navigator()


if __name__ == "__main__":
    main()
