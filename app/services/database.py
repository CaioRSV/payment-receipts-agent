import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "receipts.db")
DB_FILE = "test_receipts.db" if "pytest" in sys.modules else DB_PATH

# Ensure parent directory of DB_FILE exists
db_dir = os.path.dirname(DB_FILE)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

DEFAULT_SIGNER_NAME = os.getenv("DEFAULT_SIGNER_NAME", "Default Signer")
DEFAULT_SIGNER_ADDRESS = os.getenv("DEFAULT_SIGNER_ADDRESS", "Default Address")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Default Location")


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
        cursor.execute("SELECT signer_name, signer_address, location FROM config WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                """
                INSERT INTO config (id, signer_name, signer_address, location)
                VALUES (1, ?, ?, ?)
                """,
                (DEFAULT_SIGNER_NAME, DEFAULT_SIGNER_ADDRESS, DEFAULT_LOCATION)
            )
            conn.commit()
        else:
            db_name, db_address, db_location = row
            updated = False
            # Check if name is a placeholder or left over from test pollution, and .env has custom values
            if (db_name in ("Default Signer", "Test Signer Editado", "Test User Name")) and DEFAULT_SIGNER_NAME not in ("Default Signer", "Test Signer Editado", "Test User Name"):
                cursor.execute("UPDATE config SET signer_name = ? WHERE id = 1", (DEFAULT_SIGNER_NAME,))
                updated = True
            if (db_address in ("Default Address", "Av Teste, 100", "Test User Address, 123")) and DEFAULT_SIGNER_ADDRESS not in ("Default Address", "Av Teste, 100", "Test User Address, 123"):
                cursor.execute("UPDATE config SET signer_address = ? WHERE id = 1", (DEFAULT_SIGNER_ADDRESS,))
                updated = True
            if (db_location in ("Default Location", "TEST LOCAL", "TEST LOCATION")) and DEFAULT_LOCATION not in ("Default Location", "TEST LOCAL", "TEST LOCATION"):
                cursor.execute("UPDATE config SET location = ? WHERE id = 1", (DEFAULT_LOCATION,))
                updated = True
            if updated:
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
