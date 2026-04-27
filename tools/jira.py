import requests
from requests.auth import HTTPBasicAuth
from config.settings import settings
from typing import Dict, Any

class JiraTools:

    def __init__(self):
        self.base_url = settings.JIRA_BASE_URL
        self.auth = HTTPBasicAuth(settings.JIRA_USERNAME, settings.
            JIRA_API_TOKEN)
        self.headers = {'Accept': 'application/json', 'Content-Type':
            'application/json'}

    def get_issue(self, issue_key: str) ->Dict[str, Any]:
        url = f'{self.base_url}/rest/api/3/issue/{issue_key}'
        response = requests.get(url, headers=self.headers, auth=self.auth)
        response.raise_for_status()
        return response.json()

    def create_issue(self, summary: str, description: str, project_key: str
        ='KAN', issue_type: str='Task') ->Dict[str, Any]:
        url = f'{self.base_url}/rest/api/3/issue'
        payload = {'fields': {'project': {'key': project_key}, 'summary':
            summary, 'description': {'type': 'doc', 'version': 1, 'content':
            [{'type': 'paragraph', 'content': [{'type': 'text', 'text':
            description}]}]}, 'issuetype': {'name': issue_type}}}
        response = requests.post(url, json=payload, headers=self.headers,
            auth=self.auth)
        response.raise_for_status()
        return response.json()

    def update_issue_priority(self, issue_key: str, priority_id: str) ->Dict[
        str, Any]:
        url = f'{self.base_url}/rest/api/3/issue/{issue_key}'
        payload = {'update': {'priority': [{'set': {'id': priority_id}}]}}
        response = requests.put(url, json=payload, headers=self.headers,
            auth=self.auth)
        response.raise_for_status()
        return {'status': 'success', 'issue_key': issue_key}
