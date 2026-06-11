import asyncio
import os
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class CircuitBreaker:
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, threshold: int=5, reset_timeout: float=60.0):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = self.CLOSED
        self._opened_at: Optional[float] = None

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.monotonic() - self._opened_at >= self.reset_timeout:
                self._state = self.HALF_OPEN
                logger.info('Circuit breaker entering HALF_OPEN state')
        return self._state

    def is_open(self) -> bool:
        return self.state == self.OPEN

    def record_success(self):
        self._failures = 0
        self._state = self.CLOSED

    def record_failure(self):
        self._failures += 1
        if self._failures >= self.threshold:
            if self._state != self.OPEN:
                logger.warning(f'Circuit breaker OPENED after {self._failures} consecutive failures')
                self._state = self.OPEN
                self._opened_at = time.monotonic()

@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list
    env: dict = field(default_factory=dict)

class MCPServerSession:

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._lock = asyncio.Lock()
        self.circuit = CircuitBreaker(threshold=5, reset_timeout=60.0)

    async def connect(self):
        logger.info(f'[MCP:{self.config.name}] Connecting → {self.config.command} {self.config.args}')
        self._exit_stack = AsyncExitStack()
        merged_env = {**os.environ, **self.config.env}
        server_params = StdioServerParameters(command=self.config.command, args=self.config.args, env=merged_env)
        read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
        self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        logger.info(f'[MCP:{self.config.name}] Session initialized ✓')

    async def disconnect(self):
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.warning(f'[MCP:{self.config.name}] Disconnect error: {e}')
            finally:
                self.session = None
                self._exit_stack = None

    async def call_tool_with_retry(self, tool_name: str, arguments: dict, max_retries: int=3) -> Any:
        if self.circuit.is_open():
            raise RuntimeError(f'[MCP:{self.config.name}] Circuit breaker is OPEN — refusing call to {tool_name}. Will retry in ~{self.circuit.reset_timeout}s.')
        async with self._lock:
            for attempt in range(max_retries):
                try:
                    if not self.session:
                        await self.connect()
                    logger.info(f'[MCP:{self.config.name}] Calling {tool_name} (attempt {attempt + 1}/{max_retries})')
                    result = await self.session.call_tool(tool_name, arguments)
                    self.circuit.record_success()
                    return result
                except (BrokenPipeError, ConnectionResetError, EOFError) as e:
                    logger.warning(f'[MCP:{self.config.name}] Session lost on attempt {attempt + 1}: {e}. Reconnecting...')
                    await self.disconnect()
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                except Exception as e:
                    wait = 2 ** attempt
                    logger.warning(f'[MCP:{self.config.name}] Tool call failed on attempt {attempt + 1}: {e}. Retrying in {wait}s...')
                    self.circuit.record_failure()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait)
                    else:
                        self.circuit.record_failure()
                        raise
        raise RuntimeError(f'[MCP:{self.config.name}] All {max_retries} attempts failed for {tool_name}')

    async def list_tools(self) -> list:
        if not self.session:
            await self.connect()
        result = await self.session.list_tools()
        return result.tools if hasattr(result, 'tools') else []

    async def is_healthy(self) -> bool:
        if self.circuit.is_open():
            return False
        try:
            if not self.session:
                await self.connect()
            return True
        except Exception:
            return False

class MCPSessionPool:
    _singleton: Optional['MCPSessionPool'] = None
    _init_lock = asyncio.Lock()

    def __init__(self):
        self._servers: Dict[str, MCPServerSession] = {}

    @classmethod
    async def instance(cls) -> 'MCPSessionPool':
        async with cls._init_lock:
            if cls._singleton is None:
                cls._singleton = cls()
                logger.info('MCPSessionPool singleton created')
            return cls._singleton

    async def register(self, name: str, command: str, args: list, env: Optional[dict]=None, auto_connect: bool=False):
        if name in self._servers:
            logger.debug(f"[MCPPool] Server '{name}' already registered — skipping")
            return
        config = MCPServerConfig(name=name, command=command, args=args, env=env or {})
        session = MCPServerSession(config)
        self._servers[name] = session
        if auto_connect:
            await session.connect()
        logger.info(f"[MCPPool] Registered server '{name}' ({command} {args})")

    async def call_tool(self, server: str, tool_name: str, arguments: dict, max_retries: int=3) -> Any:
        if server not in self._servers:
            raise KeyError(f"[MCPPool] No server registered with name '{server}'")
        return await self._servers[server].call_tool_with_retry(tool_name, arguments, max_retries)

    async def list_tools(self, server: str) -> list:
        if server not in self._servers:
            raise KeyError(f"[MCPPool] No server registered with name '{server}'")
        return await self._servers[server].list_tools()

    async def is_healthy(self, server: str) -> bool:
        if server not in self._servers:
            return False
        return await self._servers[server].is_healthy()

    async def health_report(self) -> Dict[str, bool]:
        return {name: await sess.is_healthy() for name, sess in self._servers.items()}

    async def shutdown(self):
        for name, sess in self._servers.items():
            logger.info(f"[MCPPool] Shutting down '{name}'...")
            await sess.disconnect()
        self._servers.clear()
        MCPSessionPool._singleton = None
        logger.info('[MCPPool] All sessions disconnected')

    def registered_servers(self) -> list:
        return list(self._servers.keys())
