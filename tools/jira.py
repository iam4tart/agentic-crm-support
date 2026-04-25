import requests
from requests.auth import HTTPBasicAuth
from config.settings import settings
from typing import Dict, Any

class JiraTools:
    def __init__(self):
        self.base_url = settings.jira_base_url
        self.auth = HTTPBasicAuth(settings.jira_username, settings.jira_api_token)
        self.headers = {"Accept": "application/json"}

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        response = requests.get(url, headers=self.headers, auth=self.auth)
        response.raise_for_status()
        return response.json()

    def update_issue_priority(self, issue_key: str, priority_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        payload = {
            "update": {
                "priority": [{"set": {"id": priority_id}}]
            }
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        response = requests.put(url, json=payload, headers=headers, auth=self.auth)
        response.raise_for_status()
        return {"status": "success", "issue_key": issue_key}
