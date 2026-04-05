"""Redis connection and distributed locking helper.

Provides connection pooling, health checks, and distributed locking primitives
for event processing coordination across multiple middleware instances.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import RedisError, WatchError

logger = logging.getLogger(__name__)


class RedisHelper:
    """Manages Redis connections with pooling, health checks, and locks.

    Attributes:
        _url: Redis connection URL (e.g., redis://localhost:6379).
        _pool: Connection pool for efficient resource management.
        _redis: Redis async client instance.
        _lock_ttl: Lock time-to-live in seconds (default 30s).
        _max_retries: Maximum lock acquisition attempts (default 3).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        lock_ttl: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize Redis helper.

        Args:
            redis_url: Redis connection URL.
            lock_ttl: Lock expiration time in seconds.
            max_retries: Max lock acquisition retries.
        """
        self._url: str = redis_url
        self._pool: ConnectionPool | None = None
        self._redis: redis.Redis | None = None
        self._lock_ttl: int = lock_ttl
        self._max_retries: int = max_retries

    async def connect(self) -> None:
        """Establish Redis connection pool.

        Raises:
            RedisError: If connection to Redis fails.
        """
        try:
            self._pool = ConnectionPool.from_url(self._url)
            self._redis = redis.from_url(self._url)
            await self.health_check()
            logger.info("Redis connection established")
        except RedisError as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Close Redis connection.

        Safely closes the connection pool and async client.
        """
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.disconnect()  # ConnectionPool.disconnect() is async in redis.asyncio
        logger.info("Redis connection closed")

    async def health_check(self) -> bool:
        """Check Redis connectivity.

        Returns:
            True if Redis is responding to PING, False otherwise.
        """
        if not self._redis:
            logger.warning("Redis client not initialized")
            return False

        try:
            result = await self._redis.ping()  # type: ignore[misc]
            logger.debug(f"Redis PING: {result}")
            return bool(result)
        except RedisError as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    @asynccontextmanager
    async def distributed_lock(
        self, key: str, timeout: int = 5
    ) -> AsyncGenerator[bool, None]:
        """Acquire a distributed lock using Redis.

        Context manager that acquires a lock on a key and automatically
        releases it on exit. Implements retry logic with exponential backoff.

        Example:
            async with redis_helper.distributed_lock("device_ip_1.2.3.4"):
                # Safe to process event here (only one instance)
                pass

        Args:
            key: Lock key (typically device IP).
            timeout: Lock acquisition timeout in seconds.

        Yields:
            True if lock acquired, False if timeout.

        Raises:
            RedisError: On Redis connection failure.
        """
        if not self._redis:
            raise RedisError("Redis client not initialized")

        lock_key = f"lock:{key}"
        lock_id = f"{id(asyncio.current_task())}:{key}"  # Unique lock ID
        acquired = False

        try:
            # Try to acquire lock with retries
            for attempt in range(self._max_retries):
                try:
                    acquired = await self._redis.set(  # type: ignore[misc]
                        lock_key,
                        lock_id,
                        ex=self._lock_ttl,
                        nx=True,
                    )
                    if acquired:
                        logger.debug(f"Lock acquired: {lock_key}")
                        yield True
                        return

                    # Wait before retry with exponential backoff
                    backoff = 0.1 * (2 ** attempt)
                    await asyncio.sleep(backoff)

                except RedisError as e:
                    logger.warning(f"Lock acquisition attempt {attempt + 1} failed: {e}")
                    if attempt == self._max_retries - 1:
                        raise

            logger.warning(f"Failed to acquire lock after {self._max_retries} attempts")
            yield False

        finally:
            if acquired:
                try:
                    # Use Lua script for atomic lock release
                    release_script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
                    await self._redis.eval(release_script, 1, lock_key, lock_id)  # type: ignore[misc]
                    logger.debug(f"Lock released: {lock_key}")
                except RedisError as e:
                    logger.error(f"Lock release failed: {e}")

    async def push_queue(self, queue_name: str, data: str) -> int:
        """Push data to Redis list queue.

        Args:
            queue_name: Queue identifier.
            data: JSON-serialized data to push.

        Returns:
            Queue length after push.

        Raises:
            RedisError: On Redis operation failure.
        """
        if not self._redis:
            raise RedisError("Redis client not initialized")

        try:
            length = await self._redis.rpush(queue_name, data)  # type: ignore[misc]
            logger.debug(f"Pushed to queue {queue_name}, length: {length}")
            return length
        except RedisError as e:
            logger.error(f"Queue push failed: {e}")
            raise

    async def pop_queue(self, queue_name: str, timeout: int = 1) -> str | None:
        """Pop data from Redis list queue (blocking).

        Args:
            queue_name: Queue identifier.
            timeout: Blocking timeout in seconds.

        Returns:
            Next queue item or None if empty after timeout.

        Raises:
            RedisError: On Redis operation failure.
        """
        if not self._redis:
            raise RedisError("Redis client not initialized")

        try:
            result = await self._redis.blpop(queue_name, timeout=timeout)  # type: ignore[misc]
            if result:
                _, data = result
                logger.debug(f"Popped from queue {queue_name}")
                return data.decode("utf-8") if isinstance(data, bytes) else data
            return None
        except RedisError as e:
            logger.error(f"Queue pop failed: {e}")
            raise

    async def queue_length(self, queue_name: str) -> int:
        """Get current queue length.

        Args:
            queue_name: Queue identifier.

        Returns:
            Number of items in queue.

        Raises:
            RedisError: On Redis operation failure.
        """
        if not self._redis:
            raise RedisError("Redis client not initialized")

        try:
            length = await self._redis.llen(queue_name)  # type: ignore[misc]
            return length
        except RedisError as e:
            logger.error(f"Queue length check failed: {e}")
            raise

    async def clear_queue(self, queue_name: str) -> int:
        """Clear all items from a queue.

        Args:
            queue_name: Queue identifier.

        Returns:
            Number of items deleted.

        Raises:
            RedisError: On Redis operation failure.
        """
        if not self._redis:
            raise RedisError("Redis client not initialized")

        try:
            deleted = await self._redis.delete(queue_name)  # type: ignore[misc]
            logger.info(f"Queue cleared: {queue_name}, deleted {deleted} keys")
            return deleted
        except RedisError as e:
            logger.error(f"Queue clear failed: {e}")
            raise

    async def set_key(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Set a key-value pair in Redis.

        Args:
            key: Key to set.
            value: Value to store.
            ttl: Optional time-to-live in seconds.

        Returns:
            True if successful.

        Raises:
            RedisError: On Redis operation failure.
        """
        if not self._redis:
            raise RedisError("Redis client not initialized")

        try:
            await self._redis.set(key, value, ex=ttl)  # type: ignore[misc]
            logger.debug(f"Key set: {key}")
            return True
        except RedisError as e:
            logger.error(f"Set key failed: {e}")
            raise

    async def get_key(self, key: str) -> str | None:
        """Get a value from Redis.

        Args:
            key: Key to retrieve.

        Returns:
            Value if exists, None otherwise.

        Raises:
            RedisError: On Redis operation failure.
        """
        if not self._redis:
            raise RedisError("Redis client not initialized")

        try:
            value = await self._redis.get(key)  # type: ignore[misc]
            return value.decode("utf-8") if isinstance(value, bytes) else value
        except RedisError as e:
            logger.error(f"Get key failed: {e}")
            raise
