import json
import os
import sqlite3
import tempfile
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


class TestDatabaseMigration:
    """Test Alembic database migrations and legacy SQLite cards preservation."""

    def test_legacy_cards_db_migration_preserves_cards(self):
        # 1. Create a temporary SQLite database with the legacy schema
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            tmp_db_path = tmp_file.name

        try:
            # Connect directly with sqlite3 to simulate pre-Phase 1 database state
            conn = sqlite3.connect(tmp_db_path)
            conn.execute("""
                CREATE TABLE cards (
                    public_id TEXT PRIMARY KEY,
                    serial TEXT NOT NULL,
                    game_id TEXT,
                    grid TEXT NOT NULL
                )
            """)
            sample_grid = [[1, 16, 31, 46, 61], [2, 17, 32, 47, 62], [3, 18, "FREE", 48, 63], [4, 19, 34, 49, 64], [5, 20, 35, 50, 65]]
            conn.execute(
                "INSERT INTO cards (public_id, serial, game_id, grid) VALUES (?, ?, ?, ?)",
                ("LEGACY01", "serial_legacy_01", "game_abc", json.dumps(sample_grid)),
            )
            conn.execute(
                "INSERT INTO cards (public_id, serial, game_id, grid) VALUES (?, ?, ?, ?)",
                ("LEGACY02", "serial_legacy_02", None, json.dumps(sample_grid)),
            )
            conn.commit()
            conn.close()

            # 2. Configure Alembic to point to this temp DB
            alembic_cfg = Config(os.path.abspath("backend/alembic.ini"))
            alembic_cfg.set_main_option("script_location", os.path.abspath("backend/alembic"))
            # For migration execution, use sqlite:/// URI
            normalized_path = tmp_db_path.replace("\\", "/")
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{normalized_path}")

            # Set environment variable so get_database_url() picks it up in env.py
            os.environ["CARD_DB_PATH"] = tmp_db_path

            # 3. Run upgrade
            command.upgrade(alembic_cfg, "head")

            # 4. Inspect tables and columns using sync engine
            sync_engine = create_engine(f"sqlite:///{normalized_path}")
            inspector = inspect(sync_engine)
            tables = inspector.get_table_names()

            assert "users" in tables
            assert "user_auth_methods" in tables
            assert "user_sessions" in tables
            assert "cards" in tables

            # Verify new columns on cards table
            card_cols = {col["name"]: col for col in inspector.get_columns("cards")}
            assert "public_id" in card_cols
            assert "serial" in card_cols
            assert "game_id" in card_cols
            assert "grid" in card_cols
            assert "owner_id" in card_cols
            assert "is_persistent" in card_cols
            assert "created_at" in card_cols

            # 5. Verify legacy card rows are preserved and intact
            with sync_engine.connect() as check_conn:
                rows = check_conn.execute(text("SELECT public_id, serial, game_id, owner_id FROM cards ORDER BY public_id")).fetchall()
                assert len(rows) == 2
                assert rows[0][0] == "LEGACY01"
                assert rows[0][1] == "serial_legacy_01"
                assert rows[0][2] == "game_abc"
                assert rows[0][3] is None  # owner_id is NULL for legacy unowned cards

                assert rows[1][0] == "LEGACY02"
                assert rows[1][1] == "serial_legacy_02"
                assert rows[1][2] is None
                assert rows[1][3] is None

            sync_engine.dispose()

            # 6. Verify idempotency: running migration again does not error
            command.upgrade(alembic_cfg, "head")

        finally:
            if os.path.exists(tmp_db_path):
                try:
                    os.remove(tmp_db_path)
                except OSError:
                    pass
            os.environ.pop("CARD_DB_PATH", None)
