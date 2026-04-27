import os
import sys
from unittest.mock import patch, MagicMock
import pytest
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator.workflow import WorkflowGraph
from orchestrator.state import GraphState
from tools.jira import JiraTools
from rag.retriever import Retriever
from agents.reasoning import Reasoner


@pytest.fixture
def mock_settings():
    with patch('config.settings.settings') as mock:
        mock.jira_base_url = 'https://mock.atlassian.net'
        mock.jira_username = 'mockuser'
        mock.jira_api_token = 'mocktoken'
        mock.chroma_db_dir = './mock_chroma'
        mock.max_retries = 2
        yield mock


def test_workflow_initialization(mock_settings):
    with patch('orchestrator.workflow.Retriever'), patch(
        'orchestrator.workflow.Reasoner'):
        workflow = WorkflowGraph()
        assert workflow is not None


def test_jira_get_issue(mock_settings):
    jira = JiraTools()
    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'key': 'TEST-1', 'fields': {
            'summary': 'Mock Issue'}}
        mock_get.return_value = mock_resp
        result = jira.get_issue('TEST-1')
        assert result['key'] == 'TEST-1'
        assert result['fields']['summary'] == 'Mock Issue'


def test_jira_update_priority(mock_settings):
    jira = JiraTools()
    with patch('requests.put') as mock_put:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_put.return_value = mock_resp
        result = jira.update_issue_priority('TEST-1', 'High')
        assert result['status'] == 'success'
        assert result['issue_key'] == 'TEST-1'


def test_reasoning_plan_generation(mock_settings):
    with patch('agents.reasoning.pipeline') as mock_pipeline:
        mock_generator = MagicMock()
        mock_generator.return_value = [{'generated_text':
            '{"steps": ["retrieve", "tool_call", "respond"]}'}]
        mock_pipeline.return_value = mock_generator
        reasoner = Reasoner()
        plan = reasoner.generate_plan('My login is broken')
        assert 'steps' in plan
        assert len(plan['steps']) == 3


def test_workflow_plan_node(mock_settings):
    with patch('orchestrator.workflow.Retriever'), patch(
        'orchestrator.workflow.Reasoner') as MockReasoner:
        mock_reasoner_instance = MockReasoner.return_value
        mock_reasoner_instance.generate_plan.return_value = {'steps': [
            'retrieve']}
        workflow = WorkflowGraph()
        state: GraphState = {'user_query': 'Test query', 'retrieved_docs':
            [], 'reasoning_steps': [], 'tool_outputs': [], 'final_answer':
            '', 'evaluation_score': 0.0, 'retry_count': 0}
        result = workflow.plan_node(state)
        assert result['reasoning_steps'] == ['retrieve']
