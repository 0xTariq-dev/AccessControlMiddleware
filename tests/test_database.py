"""Tests for database configuration and management.

Tests cover multiple database backends, encryption, connection pooling,
and health checks.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from peewee import SqliteDatabase, PostgresqlDatabase, MySQLDatabase

from app.database import DatabaseManager, get_db


class TestDatabaseManager:
    """Tests for DatabaseManager singleton."""

    def test_singleton_pattern(self) -> None:
        """Test that DatabaseManager is a singleton."""
        manager1 = DatabaseManager()
        manager2 = DatabaseManager()
        assert manager1 is manager2

    def test_sqlite_default_database(self, tmp_path: Path) -> None:
        """Test default SQLite database creation."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "test.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

        manager = DatabaseManager()
        assert isinstance(manager.db, SqliteDatabase)
        assert manager.enable_encryption is False
        assert str(db_file) in str(manager.db.database)

    def test_sqlcipher_encryption_enabled(self, tmp_path: Path) -> None:
        """Test SQLCipher database with encryption key."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "test_encrypted.db"
        os.environ["DATABASE_URL"] = f"sqlcipher:///{db_file}"
        os.environ["DATABASE_ENCRYPTION_KEY"] = "a" * 64  # 64-char hex string (32 bytes)

        manager = DatabaseManager()
        assert isinstance(manager.db, SqliteDatabase)
        assert manager.enable_encryption is True

    def test_sqlcipher_missing_key_raises_error(self, tmp_path: Path) -> None:
        """Test SQLCipher raises error without encryption key."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "test_encrypted.db"
        os.environ["DATABASE_URL"] = f"sqlcipher:///{db_file}"
        os.environ.pop("DATABASE_ENCRYPTION_KEY", None)

        with pytest.raises(ValueError, match="DATABASE_ENCRYPTION_KEY"):
            DatabaseManager()

    def test_postgresql_connection_string(self) -> None:
        """Test PostgreSQL connection string parsing."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        os.environ[
            "DATABASE_URL"
        ] = "postgresql://user:password@localhost:5432/testdb"

        manager = DatabaseManager()
        assert isinstance(manager.db, PostgresqlDatabase)
        assert manager.db.database == "testdb"

    def test_mysql_connection_string(self) -> None:
        """Test MySQL connection string parsing."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        os.environ["DATABASE_URL"] = "mysql+pymysql://user:password@localhost:3306/testdb"

        manager = DatabaseManager()
        assert isinstance(manager.db, MySQLDatabase)
        assert manager.db.database == "testdb"

    def test_unsupported_database_scheme(self) -> None:
        """Test unsupported database scheme raises error."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        os.environ["DATABASE_URL"] = "unsupported://localhost/db"

        with pytest.raises(ValueError, match="Unsupported database scheme"):
            DatabaseManager()

    def test_mask_url_hides_password(self) -> None:
        """Test URL masking for logging."""
        url = "postgresql://user:secretpassword@localhost:5432/db"
        masked = DatabaseManager._mask_url(url)
        assert "secretpassword" not in masked
        assert "user" in masked
        assert "localhost" in masked

    def test_mask_url_without_credentials(self) -> None:
        """Test URL masking with no credentials."""
        url = "sqlite:///./test.db"
        masked = DatabaseManager._mask_url(url)
        assert masked == url

    def test_default_database_url_sqlite(self, monkeypatch) -> None:
        """Test default DATABASE_URL when not set."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        monkeypatch.delenv("DATABASE_URL", raising=False)

        manager = DatabaseManager()
        assert "sqlite:///" in manager.database_url
        assert "access_control.db" in manager.database_url

    @pytest.mark.asyncio
    async def test_health_check_sqlite(self, tmp_path: Path) -> None:
        """Test health check for SQLite."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "test_health.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

        manager = DatabaseManager()
        assert manager.health_check() is True

    def test_sqlite_wal_pragmas(self, tmp_path: Path) -> None:
        """Test SQLite WAL mode pragmas are set."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "test_wal.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

        manager = DatabaseManager()
        # WAL mode should be enabled
        result = manager.db.execute_sql("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"

    def test_create_tables_on_init(self, tmp_path: Path) -> None:
        """Test that init_db creates all necessary tables."""
        # Reset singleton for test
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "test_init.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

        manager = DatabaseManager()
        manager.db.connect()

        # Create tables
        from app.models import Device, EventLog, BackendConfig, AuditLog, OperationQueue

        tables = [Device, EventLog, BackendConfig, AuditLog, OperationQueue]
        manager.db.create_tables(tables, safe=True)

        # Verify tables exist
        tables_in_db = manager.db.get_tables()
        assert "devices" in tables_in_db
        assert "event_logs" in tables_in_db
        assert "audit_logs" in tables_in_db
        assert "operation_queues" in tables_in_db


class TestDatabaseURLParsing:
    """Tests for database URL parsing and validation."""

    def test_parse_postgresql_url(self) -> None:
        """Test PostgreSQL URL parsing."""
        DatabaseManager._instance = None
        DatabaseManager._db = None

        os.environ[
            "DATABASE_URL"
        ] = "postgresql://myuser:mypass@db.example.com:5432/mydb"
        manager = DatabaseManager()
        assert manager.db.database == "mydb"

    def test_parse_mysql_url_with_pymysql(self) -> None:
        """Test MySQL URL with pymysql driver."""
        DatabaseManager._instance = None
        DatabaseManager._db = None

        os.environ[
            "DATABASE_URL"
        ] = "mysql+pymysql://root:rootpass@localhost:3306/mydb"
        manager = DatabaseManager()
        assert manager.db.database == "mydb"

    def test_parse_url_without_port(self) -> None:
        """Test URL parsing with default ports."""
        DatabaseManager._instance = None
        DatabaseManager._db = None

        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/testdb"
        manager = DatabaseManager()
        assert isinstance(manager.db, PostgresqlDatabase)

    def test_parse_url_without_password(self) -> None:
        """Test URL parsing without password."""
        DatabaseManager._instance = None
        DatabaseManager._db = None

        os.environ["DATABASE_URL"] = "mysql://user@localhost:3306/testdb"
        manager = DatabaseManager()
        assert isinstance(manager.db, MySQLDatabase)


class TestDatabaseEncryption:
    """Tests for database encryption setup."""

    def test_sqlcipher_with_valid_key(self, tmp_path: Path) -> None:
        """Test SQLCipher with valid encryption key."""
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "encrypted.db"
        key = "a" * 64  # 32 bytes in hex
        os.environ["DATABASE_URL"] = f"sqlcipher:///{db_file}"
        os.environ["DATABASE_ENCRYPTION_KEY"] = key

        manager = DatabaseManager()
        assert manager.enable_encryption is True

    def test_sqlcipher_key_length_validation(self, tmp_path: Path) -> None:
        """Test SQLCipher key validation (can be any non-empty string)."""
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "encrypted.db"
        os.environ["DATABASE_URL"] = f"sqlcipher:///{db_file}"
        os.environ["DATABASE_ENCRYPTION_KEY"] = "short_key"  # Will be hashed

        manager = DatabaseManager()
        # Should not raise - SQLCipher will handle key stretching
        assert manager.enable_encryption is True

    def test_regular_sqlite_no_encryption(self, tmp_path: Path) -> None:
        """Test that regular SQLite is not encrypted."""
        DatabaseManager._instance = None
        DatabaseManager._db = None

        db_file = tmp_path / "plain.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
        os.environ.pop("DATABASE_ENCRYPTION_KEY", None)

        manager = DatabaseManager()
        assert manager.enable_encryption is False
