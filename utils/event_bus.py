import asyncio
import time
from typing import AsyncIterator, Dict, Optional
from loguru import logger
EVENT_TYPES = frozenset({'intent_detected', 'plan_ready', 'step_start', 'step_complete', 'tool_call', 'tool_result', 'token', 'evaluation_done', 'retry', 'done', 'error', 'fatal_error'})

class AgentEventBus:

    def __init__(self, max_queue_size: int=500):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._max_queue_size = max_queue_size
        self._lock = asyncio.Lock()

    async def _get_or_create_queue(self, session_id: str) -> asyncio.Queue:
        async with self._lock:
            if session_id not in self._queues:
                self._queues[session_id] = asyncio.Queue(maxsize=self._max_queue_size)
            return self._queues[session_id]

    def emit(self, session_id: str, event_type: str, data: Optional[dict]=None):
        if event_type not in EVENT_TYPES:
            logger.warning(f"[EventBus] Unknown event type '{event_type}' — emitting anyway")
        event = {'type': event_type, 'session_id': session_id, 'timestamp': time.time(), 'data': data or {}}
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue(maxsize=self._max_queue_size)
        try:
            self._queues[session_id].put_nowait(event)
            logger.debug(f'[EventBus] emit({session_id}) → {event_type}')
        except asyncio.QueueFull:
            logger.warning(f"[EventBus] Queue full for session {session_id} — dropping event '{event_type}'")

    async def emit_async(self, session_id: str, event_type: str, data: Optional[dict]=None):
        queue = await self._get_or_create_queue(session_id)
        event = {'type': event_type, 'session_id': session_id, 'timestamp': time.time(), 'data': data or {}}
        await queue.put(event)
        logger.debug(f'[EventBus] emit_async({session_id}) → {event_type}')

    async def stream(self, session_id: str) -> AsyncIterator[dict]:
        queue = await self._get_or_create_queue(session_id)
        logger.info(f'[EventBus] Starting stream for session {session_id}')
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                    yield event
                    queue.task_done()
                    if event['type'] in ('done', 'fatal_error'):
                        logger.info(f"[EventBus] Terminal event '{event['type']}' — closing stream for {session_id}")
                        break
                except asyncio.TimeoutError:
                    logger.warning(f'[EventBus] Stream timeout for session {session_id} — no events in 120s. Closing.')
                    break
        finally:
            await self.close(session_id)

    async def close(self, session_id: str):
        async with self._lock:
            if session_id in self._queues:
                del self._queues[session_id]
                logger.debug(f'[EventBus] Cleaned up queue for {session_id}')

    def active_sessions(self) -> list:
        return list(self._queues.keys())
event_bus = AgentEventBus()
