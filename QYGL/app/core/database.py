"""SQLite database — WAL mode, connection pool, migrations, backup.

This is the ONLY module allowed to execute raw SQL.
Agent runtime accesses data through the sqlite_data Skill.
Dashboard admin API may use this directly.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path("data/qfbj.db")
MIGRATIONS_DIR = Path("data/migrations")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Database:
    _instance: Database | None = None

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DB_PATH)
        self._conn: sqlite3.Connection | None = None

    @classmethod
    def get_instance(cls, db_path: str | Path | None = None) -> Database:
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance and cls._instance._conn:
            cls._instance._conn.close()
        cls._instance = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    # ── Core operations ──────────────────────────────────────────

    def execute(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        cursor = self.conn.execute(sql, params)
        if cursor.description:
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        self.conn.commit()
        return []

    def execute_many(self, sql: str, params_list: list[tuple]) -> int:
        cursor = self.conn.executemany(sql, params_list)
        self.conn.commit()
        return cursor.rowcount

    def insert(self, table: str, data: dict[str, Any]) -> str:
        data = dict(data)
        if "id" not in data or not data["id"]:
            data["id"] = new_id()
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                data[k] = json.dumps(v, ensure_ascii=False)
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        self.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", tuple(data.values()))
        return data["id"]

    def update(self, table: str, record_id: str, data: dict[str, Any]) -> None:
        data = dict(data)
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                data[k] = json.dumps(v, ensure_ascii=False)
        sets = ", ".join([f"{k}=?" for k in data.keys()])
        self.execute(f"UPDATE {table} SET {sets} WHERE id=?", (*data.values(), record_id))

    def delete(self, table: str, record_id: str) -> None:
        self.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))

    def query(
        self,
        table: str,
        conditions: dict[str, Any] | None = None,
        order_by: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = f"SELECT * FROM {table}"
        params: list[Any] = []
        if conditions:
            clauses = []
            for k, v in conditions.items():
                if isinstance(v, list):
                    placeholders = ",".join(["?"] * len(v))
                    clauses.append(f"{k} IN ({placeholders})")
                    params.extend(v)
                else:
                    clauses.append(f"{k}=?")
                    params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        if order_by:
            sql += f" ORDER BY {order_by}"
        sql += f" LIMIT {limit} OFFSET {offset}"
        return self.execute(sql, tuple(params))

    def count(self, table: str, conditions: dict[str, Any] | None = None) -> int:
        sql = f"SELECT COUNT(*) as cnt FROM {table}"
        params: list[Any] = []
        if conditions:
            clauses = []
            for k, v in conditions.items():
                if isinstance(v, list):
                    placeholders = ",".join(["?"] * len(v))
                    clauses.append(f"{k} IN ({placeholders})")
                    params.extend(v)
                else:
                    clauses.append(f"{k}=?")
                    params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        rows = self.execute(sql, tuple(params))
        return rows[0]["cnt"] if rows else 0

    def get_by_id(self, table: str, record_id: str) -> dict[str, Any] | None:
        rows = self.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,))
        return rows[0] if rows else None

    # ── Migrations ───────────────────────────────────────────────

    def run_migrations(self, migrations_dir: str | Path | None = None) -> int:
        mdir = Path(migrations_dir or MIGRATIONS_DIR)
        if not mdir.exists():
            logger.warning("Migrations directory not found: %s", mdir)
            return 0

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        self.conn.commit()

        rows = self.execute("SELECT MAX(version) as v FROM schema_version")
        current = rows[0]["v"] or 0

        applied = 0
        for sql_file in sorted(mdir.glob("*.sql")):
            version = int(sql_file.stem.split("_")[0])
            if version <= current:
                continue
            logger.info("Applying migration %s ...", sql_file.name)
            self.conn.executescript(sql_file.read_text(encoding="utf-8"))
            self.conn.commit()
            applied += 1

        logger.info("Migrations complete. Applied %d, current version %d", applied, current + applied)
        return applied

    # ── Backup ───────────────────────────────────────────────────

    def backup(self, target_path: str) -> None:
        target = sqlite3.connect(target_path)
        self.conn.backup(target)
        target.close()
        logger.info("Database backed up to %s", target_path)

    # ── Cleanup ──────────────────────────────────────────────────

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
