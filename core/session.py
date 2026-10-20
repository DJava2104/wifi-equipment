import json
import uuid

from redis.asyncio import Redis

from core.config import settings

redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)


async def create_session(user_id: int, username: str) -> str:
    session_id = uuid.uuid4().hex
    payload = json.dumps({"id_user": user_id, "username": username}, ensure_ascii=False)
    await redis_client.setex(f"session:{session_id}", settings.SESSION_TTL, payload)
    return session_id


async def get_session(session_id: str) -> dict | None:
    raw = await redis_client.get(f"session:{session_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def destroy_session(session_id: str) -> None:
    await redis_client.delete(f"session:{session_id}")
