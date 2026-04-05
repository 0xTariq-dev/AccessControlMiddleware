"""
Database encryption support for multi-database middleware.

Provides unified encryption across SQLite (via SQLCipher) and PostgreSQL
with transparent encryption-at-rest for sensitive data.
"""

import os
from typing import Literal, Optional
from pathlib import Path

from peewee import PostgresqlDatabase
from playhouse.sqlcipher_ext import SqlCipherDatabase


DatabaseType = Literal['sqlite', 'postgresql']


class DatabaseFactory:
    """Factory for creating database instances with appropriate encryption."""

    @staticmethod
    def create_database(
        db_type: Optional[DatabaseType] = None,
        sqlite_path: Optional[str] = None,
        sqlite_passphrase: Optional[str] = None,
        kdf_iterations: int = 64000,
    ) -> SqlCipherDatabase | PostgresqlDatabase:
        """
        Create a database instance based on configuration.

        For SQLite: Uses SQLCipher for transparent AES-256 encryption.
        For PostgreSQL: Uses SSL/TLS connection encryption.

        Args:
            db_type: Database type ('sqlite' or 'postgresql'). If None,
                     reads from DATABASE_TYPE environment variable.
            sqlite_path: Path to SQLite database file. Defaults to 'data.db'.
            sqlite_passphrase: Encryption passphrase for SQLite. If None,
                              reads from DB_PASSPHRASE environment variable.
            kdf_iterations: PBKDF2 iterations for key derivation (default: 64000).
                           Higher = more secure but slower startup.

        Returns:
            Initialized database instance (SqlCipherDatabase or PostgresqlDatabase).

        Raises:
            ValueError: If required environment variables are missing or invalid.

        Example:
            >>> # SQLite with encryption
            >>> db = DatabaseFactory.create_database(
            ...     db_type='sqlite',
            ...     sqlite_path='access_control.db',
            ...     sqlite_passphrase='my-secure-passphrase'
            ... )
            >>> # Or use environment variables
            >>> db = DatabaseFactory.create_database()  # Reads from ENV
        """
        # Get db_type from parameter or environment, normalize to lowercase
        db_type_str = (db_type or os.getenv('DATABASE_TYPE', 'sqlite')).lower()
        
        # Validate and narrow type to DatabaseType Literal
        if db_type_str not in ('sqlite', 'postgresql'):
            raise ValueError(f"Unsupported database type: {db_type_str}")
        
        # Type is now narrowed to Literal['sqlite', 'postgresql']
        db_type_narrowed: DatabaseType = db_type_str  # type: ignore[assignment]

        if db_type_narrowed == 'sqlite':
            return DatabaseFactory._create_sqlite_db(
                sqlite_path or os.getenv('DB_PATH', 'data.db'),
                sqlite_passphrase or os.getenv('DB_PASSPHRASE'),
                kdf_iterations,
            )
        elif db_type_narrowed == 'postgresql':
            return DatabaseFactory._create_postgresql_db()
        else:
            # Unreachable, but satisfies exhaustiveness check
            raise ValueError(f"Unsupported database type: {db_type_narrowed}")

    @staticmethod
    def _create_sqlite_db(
        db_path: str,
        passphrase: Optional[str],
        kdf_iterations: int,
    ) -> SqlCipherDatabase:
        """
        Create encrypted SQLite database via SQLCipher.

        Args:
            db_path: Path to database file.
            passphrase: Encryption passphrase. Required unless DB is unencrypted.
            kdf_iterations: PBKDF2 iterations (security vs. performance trade-off).

        Returns:
            Initialized SqlCipherDatabase instance.

        Raises:
            ValueError: If passphrase is missing or too weak.

        Security Considerations:
            - Passphrase should be 32+ characters for production
            - Use environment variables or secure vaults, not hardcoded values
            - kdf_iterations=64000 is recommended for security/performance balance
        """
        if not passphrase:
            raise ValueError(
                'DB_PASSPHRASE environment variable or passphrase parameter required '
                'for SQLCipher encryption'
            )

        if len(passphrase) < 16:
            raise ValueError(
                'Passphrase must be at least 16 characters. '
                'Use 32+ characters for production environments.'
            )

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create encrypted database
        db = SqlCipherDatabase(
            db_path,
            passphrase=passphrase,
            kdf_iter=kdf_iterations,
            # Additional SQLite pragmas for performance and concurrency
            pragmas={
                'journal_mode': 'wal',  # Write-Ahead Logging for concurrent access
                'cache_size': -64000,   # 64MB cache
                'foreign_keys': 1,      # Enforce foreign key constraints
                'synchronous': 'normal',  # Balance safety and performance
            },
        )

        return db

    @staticmethod
    def _create_postgresql_db() -> PostgresqlDatabase:
        """
        Create PostgreSQL database with SSL/TLS connection encryption.

        Environment variables:
            - POSTGRES_DB: Database name (required)
            - POSTGRES_USER: Database user (required)
            - POSTGRES_PASSWORD: Password (required)
            - POSTGRES_HOST: Host (default: localhost)
            - POSTGRES_PORT: Port (default: 5432)
            - POSTGRES_SSL_MODE: SSL mode (default: require)

        Returns:
            Initialized PostgresqlDatabase instance.

        Raises:
            ValueError: If required environment variables are missing.

        Note:
            PostgreSQL provides server-side encryption at rest via
            pgcrypto extension. Application can use pgp_sym_encrypt
            for column-level encryption if needed.
        """
        required_vars = ['POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(
                f'Missing required PostgreSQL environment variables: '
                f'{", ".join(missing_vars)}'
            )

        ssl_mode = os.getenv('POSTGRES_SSL_MODE', 'require')
        if ssl_mode not in ('disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full'):
            raise ValueError(f'Invalid POSTGRES_SSL_MODE: {ssl_mode}')

        db = PostgresqlDatabase(
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            sslmode=ssl_mode,
        )

        return db


def get_database() -> SqlCipherDatabase | PostgresqlDatabase:
    """
    Get configured database instance.

    Convenience function that reads environment configuration and
    returns appropriate database instance.

    Returns:
        Initialized database instance.

    Example:
        >>> from app.database_encryption import get_database
        >>> db = get_database()
        >>> # Use with Peewee models
    """
    return DatabaseFactory.create_database()
