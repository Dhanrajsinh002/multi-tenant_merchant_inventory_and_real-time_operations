import asyncio
import time
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db, get_redis
from app.core.config import settings
from app.db.base import Base
from app.main import app as fastapi_app
import app.models  # noqa: F401


# In-memory Redis mock for ultra-reliable test execution without external daemon dependency
class MockRedisPipeline:
    def __init__(self, mock_redis):
        self.mock = mock_redis
        self.ops = []

    def zremrangebyscore(self, key, min_score, max_score):
        self.ops.append(("zrem", key, min_score, max_score))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, seconds):
        self.ops.append(("expire", key, seconds))
        return self

    async def execute(self):
        results = []
        for op in self.ops:
            if op[0] == "zrem":
                key, min_s, max_s = op[1], op[2], op[3]
                if key in self.mock.zsets:
                    self.mock.zsets[key] = [(m, s) for m, s in self.mock.zsets[key] if not (min_s <= s <= max_s)]
                results.append(0)
            elif op[0] == "zcard":
                key = op[1]
                results.append(len(self.mock.zsets.get(key, [])))
            elif op[0] == "zadd":
                key, mapping = op[1], op[2]
                if key not in self.mock.zsets:
                    self.mock.zsets[key] = []
                for m, s in mapping.items():
                    self.mock.zsets[key].append((m, s))
                results.append(len(mapping))
            elif op[0] == "expire":
                results.append(True)
        self.ops = []
        return results


class MockRedis:
    def __init__(self):
        self.data = {}
        self.zsets = {}

    def pipeline(self, transaction=True):
        return MockRedisPipeline(self)

    async def get(self, key: str):
        return self.data.get(key)

    async def setex(self, key: str, seconds: int, value: str):
        self.data[key] = value
        return True

    async def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self.data:
                del self.data[k]
                count += 1
            if k in self.zsets:
                del self.zsets[k]
                count += 1
        return count

    async def ping(self):
        return True

    async def close(self):
        pass


import os

# Use an isolated SQLite test database so tests run anywhere with zero configuration
TEST_DB_FILE = "./test_cleandesk.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
mock_redis_client = MockRedis()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create tables before tests and teardown after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass



@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with overridden DB and Redis dependencies."""
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    async def override_get_redis():
        return mock_redis_client

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()