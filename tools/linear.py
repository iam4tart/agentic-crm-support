from typing import Any, Dict, List, Optional
from loguru import logger
from utils.composio_bridge import get_composio_bridge

def _extract_text(result: Any) -> str:
    if result is None:
        return ''
    if hasattr(result, 'content') and result.content:
        return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
    return str(result)

class LinearTools:
    SERVER = 'linear'

    @classmethod
    async def _call(cls, tool: str, args: dict) -> Any:
        bridge = await get_composio_bridge()
        return await bridge.call_tool(cls.SERVER, tool, args)

    @classmethod
    async def create_issue(cls, title: str, description: str, priority: str='medium', team: str='Engineering') -> Dict[str, Any]:
        logger.info(f'[Linear] create_issue: {title[:60]}')
        teams_res = await cls._call('LINEAR_LIST_LINEAR_TEAMS', {})
        import json, re
        teams_text = _extract_text(teams_res)
        team_id = None
        try:
            teams_data = json.loads(teams_text)
            teams = teams_data.get('teams', [])
            if teams:
                team_id = teams[0].get('id')
        except Exception as e:
            pass
        if not team_id:
            match = re.search('([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', teams_text)
            if match:
                team_id = match.group(1)
            else:
                logger.warning(f'Failed to find team UUID in: {teams_text[:100]}')
                return {'error': 'No Linear team available to create issue', 'status': 'failed', 'source': 'linear'}
        prio_map = {'urgent': 1, 'high': 2, 'medium': 3, 'normal': 3, 'low': 4, 'none': 0}
        mapped_priority = prio_map.get(priority.lower(), 3)
        result = await cls._call('LINEAR_CREATE_LINEAR_ISSUE', {'team_id': team_id, 'title': f'[{team}] {title}', 'description': description, 'priority': mapped_priority})
        text = _extract_text(result)
        try:
            data = json.loads(text)
        except Exception:
            data = {'raw': text}
        key = data.get('key') or data.get('identifier')
        if not key and data.get('ticket_url'):
            url_match = re.search(r'/issue/([A-Z0-9]+-\d+)', data['ticket_url'])
            if url_match:
                key = url_match.group(1)
        if not key:
            key = data.get('id', '')
        return {'key': key, 'title': title, 'team': team, 'status': 'open', 'data': data, 'source': 'linear', 'url': data.get('ticket_url', '')}

    @classmethod
    async def get_issue(cls, issue_id: str) -> Dict[str, Any]:
        logger.info(f'[Linear] get_issue: {issue_id}')
        result = await cls._call('LINEAR_GET_ISSUE', {'id': issue_id})
        import json
        text = _extract_text(result)
        try:
            data = json.loads(text)
        except Exception:
            data = {'raw': text}
        return {'key': issue_id, 'data': data, 'source': 'linear'}

    @classmethod
    async def update_status(cls, issue_id: str, state: str) -> Dict[str, Any]:
        logger.info(f'[Linear] update_status: {issue_id} → {state}')
        result = await cls._call('LINEAR_UPDATE_ISSUE', {'id': issue_id, 'state_id': state})
        import json
        text = _extract_text(result)
        try:
            data = json.loads(text)
        except Exception:
            data = {'raw': text}
        return {'key': issue_id, 'state': state, 'data': data, 'source': 'linear'}

    @classmethod
    async def search_issues(cls, query: str) -> List[Dict[str, Any]]:
        logger.info(f'[Linear] search_issues: {query}')
        result = await cls._call('LINEAR_SEARCH_ISSUES', {'query': query})
        import json
        text = _extract_text(result)
        try:
            data = json.loads(text)
            tickets = data.get('issues', []) or data.get('nodes', [])
            return [
                {
                    'key': t.get('identifier') or t.get('id', ''),
                    'title': t.get('title', ''),
                    'status': t.get('state', {}).get('name', '') if isinstance(t.get('state'), dict) else str(t.get('state') or ''),
                    'source': 'linear'
                }
                for t in tickets
            ]
        except Exception:
            return []

    @classmethod
    async def add_comment(cls, issue_id: str, body: str) -> Dict[str, Any]:
        logger.info(f'[Linear] add_comment to {issue_id}')
        result = await cls._call('LINEAR_CREATE_COMMENT', {'issue_id': issue_id, 'body': body})
        import json
        text = _extract_text(result)
        try:
            data = json.loads(text)
        except Exception:
            data = {'raw': text}
        return {'key': issue_id, 'data': data, 'source': 'linear'}
