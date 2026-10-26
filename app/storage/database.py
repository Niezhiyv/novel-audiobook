from __future__ import annotations

import sqlite3
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1

SCHEMA_V1 = """
CREATE TABLE projects (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_chapter_id INTEGER,
    last_filter TEXT NOT NULL DEFAULT ''
);

CREATE TABLE chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_index INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    output_path TEXT,
    error TEXT
);

CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    voice_id TEXT,
    speed REAL NOT NULL DEFAULT 1.0,
    is_narrator INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    evidence TEXT,
    UNIQUE (chapter_id, position)
);

CREATE INDEX idx_segments_chapter_id ON segments(chapter_id, position);
CREATE INDEX idx_segments_role_id ON segments(role_id);
"""


class SchemaVersionError(RuntimeError):
    pass


def connect_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database(path: Path) -> None:
    connection = connect_database(path)
    try:
        with connection:
            connection.executescript(SCHEMA_V1)
            connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
    finally:
        connection.close()


def open_and_migrate_database(path: Path) -> sqlite3.Connection:
    connection = connect_database(path)
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > CURRENT_SCHEMA_VERSION:
        connection.close()
        raise SchemaVersionError(
            f"项目数据库版本 {version} 高于当前支持版本 {CURRENT_SCHEMA_VERSION}"
        )
    if version == 0:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if tables:
            connection.close()
            raise SchemaVersionError("项目数据库缺少有效 schema 版本")
        with connection:
            connection.executescript(SCHEMA_V1)
            connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
    return connection

