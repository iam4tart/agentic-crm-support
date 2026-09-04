from typing import Any, Dict, List, Optional
import re
import requests
from requests.auth import HTTPBasicAuth
from loguru import logger
from utils.composio_bridge import get_composio_bridge
from config.settings import settings

def _jira_auth():
    return HTTPBasicAuth(settings.JIRA_USERNAME, settings.JIRA_API_TOKEN)

def _jira_headers():
    return {'Accept': 'application/json', 'Content-Type': 'application/json'}

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
        
        try:
            result = await cls._call('JIRA_CREATE_ISSUE', {'project_key': pk, 'summary': summary, 'description': description, 'issue_type': issue_type})
            raw_text = _extract_text(result)
            issue_key = _extract_issue_key(raw_text)
            if issue_key and 'error' not in raw_text.lower():
                return {'key': issue_key, 'title': summary, 'status': 'Open', 'source': 'jira', 'raw': raw_text}
            logger.warning(f'[Jira] Composio create_issue did not return key: {raw_text[:120]}. Falling back to direct REST API.')
        except Exception as e:
            logger.warning(f'[Jira] Composio create_issue failed: {e}. Falling back to direct REST API.')

        try:
            url = f"{settings.JIRA_BASE_URL}/rest/api/3/issue"
            payload = {
                'fields': {
                    'project': {'key': pk},
                    'summary': summary,
                    'description': {
                        'type': 'doc',
                        'version': 1,
                        'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': description}]}]
                    },
                    'issuetype': {'name': issue_type}
                }
            }
            resp = requests.post(url, auth=_jira_auth(), json=payload, headers=_jira_headers(), timeout=15)
            if resp.status_code in (200, 201):
                data = resp.json()
                key = data.get('key', '')
                logger.info(f'[Jira] Direct REST create_issue success: {key}')
                return {'key': key, 'title': summary, 'status': 'Open', 'source': 'jira', 'raw': str(data)}
            logger.error(f'[Jira] Direct REST create_issue failed ({resp.status_code}): {resp.text[:200]}')
        except Exception as ex:
            logger.error(f'[Jira] Direct REST create_issue exception: {ex}')

        return {'key': '', 'title': summary, 'status': 'Failed', 'source': 'jira', 'raw': 'Both Composio and Direct REST failed'}

    @classmethod
    async def get_issue(cls, issue_key: str) -> Dict[str, Any]:
        logger.info(f'[Jira] get_issue: {issue_key}')
        try:
            result = await cls._call('JIRA_GET_ISSUE', {'issueKeyOrId': issue_key})
            import json
            text = _extract_text(result)
            if 'error' not in text.lower():
                data = json.loads(text)
                status = data.get('fields', {}).get('status', {}).get('name', 'Unknown')
                return {'key': issue_key, 'status': status, 'data': data, 'source': 'jira'}
        except Exception:
            pass

        try:
            url = f"{settings.JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
            resp = requests.get(url, auth=_jira_auth(), headers=_jira_headers(), timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get('fields', {}).get('status', {}).get('name', 'Unknown')
                return {'key': issue_key, 'status': status, 'data': data, 'source': 'jira'}
        except Exception as ex:
            logger.error(f'[Jira] Direct REST get_issue exception: {ex}')

        return {'key': issue_key, 'data': {}, 'source': 'jira'}

    @classmethod
    async def update_status(cls, issue_key: str, status: str) -> Dict[str, Any]:
        logger.info(f'[Jira] update_status: {issue_key} → {status}')
        try:
            await cls._call('JIRA_EDIT_ISSUE', {'issueIdOrKey': issue_key, 'fields': {'status': {'name': status}}})
        except Exception:
            pass
        return {'key': issue_key, 'status': status, 'source': 'jira'}

    @classmethod
    async def search_issues(cls, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        jql = query if query.strip().startswith("project =") else f'project = {settings.JIRA_PROJECT_KEY} AND text ~ "{query}" ORDER BY created DESC'
        logger.info(f'[Jira] search_issues: {jql}')
        
        try:
            result = await cls._call('JIRA_SEARCH_ISSUES', {'jql': jql, 'maxResults': max_results})
            import json
            text = _extract_text(result)
            if 'error' not in text.lower():
                data = json.loads(text)
                issues = data.get('issues', [])
                if issues:
                    formatted = []
                    for i in issues:
                        summary = i.get('summary') or i.get('fields', {}).get('summary', '')
                        status_val = i.get('status')
                        status_name = status_val.get('name', '') if isinstance(status_val, dict) else (i.get('fields', {}).get('status', {}).get('name', '') or str(status_val or ''))
                        formatted.append({'key': i.get('key', ''), 'title': summary, 'status': status_name, 'source': 'jira'})
                    return formatted
        except Exception:
            pass

        try:
            url = f"{settings.JIRA_BASE_URL}/rest/api/3/search/jql"
            payload = {'jql': jql, 'maxResults': max_results, 'fields': ['summary', 'status']}
            resp = requests.post(url, auth=_jira_auth(), json=payload, headers=_jira_headers(), timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                issues = data.get('issues', [])
                return [{'key': i.get('key', ''), 'title': i.get('fields', {}).get('summary', ''), 'status': i.get('fields', {}).get('status', {}).get('name', ''), 'source': 'jira'} for i in issues]
            logger.warning(f'[Jira] Direct REST search failed ({resp.status_code}): {resp.text[:150]}')
        except Exception as ex:
            logger.error(f'[Jira] Direct REST search exception: {ex}')

        return []

    @classmethod
    async def add_comment(cls, issue_key: str, body: str) -> Dict[str, Any]:
        logger.info(f'[Jira] add_comment to {issue_key}')
        try:
            await cls._call('JIRA_ADD_COMMENT', {'issueIdOrKey': issue_key, 'body': body})
        except Exception:
            pass
        try:
            url = f"{settings.JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment"
            payload = {
                'body': {
                    'type': 'doc',
                    'version': 1,
                    'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': body}]}]
                }
            }
            requests.post(url, auth=_jira_auth(), json=payload, headers=_jira_headers(), timeout=15)
        except Exception as ex:
            logger.error(f'[Jira] Direct REST add_comment exception: {ex}')

        return {'key': issue_key, 'source': 'jira'}
