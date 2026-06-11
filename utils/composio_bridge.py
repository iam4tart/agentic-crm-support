import os
import asyncio
from typing import Any, Dict, Optional
from loguru import logger
COMPOSIO_TOOL_MAP: Dict[str, Dict[str, str]] = {'jira': {'jira_create_issue': 'JIRA_CREATE_ISSUE', 'jira_get_issue': 'JIRA_GET_ISSUE', 'jira_update_issue': 'JIRA_UPDATE_ISSUE', 'jira_search_issues': 'JIRA_SEARCH_ISSUES', 'jira_transition_issue': 'JIRA_UPDATE_ISSUE', 'jira_add_comment': 'JIRA_ADD_COMMENT'}, 'linear': {'crm_create_ticket': 'LINEAR_CREATE_ISSUE', 'crm_get_ticket': 'LINEAR_GET_ISSUE', 'crm_update_ticket': 'LINEAR_UPDATE_ISSUE', 'crm_search_tickets': 'LINEAR_SEARCH_ISSUES', 'crm_add_note': 'LINEAR_ADD_COMMENT'}}
RESULT_NORMALIZERS: Dict[str, str] = {'JIRA_CREATE_ISSUE': 'jira', 'LINEAR_CREATE_ISSUE': 'linear'}

class ComposioMCPBridge:

    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = os.environ.get('COMPOSIO_API_KEY', '')
        self._composio = None
        self._session = None
        self._use_composio = bool(self.api_key)
        self._local_pool = None

    async def initialize(self):
        if self._use_composio:
            await self._init_composio()
        else:
            logger.warning('[Composio] COMPOSIO_API_KEY not set — falling back to local MCPSessionPool (jira-stdio + mock CRM)')
            await self._init_local_fallback()

    async def _init_composio(self):
        try:
            from composio import Composio
            self._composio = Composio(api_key=self.api_key)
            self._session = self._composio.create(user_id='pg-test-4609adab-c0f2-4021-a1d2-8e216d6bca28')
            logger.info(f'[Composio] Session initialized. MCP URL: {self._session.mcp.url}')
            logger.info('[Composio] Connected apps: Jira + Linear (ensure connected in Composio dashboard)')
        except ImportError:
            logger.error('[Composio] composio package not installed. Run: pip install composio\nFalling back to local MCPSessionPool.')
            self._use_composio = False
            await self._init_local_fallback()
        except Exception as e:
            logger.error(f'[Composio] Session init failed: {e}. Falling back to local pool.')
            self._use_composio = False
            await self._init_local_fallback()

    async def _init_local_fallback(self):
        import sys
        from config.settings import settings
        from utils.mcp_client import MCPSessionPool
        self._local_pool = await MCPSessionPool.instance()
        jira_env = {'JIRA_URL': settings.JIRA_BASE_URL, 'JIRA_API_TOKEN': settings.JIRA_API_TOKEN, 'JIRA_EMAIL': settings.JIRA_USERNAME}
        await self._local_pool.register(name='jira', command='npx', args=['-y', 'mcp-jira-stdio'], env=jira_env, auto_connect=False)
        python_exe = sys.executable
        mock_path = os.path.join(os.path.dirname(__file__), '..', 'tools', 'mock_crm_server.py')
        mock_path = os.path.abspath(mock_path)
        await self._local_pool.register(name='linear', command=python_exe, args=[mock_path], auto_connect=False)
        logger.info(f'[Composio] Fallback pool ready: {self._local_pool.registered_servers()}')

    async def call_tool(self, server: str, tool_name: str, arguments: dict, max_retries: int=3) -> Any:
        if self._use_composio:
            return await self._call_via_composio(server, tool_name, arguments)
        else:
            return await self._local_pool.call_tool(server, tool_name, arguments, max_retries)

    async def _call_via_composio(self, server: str, tool_name: str, arguments: dict) -> Any:
        if tool_name.isupper():
            composio_action = tool_name
        else:
            composio_action = COMPOSIO_TOOL_MAP.get(server, {}).get(tool_name)
        if not composio_action:
            raise ValueError(f'[Composio] No mapping for ({server}, {tool_name}). Available: {list(COMPOSIO_TOOL_MAP.get(server, {}).keys())}')
        logger.info(f'[Composio] Executing {composio_action} with args: {list(arguments.keys())}')
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._session.execute(tool_slug=composio_action, arguments=arguments))
            return _ComposioResult(result, composio_action)
        except Exception as e:
            logger.error(f'[Composio] {composio_action} failed: {e}')
            raise

    async def is_healthy(self, server: str) -> bool:
        if self._use_composio:
            return self._session is not None
        return await self._local_pool.is_healthy(server)

    async def health_report(self) -> Dict[str, Any]:
        if self._use_composio:
            healthy = self._session is not None
            return {'composio': healthy, 'mode': 'composio', 'mcp_url': getattr(self._session, 'mcp', {}).url if healthy else None}
        report = await self._local_pool.health_report()
        report['mode'] = 'local_fallback'
        return report

    async def shutdown(self):
        if not self._use_composio and self._local_pool:
            await self._local_pool.shutdown()
        logger.info('[Composio] Bridge shut down')

    def registered_servers(self) -> list:
        if self._use_composio:
            return ['jira', 'linear']
        return self._local_pool.registered_servers() if self._local_pool else []

    @property
    def mode(self) -> str:
        return 'composio' if self._use_composio else 'local_fallback'

class _ComposioResult:

    def __init__(self, raw: Any, action: str):
        self._raw = raw
        self._action = action
        import json
        if isinstance(raw, dict):
            text = json.dumps(raw, indent=2)
        else:
            text = str(raw)
        self.content = [_TextContent(text)]
        self.is_error = isinstance(raw, dict) and raw.get('error')

class _TextContent:

    def __init__(self, text: str):
        self.text = text
_bridge_instance: Optional[ComposioMCPBridge] = None

async def get_composio_bridge() -> ComposioMCPBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = ComposioMCPBridge()
        await _bridge_instance.initialize()
    return _bridge_instance
