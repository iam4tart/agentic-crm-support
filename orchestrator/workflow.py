import asyncio
from langgraph.graph import StateGraph, END
from orchestrator.state import GraphState
from orchestrator.nodes import WorkflowNodes
from utils.composio_bridge import get_composio_bridge
from config.settings import settings
from loguru import logger

class WorkflowGraph:

    def __init__(self):
        self.nodes = WorkflowNodes()
        self.workflow = StateGraph(GraphState)
        self.workflow.add_node('triage', self.nodes.triage_node)
        self.workflow.add_node('plan', self.nodes.plan_node)
        self.workflow.add_node('execute_steps', self.nodes.execute_steps_node)
        self.workflow.add_node('evaluate', self.nodes.evaluate_node)
        self.workflow.set_entry_point('triage')
        self.workflow.add_edge('triage', 'plan')
        self.workflow.add_edge('plan', 'execute_steps')
        self.workflow.add_edge('execute_steps', 'evaluate')
        self.workflow.add_conditional_edges('evaluate', self.nodes.should_continue, {'continue': 'plan', 'end': END})
        self.app = self.workflow.compile()

    def _build_initial_state(self, query: str, ws_session_id: str='', event_source: str='ui', streaming_mode: str='steps') -> dict:
        return {'user_query': query, 'retrieved_docs': [], 'reasoning_steps': [], 'tool_outputs': [], 'final_answer': '', 'evaluation_score': 0.0, 'retry_count': 0, 'intent': 'general', 'intent_confidence': 0.0, 'ticket_key': '', 'crm_server': 'jira', 'event_source': event_source, 'ws_session_id': ws_session_id, 'streaming_mode': streaming_mode}

    def run(self, query: str) -> dict:
        logger.info(f'[Workflow] sync run: {query[:80]}')
        initial_state = self._build_initial_state(query)
        return self.app.invoke(initial_state)

    async def run_streaming(self, query: str, ws_session_id: str, event_source: str='ui', streaming_mode: str='steps') -> dict:
        logger.info(f'[Workflow] streaming run: session={ws_session_id}, mode={streaming_mode}, source={event_source}')
        initial_state = self._build_initial_state(query, ws_session_id, event_source, streaming_mode)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.app.invoke, initial_state)
        return result

async def setup_crm_bridge():
    bridge = await get_composio_bridge()
    logger.info(f'[Startup] CRM bridge ready. Mode: {bridge.mode} | Servers: {bridge.registered_servers()}')
    return bridge
setup_mcp_pool = setup_crm_bridge
