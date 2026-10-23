"""One shared SQLite connection: every local table lives in the portfolio
database, so all modules connect identically."""

import sqlite3

from app.config import settings


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.db_path)
    connection.row_factory = sqlite3.Row
    return connection
