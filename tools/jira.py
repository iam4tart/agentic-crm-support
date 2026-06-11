from typing import Any, Dict, List, Optional
import re
from loguru import logger
from utils.composio_bridge import get_composio_bridge
from config.settings import settings

def _extract_text(result: Any) -> str:
    if result is None:
        return ''
    if hasattr(result, 'content') and result.content:
        return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
    return str(result)

def _extract_issue_key(text: str) -> str:
    match = re.search('([A-Z]+-\\d+)', text)
    return match.group(1) if match else ''

class JiraTools:
    SERVER = 'jira'

    @classmethod
    async def _call(cls, tool: str, args: dict) -> Any:
        bridge = await get_composio_bridge()
        return await bridge.call_tool(cls.SERVER, tool, args)

    @classmethod
    async def create_issue(cls, summary: str, description: str, project_key: Optional[str]=None, issue_type: str='Task', priority: str='Medium') -> Dict[str, Any]:
        pk = project_key or settings.JIRA_PROJECT_KEY
        logger.info(f'[Jira] create_issue in project {pk}: {summary[:60]}')
        result = await cls._call('JIRA_CREATE_ISSUE', {'project_key': pk, 'summary': summary, 'description': description, 'issue_type': issue_type})
        raw_text = _extract_text(result)
        issue_key = _extract_issue_key(raw_text)
        return {'key': issue_key, 'title': summary, 'status': 'Open', 'source': 'jira', 'raw': raw_text}

    @classmethod
    async def get_issue(cls, issue_key: str) -> Dict[str, Any]:
        logger.info(f'[Jira] get_issue: {issue_key}')
        result = await cls._call('JIRA_GET_ISSUE', {'issueKeyOrId': issue_key})
        import json
        try:
            text = _extract_text(result)
            data = json.loads(text)
            status = data.get('fields', {}).get('status', {}).get('name', 'Unknown')
            return {'key': issue_key, 'status': status, 'data': data, 'source': 'jira'}
        except Exception:
            return {'key': issue_key, 'data': _extract_text(result), 'source': 'jira'}

    @classmethod
    async def update_status(cls, issue_key: str, status: str) -> Dict[str, Any]:
        logger.info(f'[Jira] update_status: {issue_key} → {status}')
        result = await cls._call('JIRA_EDIT_ISSUE', {'issueIdOrKey': issue_key, 'fields': {'status': {'name': status}}})
        return {'key': issue_key, 'status': status, 'source': 'jira'}

    @classmethod
    async def search_issues(cls, query: str) -> List[Dict[str, Any]]:
        jql = f'project = {settings.JIRA_PROJECT_KEY} AND text ~ "{query}" ORDER BY created DESC'
        logger.info(f'[Jira] search_issues: {jql}')
        result = await cls._call('JIRA_SEARCH_ISSUES', {'jql': jql, 'maxResults': 5})
        import json
        text = _extract_text(result)
        try:
            data = json.loads(text)
            issues = data.get('issues', [])
            return [{'key': i['key'], 'title': i.get('fields', {}).get('summary', ''), 'status': i.get('fields', {}).get('status', {}).get('name', ''), 'source': 'jira'} for i in issues]
        except Exception:
            return []

    @classmethod
    async def add_comment(cls, issue_key: str, body: str) -> Dict[str, Any]:
        logger.info(f'[Jira] add_comment to {issue_key}')
        result = await cls._call('JIRA_ADD_COMMENT', {'issueIdOrKey': issue_key, 'body': body})
        return {'key': issue_key, 'source': 'jira'}
