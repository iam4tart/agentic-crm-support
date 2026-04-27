from loguru import logger
import json
from orchestrator.state import GraphState
from agents.reasoning import Reasoner
from rag.retriever import Retriever
from tools.jira import JiraTools
from evaluation.evaluator import Evaluator
from config.settings import settings
from langgraph.graph import END


class WorkflowNodes:

    def __init__(self):
        self.reasoner = Reasoner()
        self.retriever = Retriever()
        self.jira = JiraTools()
        self.evaluator = Evaluator()

    def plan_node(self, state: GraphState) ->dict:
        logger.info(f"Planning steps for query: {state['user_query']}")
        plan = self.reasoner.generate_plan(state['user_query'])
        steps = plan.get('steps', [])
        query_lower = state['user_query'].lower()
        if 'ticket' in query_lower or 'jira' in query_lower:
            if not any(s for s in steps if 'tool' in str(s) or 'jira' in str(s)
                ):
                logger.info('Heuristic Override: Forcing tool_call')
                steps.insert(0, 'tool_call')
        if 'respond' not in steps:
            steps.append('respond')
        return {'reasoning_steps': steps}

    def execute_steps_node(self, state: GraphState) ->dict:
        updates = {}
        retrieved_docs = list(state.get('retrieved_docs', []))
        tool_outputs = list(state.get('tool_outputs', []))
        for raw_step in state['reasoning_steps']:
            step = raw_step.get('tool_call', '') if isinstance(raw_step, dict
                ) else str(raw_step)
            step = step.lower()
            if 'retrieve' in step:
                logger.info('Performing Real RAG Retrieval...')
                docs = self.retriever.retrieve(state['user_query'])
                retrieved_docs.extend(docs)
                updates['retrieved_docs'] = retrieved_docs
            elif 'tool' in step or 'jira' in step or 'ticket' in step:
                try:
                    if 'create' in state['user_query'].lower(
                        ) or 'ticket' in state['user_query'].lower():
                        issue = self.jira.create_issue(summary=
                            f"Support Request: {state['user_query'][:50]}",
                            description=
                            f"Automated ticket created for: {state['user_query']}"
                            , project_key=settings.JIRA_PROJECT_KEY)
                        tool_outputs.append({'type': 'jira_create', 'data':
                            issue})
                    else:
                        issue_data = self.jira.get_issue('TEST-1')
                        tool_outputs.append({'type': 'jira_get', 'data':
                            issue_data})
                except Exception as e:
                    logger.error(f'Jira Tool Error: {e}')
                    tool_outputs.append({'type': 'error', 'message': str(e)})
                updates['tool_outputs'] = tool_outputs
            elif 'respond' in step:
                context = '\n'.join(retrieved_docs)
                tools_out = json.dumps(tool_outputs)
                final_answer = self.reasoner.generate_response(state[
                    'user_query'], context, tools_out)
                updates['final_answer'] = final_answer
        return updates

    def evaluate_node(self, state: GraphState) ->dict:
        if not state.get('final_answer'):
            return {'evaluation_score': 0.0}
        eval_result = self.evaluator.evaluate(state['user_query'], state.
            get('final_answer', ''), state.get('retrieved_docs', []))
        return {'evaluation_score': eval_result['score']}

    def should_continue(self, state: GraphState) ->str:
        score = state.get('evaluation_score', 0.0)
        retries = state.get('retry_count', 0)
        if score >= 0.7 or retries >= settings.MAX_RETRIES:
            return 'end'
        state['retry_count'] = retries + 1
        return 'continue'
