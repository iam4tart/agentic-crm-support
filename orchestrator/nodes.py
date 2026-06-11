import asyncio
import json
from loguru import logger
from orchestrator.state import GraphState
from agents.reasoning import Reasoner
from rag.retriever import Retriever
from evaluation.evaluator import Evaluator
from config.settings import settings
from tools.crm_router import CRMRouter, resolve_server
from utils.event_bus import event_bus
from langgraph.graph import END

def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

def _emit(state: GraphState, event_type: str, data: dict=None):
    sid = state.get('ws_session_id', '')
    if sid:
        event_bus.emit(sid, event_type, data or {})

class WorkflowNodes:

    def __init__(self):
        self.reasoner = Reasoner()
        self.retriever = Retriever()
        self.evaluator = Evaluator()

    def triage_node(self, state: GraphState) -> dict:
        query = state['user_query']
        logger.info(f'[Triage] Classifying intent for: {query[:80]}')
        messages = [{'role': 'system', 'content': 'You are a CRM triage agent. Classify the user\'s query into ONE category.\nCategories:\n  - billing: payment issues, invoice disputes, subscription, pricing\n  - technical: bugs, errors, API issues, system failures, login problems\n  - product: feature requests, UI feedback, enhancement suggestions\n  - escalate: urgent/critical issues, data loss, security, SLA breach\n  - general: general questions, how-to, documentation, policy\nOutput ONLY valid JSON: {"intent": "<category>", "confidence": 0.0-1.0, "reasoning": "<1 sentence>"}'}, {'role': 'user', 'content': f'Query: {query}'}]
        raw = self.reasoner._query_api(messages, max_tokens=120)
        intent = 'general'
        confidence = 0.5
        try:
            start = raw.find('{')
            end = raw.rfind('}') + 1
            parsed = json.loads(raw[start:end])
            intent = parsed.get('intent', 'general').lower()
            confidence = float(parsed.get('confidence', 0.5))
            reasoning = parsed.get('reasoning', '')
            logger.info(f'[Triage] Intent={intent} (conf={confidence:.2f}) — {reasoning}')
        except Exception as e:
            logger.warning(f"[Triage] LLM parse failed, defaulting to 'general': {e}")
        valid_intents = {'billing', 'technical', 'product', 'escalate', 'general'}
        if intent not in valid_intents:
            intent = 'general'
        crm_server = resolve_server(intent)
        _emit(state, 'intent_detected', {'intent': intent, 'confidence': confidence, 'crm_server': crm_server, 'crm_label': CRMRouter.label(crm_server)})
        return {'intent': intent, 'intent_confidence': confidence, 'crm_server': crm_server}

    def plan_node(self, state: GraphState) -> dict:
        intent = state.get('intent', 'general')
        query = state['user_query']
        logger.info(f'[Plan] Generating plan for intent={intent}, query={query[:60]}')
        intent_hints = {'billing': 'Focus on account lookups, billing records, and creating Jira tickets.', 'technical': 'Focus on RAG retrieval of technical docs and creating Jira bug tickets.', 'product': 'Focus on searching existing feature requests and creating Linear issues.', 'escalate': 'Create a high-priority Jira ticket immediately, then retrieve relevant docs.', 'general': 'Retrieve relevant documentation and provide a direct answer.'}
        hint = intent_hints.get(intent, '')
        messages = [{'role': 'system', 'content': f'You are a CRM planner. Intent: {intent}. {hint}\nOutput ONLY JSON with steps from: [retrieve, analyze, tool_call, respond].\nFormat: {{"steps": ["retrieve", "tool_call", "respond"]}}'}, {'role': 'user', 'content': f"Query: '{query}'"}]
        result = self.reasoner._query_api(messages, max_tokens=150)
        steps = ['retrieve', 'respond']
        if result and 'Error:' not in result:
            try:
                start = result.find('{')
                end = result.rfind('}') + 1
                parsed = json.loads(result[start:end])
                steps = parsed.get('steps', steps)
            except Exception:
                pass
        if 'respond' not in steps:
            steps.append('respond')
        if intent == 'escalate' and 'tool_call' not in steps:
            steps.insert(0, 'tool_call')
        logger.info(f'[Plan] Steps: {steps}')
        _emit(state, 'plan_ready', {'steps': steps, 'intent': intent})
        return {'reasoning_steps': steps}

    def execute_steps_node(self, state: GraphState) -> dict:
        intent = state.get('intent', 'general')
        query = state['user_query']
        crm_server = state.get('crm_server', 'jira')
        updates: dict = {}
        retrieved_docs = list(state.get('retrieved_docs', []))
        tool_outputs = list(state.get('tool_outputs', []))
        ticket_key = state.get('ticket_key', '')
        for raw_step in state.get('reasoning_steps', []):
            step = (raw_step.get('tool_call', '') if isinstance(raw_step, dict) else str(raw_step)).lower()
            _emit(state, 'step_start', {'step': step, 'crm_server': crm_server})
            logger.info(f'[Execute] Step: {step}')
            if 'retrieve' in step:
                logger.info('[Execute] RAG retrieval...')
                try:
                    docs = self.retriever.retrieve(query)
                    retrieved_docs.extend(docs)
                    updates['retrieved_docs'] = retrieved_docs
                    _emit(state, 'step_complete', {'step': 'retrieve', 'doc_count': len(docs)})
                except Exception as e:
                    logger.error(f'[Execute] Retrieval error: {e}')
                    tool_outputs.append({'type': 'error', 'step': 'retrieve', 'message': str(e)})
                    _emit(state, 'error', {'step': 'retrieve', 'message': str(e)})
            elif 'tool' in step or 'ticket' in step or 'jira' in step or ('crm' in step):
                try:
                    already_created = any((out.get('type') in ('crm_create', 'jira_create') for out in tool_outputs))
                    query_lower = query.lower()
                    wants_create = any((kw in query_lower for kw in ('create', 'open', 'file', 'raise', 'submit', 'ticket', 'issue', 'escalate', 'down'))) or intent == 'escalate'
                    wants_resolve = any((kw in query_lower for kw in ('resolve', 'close', 'done', 'fixed', 'complete')))
                    if wants_resolve and ticket_key:
                        _emit(state, 'tool_call', {'server': crm_server, 'tool': 'resolve_ticket', 'ticket_key': ticket_key})
                        result = _run_async(CRMRouter.resolve_ticket(intent, ticket_key))
                        tool_outputs.append({'type': 'crm_resolve', 'data': result})
                        _emit(state, 'tool_result', {'tool': 'resolve_ticket', 'result': result})
                    elif already_created:
                        logger.info('[Execute] CRM ticket already created — skipping duplicate')
                        if ticket_key:
                            _emit(state, 'tool_call', {'server': crm_server, 'tool': 'add_note', 'ticket_key': ticket_key})
                            result = _run_async(CRMRouter.add_note(intent, ticket_key, f'Follow-up: {query}'))
                            tool_outputs.append({'type': 'crm_note', 'data': result})
                    elif wants_create:
                        _emit(state, 'tool_call', {'server': crm_server, 'tool': 'create_ticket', 'intent': intent})
                        result = _run_async(CRMRouter.create_ticket(intent=intent, summary=f'Support Request: {query[:80]}', description=f'Automated ticket created for: {query}', priority='High' if intent == 'escalate' else 'Medium'))
                        new_key = result.get('key', '')
                        if new_key:
                            ticket_key = new_key
                            updates['ticket_key'] = ticket_key
                        tool_outputs.append({'type': 'crm_create', 'data': result})
                        _emit(state, 'tool_result', {'tool': 'create_ticket', 'result': result})
                    else:
                        _emit(state, 'tool_call', {'server': crm_server, 'tool': 'search_tickets', 'query': query[:50]})
                        results = _run_async(CRMRouter.search_tickets(intent, query[:50]))
                        tool_outputs.append({'type': 'crm_search', 'data': results})
                        _emit(state, 'tool_result', {'tool': 'search_tickets', 'count': len(results), 'results': results[:3]})
                except Exception as e:
                    logger.error(f'[Execute] CRM tool error: {e}')
                    tool_outputs.append({'type': 'error', 'step': 'tool_call', 'message': str(e)})
                    _emit(state, 'error', {'step': 'tool_call', 'message': str(e)})
                updates['tool_outputs'] = tool_outputs
            elif 'respond' in step:
                _emit(state, 'step_start', {'step': 'respond'})
                context = '\n'.join(retrieved_docs)
                tools_out = json.dumps(tool_outputs)
                streaming_mode = state.get('streaming_mode', 'steps')
                if streaming_mode == 'tokens':
                    final_answer = self._stream_tokens(state, query, context, tools_out)
                else:
                    final_answer = self.reasoner.generate_response(query, context, tools_out)
                updates['final_answer'] = final_answer
                _emit(state, 'step_complete', {'step': 'respond'})
        return updates

    def _stream_tokens(self, state: GraphState, query: str, context: str, tools_out: str) -> str:
        sid = state.get('ws_session_id', '')
        messages = [{'role': 'system', 'content': 'You are a Customer Support Expert. Use the provided Context and Tool results to give a DIRECT answer.'}, {'role': 'user', 'content': f'Context Knowledge Base:\n{context}\n\nTool Results:\n{tools_out}\n\nUser Question: {query}'}]
        accumulated = ''
        try:
            for token in self.reasoner.stream_tokens(messages, max_tokens=800):
                accumulated += token
                if sid:
                    event_bus.emit(sid, 'token', {'text': token})
            return accumulated
        except Exception as e:
            logger.warning(f'[Execute] Token streaming failed, falling back: {e}')
            return self.reasoner.generate_response(query, context, tools_out)

    def evaluate_node(self, state: GraphState) -> dict:
        if not state.get('final_answer'):
            _emit(state, 'evaluation_done', {'score': 0.0, 'retry': True})
            return {'evaluation_score': 0.0, 'retry_count': state.get('retry_count', 0) + 1}
        eval_result = self.evaluator.evaluate(state['user_query'], state.get('final_answer', ''), state.get('retrieved_docs', []))
        score = eval_result['score']
        retries = state.get('retry_count', 0) + 1
        will_retry = score < 0.7 and retries < settings.MAX_RETRIES
        _emit(state, 'evaluation_done', {'score': score, 'faithfulness': eval_result.get('faithfulness', 0.0), 'relevance': eval_result.get('relevance', 0.0), 'retry': will_retry})
        return {'evaluation_score': score, 'retry_count': retries}

    def should_continue(self, state: GraphState) -> str:
        score = state.get('evaluation_score', 0.0)
        retries = state.get('retry_count', 0)
        if score >= 0.7 or retries >= settings.MAX_RETRIES:
            logger.info(f'[Gate] Ending. Score={score:.2f}, Retries={retries}')
            _emit(state, 'done', {'final_answer': state.get('final_answer', ''), 'score': score, 'ticket_key': state.get('ticket_key', ''), 'crm_server': state.get('crm_server', '')})
            return 'end'
        logger.info(f'[Gate] Retrying. Score={score:.2f}, Retries={retries}')
        _emit(state, 'retry', {'score': score, 'retry_count': retries})
        return 'continue'
