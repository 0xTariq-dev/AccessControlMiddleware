"""
CLI interface for database migration management.

Provides commands for running, rolling back, and inspecting database migrations.
Supports multi-backend databases (SQLite, PostgreSQL, MySQL) via peewee-migrate Router.

Usage:
    python -m app.cli migrate      # Run pending migrations
    python -m app.cli rollback     # Revert to previous migration
    python -m app.cli status       # Show migration history
    
    # Docker integration:
    docker-compose run migration migrate
    docker-compose run --profile tools migration migrate
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from peewee_migrate import Router

from app.database import get_db


def get_router() -> Router:
    """
    Initialize and return peewee-migrate Router instance.
    
    Returns:
        Router: Configured Router for the active database
        
    Raises:
        RuntimeError: If database initialization fails
    """
    try:
        db = get_db()
        migrations_dir = Path(__file__).parent.parent / "migrations"
        return Router(db, migrate_dir=str(migrations_dir))
    except Exception as e:
        click.echo(f"Error initializing database: {e}", err=True)
        sys.exit(1)


@click.group()
@click.version_option(version="1.0.0")
def cli() -> None:
    """
    Database Migration CLI
    
    Manage database schema migrations for multi-backend support.
    Supports: SQLite, PostgreSQL, MySQL
    """
    pass


@cli.command()
@click.option(
    "--name",
    default=None,
    help="Migration name (optional; runs all pending if not specified)",
)
@click.option(
    "--fake",
    is_flag=True,
    help="Mark migration as executed without running it (use with caution)",
)
def migrate(name: Optional[str], fake: bool) -> None:
    """
    Run pending database migrations.
    
    Idempotent: Safe to run multiple times. Only applies unapplied migrations.
    
    Examples:
        python -m app.cli migrate                  # Run all pending migrations
        python -m app.cli migrate --name 001_init  # Run specific migration
        python -m app.cli migrate --fake           # Mark as applied without executing
    """
    try:
        router = get_router()
        click.echo("Running database migrations...")
        
        if fake:
            click.echo("⚠️  Fake mode: marking migrations as applied without execution")
        
        if name:
            # Run specific migration
            click.echo(f"Running migration: {name}")
            router.run(name, fake=fake)
            click.echo(f"✅ Migration '{name}' applied successfully")
        else:
            # Run all pending migrations (idempotent)
            click.echo("Executing all pending migrations...")
            applied = router.run(fake=fake)
            
            if applied:
                click.echo(f"✅ Successfully applied {len(applied)} migration(s):")
                for m in applied:
                    click.echo(f"   • {m}")
            else:
                click.echo("ℹ️  No pending migrations to apply")
        
        click.echo("Migration complete!")
        
    except Exception as e:
        click.echo(f"❌ Migration failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--steps",
    type=int,
    default=1,
    help="Number of migrations to rollback",
)
def rollback(steps: int) -> None:
    """
    Rollback database migrations.
    
    Reverts the specified number of migrations in reverse order.
    All migrations are reversible (contain rollback() function).
    
    Examples:
        python -m app.cli rollback           # Rollback 1 migration
        python -m app.cli rollback --steps 3 # Rollback 3 migrations
    """
    try:
        if steps < 1:
            click.echo("Error: --steps must be >= 1", err=True)
            sys.exit(1)
        
        router = get_router()
        click.echo(f"Rolling back {steps} migration(s)...")
        
        # Get migration history to show what we're rolling back
        history = router.done
        if not history or not router.done:
            click.echo("ℹ️  No migrations to rollback")
            return
        
        # Rollback step by step
        for i in range(steps):
            click.echo(f"[{i + 1}/{steps}] Rolling back...")
            try:
                router.rollback()
                click.echo(f"✅ Rollback step {i + 1} complete")
            except Exception as e:
                click.echo(f"⚠️  Rollback step {i + 1} encountered: {e}", err=True)
                if i > 0:
                    click.echo(f"Partially rolled back {i} migration(s)")
                sys.exit(1)
        
        click.echo(f"✅ Successfully rolled back {steps} migration(s)")
        
    except Exception as e:
        click.echo(f"❌ Rollback failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def status() -> None:
    """
    Display migration status and history.
    
    Shows:
    - Current database state
    - Applied migrations with timestamps
    - Pending migrations (if any)
    - Migration directory location
    """
    try:
        router = get_router()
        
        click.echo("\n" + "=" * 60)
        click.echo("DATABASE MIGRATION STATUS")
        click.echo("=" * 60)
        
        # Database info
        db = get_db()
        click.echo(f"\n📊 Database Info:")
        click.echo(f"   Database URL: {os.getenv('DATABASE_URL', 'sqlite:///./access_control.db')}")
        click.echo(f"   Database Type: {os.getenv('DATABASE_TYPE', 'sqlite')}")
        click.echo(f"   Migrations Dir: {Path(__file__).parent.parent / 'migrations'}")
        
        # Available migrations
        available = router.todo + router.done
        applied = router.done
        pending = router.todo
        
        click.echo(f"\n📋 Migration Summary:")
        click.echo(f"   Total Available: {len(available)}")
        click.echo(f"   Applied: {len(applied)}")
        click.echo(f"   Pending: {len(pending)}")
        
        # Applied migrations
        if applied:
            click.echo(f"\n✅ Applied Migrations ({len(applied)}):")
            for m in applied:
                click.echo(f"   • {m}")
        
        # Pending migrations
        if pending:
            click.echo(f"\n⏳ Pending Migrations ({len(pending)}):")
            for m in pending:
                click.echo(f"   • {m}")
        else:
            click.echo(f"\n✅ All migrations applied - database is up to date")
        
        click.echo("\n" + "=" * 60 + "\n")
        
    except Exception as e:
        click.echo(f"❌ Status check failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def init() -> None:
    """
    Initialize migrations directory and create initial migration template.
    
    Creates:
    - migrations/ directory (if not exists)
    - __init__.py in migrations/
    - First migration file template
    
    Safe to run multiple times (idempotent).
    """
    try:
        migrations_dir = Path(__file__).parent.parent / "migrations"
        migrations_dir.mkdir(exist_ok=True)
        
        # Create __init__.py
        init_file = migrations_dir / "__init__.py"
        init_file.touch()
        
        click.echo("✅ Migrations directory initialized")
        click.echo(f"   Location: {migrations_dir}")
        click.echo("\nRun 'python -m app.cli migrate' to execute pending migrations")
        
    except Exception as e:
        click.echo(f"❌ Initialization failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--name",
    required=True,
    prompt="Migration name",
    help="Name of the new migration (e.g., 'add_device_column')",
)
def create(name: str) -> None:
    """
    Create a new migration skeleton.
    
    Generates a new migration file with migrate() and rollback() stubs.
    
    Example:
        python -m app.cli create --name add_device_column
    """
    try:
        if not name or not name.replace("_", "").replace("-", "").isalnum():
            click.echo("Error: Migration name must be alphanumeric with underscores/hyphens", err=True)
            sys.exit(1)
        
        router = get_router()
        router.create(name)
        
        # Find the created migration file
        migrations_dir = Path(__file__).parent.parent / "migrations"
        latest = max(migrations_dir.glob("*.py"), key=os.path.getctime)
        
        click.echo(f"✅ Migration created: {latest.name}")
        click.echo(f"\nEdit the file to add your schema changes:")
        click.echo(f"   Location: {latest}")
        click.echo(f"\nThen run: python -m app.cli migrate")
        
    except Exception as e:
        click.echo(f"❌ Migration creation failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
