"""
Reset local demo state (SQLite DB + generated storage).

Default behavior:
- Deletes the local SQLite DB file (wildlife.db) and recreates tables.
- Clears generated storage subfolders (thumbnails/crops).

Usage:
  python scripts/reset_demo.py
  python scripts/reset_demo.py --db-only
  python scripts/reset_demo.py --storage-only
  python scripts/reset_demo.py --db-name wildlife.db
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path


def _project_root() -> Path:
    # scripts/ is at project root in this repo
    return Path(__file__).resolve().parent.parent


def _delete_file_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except TypeError:
        # Python < 3.8 fallback (unlikely here, but safe)
        if path.exists():
            path.unlink()


def _clear_dir_contents(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except OSError:
                pass


async def _recreate_tables() -> None:
    # Import inside function so PYTHONPATH issues surface clearly
    from backend.app.db.init_db import init_database

    await init_database()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset demo DB and generated storage.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--db-only", action="store_true", help="Only reset the SQLite DB.")
    group.add_argument(
        "--storage-only", action="store_true", help="Only clear generated storage."
    )
    parser.add_argument(
        "--db-name",
        default="wildlife.db",
        help="SQLite DB filename at project root (default: wildlife.db).",
    )
    args = parser.parse_args()

    root = _project_root()
    # Ensure `import backend...` works when running as a script on Windows.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    do_db = not args.storage_only
    do_storage = not args.db_only

    if do_db:
        db_path = (root / args.db_name).resolve()
        _delete_file_if_exists(db_path)
        asyncio.run(_recreate_tables())
        print(f"Reset database: {db_path}")

    if do_storage:
        storage_root = (root / "storage").resolve()
        for sub in ("thumbnails", "crops"):
            _clear_dir_contents(storage_root / sub)
        print(f"Cleared generated storage under: {storage_root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

