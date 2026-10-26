"""SQLite connection management and table setup."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Keep the local database beside the backend project, not in the source package.
DATABASE_PATH = Path(__file__).resolve().parents[2] / "devmate.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open one database connection and always close it after use."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the projects table the first time the application starts."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                filename TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                UNIQUE(document_id, chunk_index)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_questions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                model TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                structured_answer_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_action_plans (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                workflow_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                actions_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_investigations (
                workflow_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        question_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(project_questions)")
        }
        if "structured_answer_json" not in question_columns:
            connection.execute(
                "ALTER TABLE project_questions ADD COLUMN structured_answer_json TEXT"
            )
