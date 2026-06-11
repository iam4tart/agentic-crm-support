import asyncio
import os
import sys
import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestEventBus:

    def test_emit_and_stream(self):
        from utils.event_bus import AgentEventBus
        bus = AgentEventBus()
        sid = 'test-session-1'

        async def run():
            bus.emit(sid, 'intent_detected', {'intent': 'technical'})
            bus.emit(sid, 'done', {'final_answer': 'Fixed!'})
            events = []
            async for event in bus.stream(sid):
                events.append(event)
            return events
        events = asyncio.run(run())
        assert len(events) == 2
        assert events[0]['type'] == 'intent_detected'
        assert events[0]['data']['intent'] == 'technical'
        assert events[1]['type'] == 'done'

    def test_timeout_closes_stream(self):
        from utils.event_bus import AgentEventBus
        bus = AgentEventBus()
        sid = 'test-session-timeout'
        bus.emit(sid, 'done', {})

        async def run():
            events = []
            async for event in bus.stream(sid):
                events.append(event)
            return events
        events = asyncio.run(run())
        assert any((e['type'] == 'done' for e in events))

class TestCircuitBreaker:

    def test_opens_after_threshold(self):
        from utils.mcp_client import CircuitBreaker
        cb = CircuitBreaker(threshold=3, reset_timeout=60.0)
        assert not cb.is_open()
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open()
        cb.record_failure()
        assert cb.is_open()

    def test_success_resets_counter(self):
        from utils.mcp_client import CircuitBreaker
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert not cb.is_open()

    def test_half_open_after_timeout(self):
        from utils.mcp_client import CircuitBreaker
        cb = CircuitBreaker(threshold=1, reset_timeout=0.01)
        cb.record_failure()
        assert cb.is_open()
        time.sleep(0.05)
        assert cb.state == 'half_open'

class TestCRMRouter:

    def test_routing_table_technical(self):
        from tools.crm_router import resolve_server
        assert resolve_server('technical') == 'jira'

    def test_routing_table_billing(self):
        from tools.crm_router import resolve_server
        assert resolve_server('billing') == 'jira'

    def test_routing_table_product(self):
        from tools.crm_router import resolve_server
        assert resolve_server('product') == 'linear'

    def test_routing_table_escalate(self):
        from tools.crm_router import resolve_server
        assert resolve_server('escalate') == 'jira'

    def test_routing_table_unknown_defaults_jira(self):
        from tools.crm_router import resolve_server
        assert resolve_server('unknown_intent') == 'jira'

    def test_create_ticket_routes_to_jira(self):
        from tools.crm_router import CRMRouter

        async def run():
            with patch('tools.crm_router.JiraTools.create_issue', new_callable=AsyncMock) as mock:
                mock.return_value = {'key': 'KAN-99', 'source': 'jira'}
                result = await CRMRouter.create_ticket(intent='technical', summary='Login broken', description='User cannot log in')
                mock.assert_called_once()
                assert result['source'] == 'jira'
        asyncio.run(run())

class TestMockCRMServer:

    def test_create_ticket(self):
        from tools.mock_crm_server import handle_crm_create_ticket, TICKET_DB
        TICKET_DB.clear()
        result = handle_crm_create_ticket({'subject': 'Test issue', 'description': 'Something is wrong', 'priority': 'high', 'type': 'Bug'})
        assert result['success'] is True
        assert 'ticket_id' in result
        assert result['ticket']['status'] == 'open'
        assert result['ticket_id'] in TICKET_DB

    def test_get_ticket_not_found(self):
        from tools.mock_crm_server import handle_crm_get_ticket
        result = handle_crm_get_ticket({'ticket_id': 'NONEXISTENT-999'})
        assert result['success'] is False
        assert 'not found' in result['error']

    def test_resolve_ticket(self):
        from tools.mock_crm_server import handle_crm_create_ticket, handle_crm_resolve_ticket, TICKET_DB
        TICKET_DB.clear()
        create_result = handle_crm_create_ticket({'subject': 'To resolve', 'description': '...'})
        tid = create_result['ticket_id']
        resolve_result = handle_crm_resolve_ticket({'ticket_id': tid})
        assert resolve_result['success'] is True
        assert TICKET_DB[tid]['status'] == 'resolved'

    def test_search_tickets(self):
        from tools.mock_crm_server import handle_crm_create_ticket, handle_crm_search_tickets, TICKET_DB
        TICKET_DB.clear()
        handle_crm_create_ticket({'subject': 'API key reset needed', 'description': 'User locked out'})
        handle_crm_create_ticket({'subject': 'Billing error', 'description': 'Wrong charge'})
        results = handle_crm_search_tickets({'query': 'API key'})
        assert results['success'] is True
        assert results['count'] >= 1
        assert all(('api key' in t['subject'].lower() for t in results['tickets']))

class TestWorkflowGraph:

    def test_initialization(self):
        with patch('orchestrator.workflow.WorkflowNodes'), patch('orchestrator.workflow.setup_mcp_pool'):
            from orchestrator.workflow import WorkflowGraph
            wf = WorkflowGraph()
            assert wf.app is not None

    def test_initial_state_structure(self):
        with patch('orchestrator.workflow.WorkflowNodes'), patch('orchestrator.workflow.setup_mcp_pool'):
            from orchestrator.workflow import WorkflowGraph
            wf = WorkflowGraph()
            state = wf._build_initial_state('test query', 'sess-123', 'ui', 'steps')
            assert state['user_query'] == 'test query'
            assert state['ws_session_id'] == 'sess-123'
            assert state['event_source'] == 'ui'
            assert state['streaming_mode'] == 'steps'
            assert state['intent'] == 'general'
            assert state['ticket_key'] == ''

class TestTriageNode:

    def _make_nodes(self, intent_response: str):
        with patch('orchestrator.nodes.Retriever'), patch('orchestrator.nodes.Evaluator'):
            from orchestrator.nodes import WorkflowNodes
            nodes = WorkflowNodes()
            nodes.reasoner = MagicMock()
            nodes.reasoner._query_api.return_value = intent_response
            return nodes

    def test_classifies_technical(self):
        nodes = self._make_nodes('{"intent": "technical", "confidence": 0.95, "reasoning": "login bug"}')
        state = {'user_query': 'Login is broken', 'ws_session_id': '', 'intent': 'general', 'intent_confidence': 0.0, 'crm_server': 'jira'}
        result = nodes.triage_node(state)
        assert result['intent'] == 'technical'
        assert result['crm_server'] == 'jira'

    def test_classifies_billing(self):
        nodes = self._make_nodes('{"intent": "billing", "confidence": 0.88, "reasoning": "invoice dispute"}')
        state = {'user_query': 'Wrong invoice amount', 'ws_session_id': '', 'intent': 'general', 'intent_confidence': 0.0, 'crm_server': 'jira'}
        result = nodes.triage_node(state)
        assert result['intent'] == 'billing'
        assert result['crm_server'] == 'jira'

    def test_invalid_llm_response_defaults_general(self):
        nodes = self._make_nodes('I cannot classify this')
        state = {'user_query': 'Something random', 'ws_session_id': '', 'intent': 'general', 'intent_confidence': 0.0, 'crm_server': 'jira'}
        result = nodes.triage_node(state)
        assert result['intent'] == 'general'
