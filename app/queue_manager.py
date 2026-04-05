"""Queue-based fallback mechanism for event processing resilience.

Implements in-memory queue with optional persistent SQLite backend
to ensure event processing continues when Redis is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QueuedEvent:
    """Represents a single queued event.

    Attributes:
        event_id: Unique event identifier.
        device_ip: Source device IP address.
        event_type: Type of event (e.g., 'access', 'alarm').
        payload: Event data as JSON string.
        queued_at: ISO format timestamp when event was queued.
        retry_count: Number of processing attempts.
    """

    event_id: str
    device_ip: str
    event_type: str
    payload: str
    queued_at: str
    retry_count: int = 0

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> QueuedEvent:
        """Create instance from JSON string."""
        obj = json.loads(data)
        return cls(**obj)


class QueueManager:
    """In-memory queue with persistent SQLite fallback.

    Attributes:
        _queue: In-memory asyncio queue.
        _db_path: Path to SQLite database file.
        _conn: SQLite connection.
        _batch_size: Number of events to process per batch.
        _enable_persistence: Whether to persist queue to SQLite.
    """

    def __init__(
        self,
        db_path: str = "queue.db",
        enable_persistence: bool = True,
        batch_size: int = 10,
    ) -> None:
        """Initialize queue manager.

        Args:
            db_path: Path to SQLite database for persistence.
            enable_persistence: Enable database persistence.
            batch_size: Number of events per processing batch.
        """
        self._queue: asyncio.Queue[QueuedEvent] = asyncio.Queue()
        self._db_path: Path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._enable_persistence: bool = enable_persistence
        self._batch_size: int = batch_size

    async def initialize(self) -> None:
        """Initialize queue database and load persisted events.

        Raises:
            Exception: If database initialization fails.
        """
        if self._enable_persistence:
            self._initialize_db()
            await self._load_persisted_events()
            logger.info(f"Queue manager initialized with database: {self._db_path}")
        else:
            logger.info("Queue manager initialized (in-memory only)")

    def _initialize_db(self) -> None:
        """Create SQLite database and schema."""
        try:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            cursor = self._conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS queued_events (
                    event_id TEXT PRIMARY KEY,
                    device_ip TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._conn.commit()
            logger.debug("Queue database schema initialized")
        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def _load_persisted_events(self) -> None:
        """Load all persisted events from SQLite into memory queue."""
        if not self._conn:
            return

        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT event_id, device_ip, event_type, payload, queued_at, retry_count FROM queued_events"
            )
            rows = cursor.fetchall()

            for row in rows:
                event = QueuedEvent(
                    event_id=row[0],
                    device_ip=row[1],
                    event_type=row[2],
                    payload=row[3],
                    queued_at=row[4],
                    retry_count=row[5],
                )
                await self._queue.put(event)

            logger.info(f"Loaded {len(rows)} persisted events from database")
        except sqlite3.Error as e:
            logger.error(f"Failed to load persisted events: {e}")

    async def enqueue(self, event: QueuedEvent) -> None:
        """Add event to queue.

        Args:
            event: Event to queue.

        Raises:
            Exception: If persistence fails.
        """
        await self._queue.put(event)

        if self._enable_persistence:
            self._persist_event(event)

        logger.debug(f"Event queued: {event.event_id}")

    def _persist_event(self, event: QueuedEvent) -> None:
        """Persist event to SQLite.

        Args:
            event: Event to persist.
        """
        if not self._conn:
            return

        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO queued_events
                (event_id, device_ip, event_type, payload, queued_at, retry_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.device_ip,
                    event.event_type,
                    event.payload,
                    event.queued_at,
                    event.retry_count,
                ),
            )
            self._conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to persist event {event.event_id}: {e}")

    async def dequeue(self, timeout: int = 1) -> QueuedEvent | None:
        """Get next event from queue (blocking with timeout).

        Args:
            timeout: Blocking timeout in seconds.

        Returns:
            Next queued event or None if queue empty after timeout.
        """
        try:
            event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            logger.debug(f"Event dequeued: {event.event_id}")
            return event
        except asyncio.TimeoutError:
            return None

    async def batch_dequeue(self, size: int | None = None) -> list[QueuedEvent]:
        """Get multiple events from queue in a batch.

        Args:
            size: Number of events to retrieve (uses _batch_size if None).

        Returns:
            List of queued events (may be smaller than requested size).
        """
        size = size or self._batch_size
        events: list[QueuedEvent] = []

        for _ in range(size):
            try:
                event = await asyncio.wait_for(
                    self._queue.get(), timeout=0.1
                )
                events.append(event)
            except asyncio.TimeoutError:
                break

        logger.debug(f"Batch dequeued: {len(events)} events")
        return events

    def queue_size(self) -> int:
        """Get current queue size.

        Returns:
            Number of events in queue.
        """
        return self._queue.qsize()

    async def mark_processed(self, event_id: str) -> None:
        """Remove successfully processed event from persistence.

        Args:
            event_id: Event to mark as processed.
        """
        if not self._enable_persistence or not self._conn:
            return

        try:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM queued_events WHERE event_id = ?", (event_id,))
            self._conn.commit()
            logger.debug(f"Event marked processed: {event_id}")
        except sqlite3.Error as e:
            logger.error(f"Failed to mark event processed: {e}")

    async def increment_retry(self, event: QueuedEvent) -> None:
        """Increment retry count and persist.

        Args:
            event: Event to update.
        """
        event.retry_count += 1

        if self._enable_persistence:
            self._persist_event(event)

        logger.debug(f"Event retry count incremented: {event.event_id}")

    async def clear(self) -> int:
        """Clear all queued events (in-memory and persisted).

        Returns:
            Number of events cleared.
        """
        cleared = self._queue.qsize()

        # Clear in-memory queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Clear database
        if self._enable_persistence and self._conn:
            try:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM queued_events")
                self._conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to clear database: {e}")

        logger.info(f"Queue cleared: {cleared} events")
        return cleared

    async def close(self) -> None:
        """Close queue and database connections."""
        if self._conn:
            self._conn.close()
            logger.info("Queue manager closed")

    async def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue stats (size, db_size, etc.).
        """
        stats: dict[str, Any] = {
            "queue_size": self.queue_size(),
            "persistence_enabled": self._enable_persistence,
        }

        if self._enable_persistence and self._conn:
            try:
                cursor = self._conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM queued_events")
                db_count = cursor.fetchone()[0]
                stats["persisted_events"] = db_count
            except sqlite3.Error as e:
                logger.error(f"Failed to get stats: {e}")

        return stats
