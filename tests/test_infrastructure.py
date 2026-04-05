"""Tests for Redis helper and queue manager infrastructure.

Tests cover distributed locking, queue operations, persistence,
and health checks with fallback scenarios.
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.queue_manager import QueueManager, QueuedEvent
from app.redis_helper import RedisHelper


class TestQueuedEvent:
    """Tests for QueuedEvent data class."""

    def test_event_creation(self) -> None:
        """Test creating a QueuedEvent instance."""
        event = QueuedEvent(
            event_id="evt_123",
            device_ip="192.168.1.100",
            event_type="access",
            payload='{"user": "alice"}',
            queued_at="2026-04-05T10:00:00Z",
            retry_count=0,
        )
        assert event.event_id == "evt_123"
        assert event.device_ip == "192.168.1.100"
        assert event.retry_count == 0

    def test_event_to_json(self) -> None:
        """Test serializing event to JSON."""
        event = QueuedEvent(
            event_id="evt_123",
            device_ip="192.168.1.100",
            event_type="access",
            payload='{"user": "alice"}',
            queued_at="2026-04-05T10:00:00Z",
        )
        json_str = event.to_json()
        data = json.loads(json_str)
        assert data["event_id"] == "evt_123"
        assert data["retry_count"] == 0

    def test_event_from_json(self) -> None:
        """Test deserializing event from JSON."""
        json_str = '{"event_id":"evt_456","device_ip":"10.0.0.1","event_type":"alarm","payload":"{\\"code\\":999}","queued_at":"2026-04-05T11:00:00Z","retry_count":2}'
        event = QueuedEvent.from_json(json_str)
        assert event.event_id == "evt_456"
        assert event.retry_count == 2


class TestQueueManager:
    """Tests for QueueManager with persistence."""

    @pytest.fixture
    async def queue_mgr(self, tmp_path):
        """Provide QueueManager instance with temp database."""
        db_path = tmp_path / "test_queue.db"
        mgr = QueueManager(db_path=str(db_path), enable_persistence=True)
        await mgr.initialize()
        yield mgr
        await mgr.close()

    @pytest.mark.asyncio
    async def test_initialization(self, queue_mgr: QueueManager) -> None:
        """Test queue manager initialization."""
        assert queue_mgr.queue_size() == 0
        stats = await queue_mgr.get_stats()
        assert stats["persistence_enabled"] is True
        assert stats["queued_events"] == 0

    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self, queue_mgr: QueueManager) -> None:
        """Test basic enqueue and dequeue operations."""
        event = QueuedEvent(
            event_id="evt_001",
            device_ip="192.168.1.100",
            event_type="access",
            payload='{"user": "bob"}',
            queued_at="2026-04-05T10:00:00Z",
        )
        await queue_mgr.enqueue(event)
        assert queue_mgr.queue_size() == 1

        dequeued = await queue_mgr.dequeue(timeout=1)
        assert dequeued is not None
        assert dequeued.event_id == "evt_001"
        assert dequeued.device_ip == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_batch_dequeue(self, queue_mgr: QueueManager) -> None:
        """Test batch dequeue operation."""
        for i in range(5):
            event = QueuedEvent(
                event_id=f"evt_{i:03d}",
                device_ip=f"192.168.1.{100 + i}",
                event_type="access",
                payload="{}",
                queued_at="2026-04-05T10:00:00Z",
            )
            await queue_mgr.enqueue(event)

        batch = await queue_mgr.batch_dequeue(size=3)
        assert len(batch) == 3
        assert batch[0].event_id == "evt_000"

    @pytest.mark.asyncio
    async def test_mark_processed(self, queue_mgr: QueueManager) -> None:
        """Test marking event as processed (deletion from db)."""
        event = QueuedEvent(
            event_id="evt_delete_me",
            device_ip="192.168.1.100",
            event_type="access",
            payload="{}",
            queued_at="2026-04-05T10:00:00Z",
        )
        await queue_mgr.enqueue(event)
        stats_before = await queue_mgr.get_stats()
        assert stats_before["persisted_events"] == 1

        await queue_mgr.mark_processed("evt_delete_me")
        stats_after = await queue_mgr.get_stats()
        assert stats_after["persisted_events"] == 0

    @pytest.mark.asyncio
    async def test_increment_retry(self, queue_mgr: QueueManager) -> None:
        """Test incrementing retry count."""
        event = QueuedEvent(
            event_id="evt_retry",
            device_ip="192.168.1.100",
            event_type="access",
            payload="{}",
            queued_at="2026-04-05T10:00:00Z",
            retry_count=0,
        )
        await queue_mgr.increment_retry(event)
        assert event.retry_count == 1

        await queue_mgr.increment_retry(event)
        assert event.retry_count == 2

    @pytest.mark.asyncio
    async def test_clear_queue(self, queue_mgr: QueueManager) -> None:
        """Test clearing all queued events."""
        for i in range(3):
            event = QueuedEvent(
                event_id=f"evt_clear_{i}",
                device_ip="192.168.1.100",
                event_type="access",
                payload="{}",
                queued_at="2026-04-05T10:00:00Z",
            )
            await queue_mgr.enqueue(event)

        cleared = await queue_mgr.clear()
        assert cleared == 3
        assert queue_mgr.queue_size() == 0

    @pytest.mark.asyncio
    async def test_dequeue_timeout(self, queue_mgr: QueueManager) -> None:
        """Test dequeue with empty queue returns None after timeout."""
        event = await queue_mgr.dequeue(timeout=1)
        assert event is None


class TestRedisHelper:
    """Tests for RedisHelper distributed locking and queue operations."""

    @pytest.fixture
    async def redis_helper(self) -> RedisHelper:
        """Provide RedisHelper instance (mocked for testing)."""
        helper = RedisHelper(
            redis_url="redis://localhost:6379", lock_ttl=30, max_retries=3
        )
        # Mock the redis connection
        helper._redis = AsyncMock()  # type: ignore[assignment]
        return helper

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test initialization with default parameters."""
        helper = RedisHelper()
        assert helper._lock_ttl == 30
        assert helper._max_retries == 3
        assert helper._url == "redis://localhost:6379"

    @pytest.mark.asyncio
    async def test_health_check_failure(self, redis_helper: RedisHelper) -> None:
        """Test health check when Redis client not initialized."""
        helper = RedisHelper()
        result = await helper.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_push_queue(self, redis_helper: RedisHelper) -> None:
        """Test pushing data to queue."""
        redis_helper._redis.rpush = AsyncMock(return_value=1)  # type: ignore[attr-defined]
        length = await redis_helper.push_queue("test_queue", "data")
        assert length == 1
        redis_helper._redis.rpush.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_pop_queue(self, redis_helper: RedisHelper) -> None:
        """Test popping data from queue."""
        redis_helper._redis.blpop = AsyncMock(return_value=(b"queue", b"test_data"))  # type: ignore[attr-defined]
        data = await redis_helper.pop_queue("test_queue", timeout=1)
        assert data == "test_data"

    @pytest.mark.asyncio
    async def test_pop_queue_empty(self, redis_helper: RedisHelper) -> None:
        """Test popping from empty queue returns None."""
        redis_helper._redis.blpop = AsyncMock(return_value=None)  # type: ignore[attr-defined]
        data = await redis_helper.pop_queue("test_queue", timeout=1)
        assert data is None

    @pytest.mark.asyncio
    async def test_set_key(self, redis_helper: RedisHelper) -> None:
        """Test setting a key-value pair."""
        redis_helper._redis.set = AsyncMock(return_value=True)  # type: ignore[attr-defined]
        result = await redis_helper.set_key("test_key", "test_value", ttl=60)
        assert result is True
        redis_helper._redis.set.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_get_key(self, redis_helper: RedisHelper) -> None:
        """Test getting a value from Redis."""
        redis_helper._redis.get = AsyncMock(return_value=b"test_value")  # type: ignore[attr-defined]
        value = await redis_helper.get_key("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_queue_length(self, redis_helper: RedisHelper) -> None:
        """Test getting queue length."""
        redis_helper._redis.llen = AsyncMock(return_value=5)  # type: ignore[attr-defined]
        length = await redis_helper.queue_length("test_queue")
        assert length == 5

    @pytest.mark.asyncio
    async def test_clear_queue(self, redis_helper: RedisHelper) -> None:
        """Test clearing a queue."""
        redis_helper._redis.delete = AsyncMock(return_value=5)  # type: ignore[attr-defined]
        deleted = await redis_helper.clear_queue("test_queue")
        assert deleted == 5

    @pytest.mark.asyncio
    async def test_distributed_lock_not_initialized(self) -> None:
        """Test lock acquisition fails when Redis not initialized."""
        helper = RedisHelper()
        with pytest.raises(Exception):
            async with helper.distributed_lock("test_key"):
                pass

    @pytest.mark.asyncio
    async def test_distributed_lock_success(self, redis_helper: RedisHelper) -> None:
        """Test successful lock acquisition and release."""
        redis_helper._redis.set = AsyncMock(return_value=True)  # type: ignore[attr-defined]
        redis_helper._redis.eval = AsyncMock(return_value=1)  # type: ignore[attr-defined]

        async with redis_helper.distributed_lock("device_1.2.3.4") as acquired:
            assert acquired is True

        redis_helper._redis.eval.assert_called_once()  # type: ignore[attr-defined]
