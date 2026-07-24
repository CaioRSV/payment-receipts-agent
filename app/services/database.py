import sqlite3
from pathlib import Path

DB_FILE = "receipts.db"

DEFAULT_SIGNER_NAME = "MÁRCIA SANTOS DA SILVA VERÇOSA"
DEFAULT_SIGNER_ADDRESS = "RUA JOÃO MURILO DE OLIVEIRA, 142, SÃO VICENTE DE PAULO."
DEFAULT_LOCATION = "VITÓRIA-PE"


def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_db():
    """Initializes the SQLite database, creates the configuration table, and seeds defaults."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                signer_name TEXT NOT NULL,
                signer_address TEXT NOT NULL,
                location TEXT NOT NULL
            )
            """
        )
        # Check if seed config already exists
        cursor.execute("SELECT COUNT(*) FROM config WHERE id = 1")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                """
                INSERT INTO config (id, signer_name, signer_address, location)
                VALUES (1, ?, ?, ?)
                """,
                (DEFAULT_SIGNER_NAME, DEFAULT_SIGNER_ADDRESS, DEFAULT_LOCATION)
            )
            conn.commit()
    finally:
        conn.close()


def get_db_config() -> dict[str, str]:
    """Fetches the current signer configurations from the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT signer_name, signer_address, location FROM config WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return {
                "signer_name": row[0],
                "signer_address": row[1],
                "location": row[2]
            }
        else:
            return {
                "signer_name": DEFAULT_SIGNER_NAME,
                "signer_address": DEFAULT_SIGNER_ADDRESS,
                "location": DEFAULT_LOCATION
            }
    finally:
        conn.close()


def update_db_config(signer_name: str, signer_address: str, location: str) -> None:
    """Updates the database configuration row with new default settings."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO config (id, signer_name, signer_address, location)
            VALUES (1, ?, ?, ?)
            """,
            (signer_name, signer_address, location)
        )
        conn.commit()
    finally:
        conn.close()
