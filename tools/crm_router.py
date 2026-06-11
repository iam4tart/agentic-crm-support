from typing import Any, Dict, List, Optional
from loguru import logger
from tools.jira import JiraTools
from tools.linear import LinearTools
ROUTING: Dict[str, str] = {'technical': 'jira', 'billing': 'jira', 'product': 'linear', 'escalate': 'linear', 'general': 'jira'}
CRM_LABELS: Dict[str, str] = {'jira': '🐛 Jira (Engineering)', 'linear': '📐 Linear (Product)'}

def resolve_server(intent: str) -> str:
    return ROUTING.get(intent.lower(), 'jira')

class CRMRouter:

    @staticmethod
    def label(server: str) -> str:
        return CRM_LABELS.get(server, server)

    @staticmethod
    async def create_ticket(intent: str, summary: str, description: str, priority: str='Medium', **kwargs) -> Dict[str, Any]:
        server = resolve_server(intent)
        logger.info(f'[CRMRouter] create_ticket → {server} (intent={intent})')
        try:
            if server == 'jira':
                return await JiraTools.create_issue(summary=summary, description=description, project_key=kwargs.get('project_key'), issue_type=kwargs.get('issue_type', 'Task'), priority=priority)
            elif server == 'linear':
                return await LinearTools.create_issue(title=summary, description=description, priority=priority.lower(), team=kwargs.get('team', 'Engineering'))
        except Exception as e:
            logger.error(f'[CRMRouter] create_ticket failed on {server}: {e}')
            return {'key': '', 'error': str(e), 'source': server, 'status': 'error'}

    @staticmethod
    async def get_ticket(intent: str, ticket_key: str) -> Dict[str, Any]:
        server = resolve_server(intent)
        logger.info(f'[CRMRouter] get_ticket {ticket_key} → {server}')
        try:
            if server == 'jira':
                return await JiraTools.get_issue(ticket_key)
            elif server == 'linear':
                return await LinearTools.get_issue(ticket_key)
        except Exception as e:
            logger.error(f'[CRMRouter] get_ticket failed: {e}')
            return {'key': ticket_key, 'error': str(e), 'source': server}

    @staticmethod
    async def search_tickets(intent: str, query: str, max_results: int=5) -> List[Dict[str, Any]]:
        server = resolve_server(intent)
        logger.info(f'[CRMRouter] search_tickets on {server}: {query}')
        try:
            if server == 'jira':
                from config.settings import settings
                jql = f'project = {settings.JIRA_PROJECT_KEY} AND text ~ "{query}" ORDER BY created DESC'
                return await JiraTools.search_issues(jql, max_results)
            elif server == 'linear':
                return await LinearTools.search_issues(query)
        except Exception as e:
            logger.error(f'[CRMRouter] search_tickets failed: {e}')
            return []
        return []

    @staticmethod
    async def update_ticket(intent: str, ticket_key: str, status: Optional[str]=None, priority: Optional[str]=None) -> Dict[str, Any]:
        server = resolve_server(intent)
        logger.info(f'[CRMRouter] update_ticket {ticket_key} → {server}')
        try:
            if server == 'jira':
                return await JiraTools.update_issue(ticket_key, priority=priority)
            elif server == 'linear':
                if status:
                    return await LinearTools.update_status(ticket_key, status)
                return {'key': ticket_key, 'source': server}
        except Exception as e:
            logger.error(f'[CRMRouter] update_ticket failed: {e}')
            return {'key': ticket_key, 'error': str(e), 'source': server}

    @staticmethod
    async def add_note(intent: str, ticket_key: str, body: str) -> Dict[str, Any]:
        server = resolve_server(intent)
        logger.info(f'[CRMRouter] add_note to {ticket_key} → {server}')
        try:
            if server == 'jira':
                return await JiraTools.add_comment(ticket_key, body)
            elif server == 'linear':
                return await LinearTools.add_comment(ticket_key, body)
        except Exception as e:
            logger.error(f'[CRMRouter] add_note failed: {e}')
            return {'key': ticket_key, 'error': str(e), 'source': server}

    @staticmethod
    async def resolve_ticket(intent: str, ticket_key: str) -> Dict[str, Any]:
        server = resolve_server(intent)
        logger.info(f'[CRMRouter] resolve_ticket {ticket_key} → {server}')
        try:
            if server == 'jira':
                return await JiraTools.transition_issue(ticket_key, 'Done')
            elif server == 'linear':
                return await LinearTools.update_status(ticket_key, 'resolved')
        except Exception as e:
            logger.error(f'[CRMRouter] resolve_ticket failed: {e}')
            return {'key': ticket_key, 'error': str(e), 'source': server}
