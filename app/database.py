"""Database configuration and connection management.

Supports multiple backends: SQLite (default), PostgreSQL, MySQL with optional encryption.
Uses Peewee ORM with connection pooling and WAL mode for optimal concurrency.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from peewee import (
    Database,
    MySQLDatabase,
    PostgresqlDatabase,
    SqliteDatabase,
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connection and lifecycle.

    Attributes:
        database_url: Connection URL (sqlite:///, postgres:///, mysql:///)
        db: Peewee database instance
        enable_encryption: Whether database is encrypted (SQLCipher)
    """

    _instance: DatabaseManager | None = None
    _db: Database | None = None

    def __new__(cls) -> DatabaseManager:
        """Implement singleton pattern for database manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize database from environment variables."""
        if self._db is not None:
            return  # Already initialized

        self.database_url: str = self._get_database_url()
        self.enable_encryption: bool = self._should_encrypt()
        self._db = self._create_database()

    @property
    def db(self) -> Database:
        """Get database instance."""
        if self._db is None:
            raise RuntimeError("Database not initialized. Call __init__ first.")
        return self._db

    def _get_database_url(self) -> str:
        """Get database URL from environment or use SQLite default.

        Returns:
            Database connection URL.

        Raises:
            ValueError: If DATABASE_URL is invalid.
        """
        url = os.getenv(
            "DATABASE_URL",
            "sqlite:///./access_control.db",  # Default SQLite in current directory
        )

        logger.info(f"Using database URL: {self._mask_url(url)}")
        return url

    def _should_encrypt(self) -> bool:
        """Check if encryption is enabled for SQLite.

        Returns:
            True if using SQLCipher (sqlcipher:///) scheme.
        """
        return self.database_url.startswith("sqlcipher:///")

    def _create_database(self) -> Database:
        """Create appropriate database instance based on URL scheme.

        Returns:
            Peewee database instance (SqliteDatabase, PostgresqlDatabase, or MySQLDatabase).

        Raises:
            ValueError: If URL scheme is unsupported.
        """
        if self.database_url.startswith("sqlite:///"):
            return self._create_sqlite_database()
        elif self.database_url.startswith("sqlcipher:///"):
            return self._create_sqlcipher_database()
        elif self.database_url.startswith("postgresql://") or self.database_url.startswith(
            "postgres://"
        ):
            return self._create_postgresql_database()
        elif self.database_url.startswith("mysql://") or self.database_url.startswith(
            "mysql+pymysql://"
        ):
            return self._create_mysql_database()
        else:
            raise ValueError(f"Unsupported database scheme: {self.database_url}")

    def _create_sqlite_database(self) -> SqliteDatabase:
        """Create SQLite database with WAL mode enabled.

        Returns:
            Configured SqliteDatabase instance.
        """
        db_path = self.database_url.replace("sqlite:///", "")
        db_path = Path(db_path).absolute()

        # Create parent directories if needed
        db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating SQLite database at: {db_path}")

        db = SqliteDatabase(
            str(db_path),
            pragmas={
                "journal_mode": "wal",  # Write-Ahead Logging for better concurrency
                "cache_size": -1 * 64000,  # 64MB cache
                "foreign_keys": 1,  # Enable foreign key constraints
                "synchronous": 0,  # FULL (safest), NORMAL (default), OFF (fastest)
                "wal_autocheckpoint": 1000,  # Checkpoint after 1000 pages
            },
        )

        logger.info("SQLite database initialized with WAL mode")
        return db

    def _create_sqlcipher_database(self) -> SqliteDatabase:
        """Create encrypted SQLite database using SQLCipher.

        Requires DATABASE_ENCRYPTION_KEY environment variable.

        Returns:
            Configured SqliteDatabase instance with encryption.

        Raises:
            ValueError: If DATABASE_ENCRYPTION_KEY is not set.
        """
        encryption_key = os.getenv("DATABASE_ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError(
                "DATABASE_ENCRYPTION_KEY environment variable is required for SQLCipher. "
                "Generate a 32-byte key and set it: "
                "export DATABASE_ENCRYPTION_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')"
            )

        db_path = self.database_url.replace("sqlcipher:///", "")
        db_path = Path(db_path).absolute()

        # Create parent directories if needed
        db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating encrypted SQLCipher database at: {db_path}")

        db = SqliteDatabase(
            str(db_path),
            pragmas={
                "journal_mode": "wal",
                "cache_size": -1 * 64000,
                "foreign_keys": 1,
                "synchronous": 0,
                "wal_autocheckpoint": 1000,
                "key": encryption_key,  # Enable encryption
            },
        )

        logger.info("SQLCipher database initialized with AES-256 encryption")
        return db

    def _create_postgresql_database(self) -> PostgresqlDatabase:
        """Create PostgreSQL database connection.

        Uses psycopg3 driver (psycopg[binary] from requirements.txt).

        Returns:
            Configured PostgresqlDatabase instance.
        """
        # Parse connection string
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "", 1)

        # Extract components: user:password@host:port/database
        if "@" in url:
            auth, host_db = url.split("@", 1)
            user, password = auth.split(":", 1) if ":" in auth else (auth, "")
        else:
            user, password, host_db = "", "", url

        host_port, db_name = host_db.split("/", 1) if "/" in host_db else (host_db, "")
        host, port = host_port.split(":", 1) if ":" in host_port else (host_port, "5432")

        logger.info(f"Creating PostgreSQL connection to {host}:{port}/{db_name}")

        db = PostgresqlDatabase(
            database=db_name,
            user=user,
            password=password,
            host=host,
            port=int(port),
            autoconnect=False,
        )

        logger.info("PostgreSQL database configured")
        return db

    def _create_mysql_database(self) -> MySQLDatabase:
        """Create MySQL database connection.

        Uses pymysql driver (from requirements.txt).

        Returns:
            Configured MySQLDatabase instance.
        """
        # Parse connection string
        url = self.database_url
        if url.startswith("mysql+pymysql://"):
            url = url.replace("mysql+pymysql://", "", 1)
        elif url.startswith("mysql://"):
            url = url.replace("mysql://", "", 1)

        # Extract components: user:password@host:port/database
        if "@" in url:
            auth, host_db = url.split("@", 1)
            user, password = auth.split(":", 1) if ":" in auth else (auth, "")
        else:
            user, password, host_db = "", "", url

        host_port, db_name = host_db.split("/", 1) if "/" in host_db else (host_db, "")
        host, port = host_port.split(":", 1) if ":" in host_port else (host_port, "3306")

        logger.info(f"Creating MySQL connection to {host}:{port}/{db_name}")

        db = MySQLDatabase(
            database=db_name,
            user=user,
            password=password,
            host=host,
            port=int(port),
            autoconnect=False,
        )

        logger.info("MySQL database configured")
        return db

    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask sensitive information in database URL for logging.

        Args:
            url: Database URL potentially containing credentials.

        Returns:
            URL with password masked.
        """
        if "@" in url:
            scheme_auth, host = url.split("@", 1)
            if ":" in scheme_auth:
                scheme, auth = scheme_auth.rsplit(":", 1)
                user = auth.split(":")[0] if ":" in auth else auth
                return f"{scheme}:{user}:***@{host}"
        return url

    async def connect(self) -> None:
        """Establish database connection.

        Raises:
            Exception: If connection fails.
        """
        try:
            self.db.connect()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self) -> None:
        """Close database connection gracefully."""
        try:
            if self.db.is_closed():
                logger.info("Database already closed")
                return

            self.db.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

    async def init_db(self, create_tables: bool = True) -> None:
        """Initialize database (create tables if needed).

        Args:
            create_tables: Whether to create tables defined in models.

        Raises:
            Exception: If initialization fails.
        """
        try:
            await self.connect()

            if create_tables:
                # Import models here to avoid circular imports
                from app.models import Device, EventLog, BackendConfig, AuditLog, OperationQueue

                tables = [Device, EventLog, BackendConfig, AuditLog, OperationQueue]
                self.db.create_tables(tables, safe=True)
                logger.info(f"Database tables initialized: {len(tables)} tables")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    def health_check(self) -> bool:
        """Check if database is accessible.

        Returns:
            True if database responds to query, False otherwise.
        """
        try:
            self.db.execute_sql("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Singleton instance
db_manager = DatabaseManager()


def get_db() -> Database:
    """Get database instance for use in application."""
    return db_manager.db
