import gradio as gr
import requests
import json
import uuid
import time
import threading
from typing import Generator, Tuple
try:
    import websocket as ws_client
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
API_BASE = 'http://localhost:8000'
WS_BASE = 'ws://localhost:8000'

def process_normal(query: str):
    if not query.strip():
        return ('Please enter a query.', '', '', '', '0.0/1.0', '', '')
    try:
        resp = requests.post(f'{API_BASE}/query', json={'query': query}, timeout=300)
        if resp.status_code == 200:
            data = resp.json()
            final_answer = data.get('final_answer', '')
            reasoning = json.dumps(data.get('reasoning_steps', []), indent=2)
            docs = data.get('retrieved_docs', [])
            knowledge = '\n\n'.join([f'Chunk {i + 1}:\n{doc}' for i, doc in enumerate(docs)]) if docs else 'No relevant documents found.'
            tools = json.dumps(data.get('tool_outputs', []), indent=2)
            score = f'{data.get('evaluation_score', 0.0):.2f}/1.0'
            intent = data.get('intent', 'general')
            crm_server = data.get('crm_server', 'jira')
            ticket_key = data.get('ticket_key', '')
            intent_md = _intent_badge(intent, crm_server, ticket_key)
            steps_log = 'Streaming disabled — switch to Streaming Mode for live steps.'
            return (final_answer, reasoning, knowledge, tools, score, intent_md, steps_log)
        else:
            return (f'Backend Error: {resp.status_code}', '', '', '', '0.0', '', '')
    except Exception as e:
        return (f'Connection Error: {str(e)}', '', '', '', '0.0', '', '')

def process_streaming(query: str, token_mode: bool) -> Generator:
    if not query.strip():
        yield ('Please enter a query.', '', '', '', '0.0/1.0', '', '')
        return
    if not WS_AVAILABLE:
        yield ('websocket-client not installed. Run: pip install websocket-client\nOr switch to Normal Mode.', '', '', '', '0.0', '', '')
        return
    session_id = str(uuid.uuid4())
    ws_url = f'{WS_BASE}/ws/{session_id}'
    streaming_mode = 'tokens' if token_mode else 'steps'
    state = {'answer': 'Waiting for agent...', 'reasoning': '', 'knowledge': '', 'tools': '', 'score': '—', 'intent_md': '', 'steps': [], 'token_buffer': ''}

    def _render_steps(steps: list) -> str:
        if not steps:
            return ''
        lines = []
        for s in steps:
            icon = '[Done]' if s.get('done') else '[Active]' if s.get('active') else '[Pending]'
            label = s.get('label', '')
            detail = f' — {s['detail']}' if s.get('detail') else ''
            lines.append(f'{icon} **{label}**{detail}')
        return '\n'.join(lines)
    try:
        conn = ws_client.create_connection(ws_url, timeout=30)
        conn.send(json.dumps({'query': query, 'streaming_mode': streaming_mode}))
        state['steps'] = []
        state['answer'] = 'Agent is processing...'
        yield (state['answer'], state['reasoning'], state['knowledge'], state['tools'], state['score'], state['intent_md'], _render_steps(state['steps']))
        while True:
            try:
                raw = conn.recv()
                if not raw:
                    break
                event = json.loads(raw)
            except Exception as e:
                state['answer'] = f'Stream error: {e}'
                yield (state['answer'], state['reasoning'], state['knowledge'], state['tools'], state['score'], state['intent_md'], _render_steps(state['steps']))
                break
            etype = event.get('type', '')
            data = event.get('data', {})
            if etype == 'intent_detected':
                state['intent_md'] = _intent_badge(data.get('intent', ''), data.get('crm_server', ''), '')
                state['answer'] = f'Intent detected: **{data.get('intent', '')}** ({data.get('confidence', 0):.0%} confidence)'
            elif etype == 'plan_ready':
                steps_list = data.get('steps', [])
                state['steps'] = [{'label': s, 'done': False, 'active': False} for s in steps_list]
                state['reasoning'] = json.dumps(steps_list, indent=2)
            elif etype == 'step_start':
                step_name = data.get('step', '')
                for s in state['steps']:
                    if s['label'] == step_name:
                        s['active'] = True
                        break
            elif etype == 'step_complete':
                step_name = data.get('step', '')
                for s in state['steps']:
                    if s['label'] == step_name:
                        s['done'] = True
                        s['active'] = False
                        if step_name == 'retrieve':
                            s['detail'] = f'{data.get('doc_count', 0)} docs'
                        break
            elif etype == 'tool_call':
                detail = f'Calling **{data.get('tool', '')}** on {data.get('server', '')}'
                state['steps'].append({'label': detail, 'done': False, 'active': True})
            elif etype == 'tool_result':
                for s in reversed(state['steps']):
                    if 'Calling' in s.get('label', '') and s.get('active'):
                        s['done'] = True
                        s['active'] = False
                        s['detail'] = f'key={data.get('result', {}).get('key', '')}'
                        break
                current_tools = json.loads(state['tools']) if state['tools'] else []
                current_tools.append(data.get('result', {}))
                state['tools'] = json.dumps(current_tools, indent=2)
            elif etype == 'token':
                state['token_buffer'] += data.get('text', '')
                state['answer'] = state['token_buffer']
            elif etype == 'evaluation_done':
                score = data.get('score', 0.0)
                state['score'] = f'{score:.2f}/1.0'
                if data.get('retry'):
                    state['steps'].append({'label': f'Retrying (score={score:.2f} < 0.70)', 'done': False, 'active': True})
            elif etype == 'retry':
                state['answer'] = f'Score {data.get('score', 0):.2f} — refining answer (retry {data.get('retry_count', '')})'
            elif etype == 'error':
                state['steps'].append({'label': f'Error in {data.get('step', '')}: {data.get('message', '')[:60]}', 'done': True, 'active': False})
            elif etype == 'done':
                final = data.get('final_answer', state.get('token_buffer', ''))
                state['answer'] = final or state['answer']
                ticket_key = data.get('ticket_key', '')
                crm_server = data.get('crm_server', '')
                state['intent_md'] = _intent_badge(state.get('_intent', ''), crm_server, ticket_key)
                for s in state['steps']:
                    if s.get('active'):
                        s['done'] = True
                        s['active'] = False
                yield (state['answer'], state['reasoning'], state['knowledge'], state['tools'], state['score'], state['intent_md'], _render_steps(state['steps']))
                break
            elif etype == 'fatal_error':
                state['answer'] = f'Fatal error: {data.get('message', 'Unknown error')}'
                yield (state['answer'], state['reasoning'], state['knowledge'], state['tools'], state['score'], state['intent_md'], _render_steps(state['steps']))
                break
            if etype not in ('token',):
                yield (state['answer'], state['reasoning'], state['knowledge'], state['tools'], state['score'], state['intent_md'], _render_steps(state['steps']))
            elif etype == 'token' and len(state['token_buffer']) % 20 == 0:
                yield (state['answer'], state['reasoning'], state['knowledge'], state['tools'], state['score'], state['intent_md'], _render_steps(state['steps']))
    except Exception as e:
        yield (f'WebSocket connection failed: {e}\n\nMake sure the API is running at {API_BASE}', '', '', '', '0.0', '', '')
    finally:
        try:
            conn.close()
        except Exception:
            pass

def dispatch(query: str, streaming_enabled: bool, token_mode: bool):
    if streaming_enabled:
        yield from process_streaming(query, token_mode)
    else:
        result = process_normal(query)
        yield result
CRM_ICONS = {'jira': '', 'linear': ''}
INTENT_COLORS = {'technical': '', 'billing': '', 'product': '', 'escalate': '', 'general': ''}

def _intent_badge(intent: str, crm_server: str, ticket_key: str) -> str:
    parts = []
    if intent:
        parts.append(f'**Intent:** `{intent}`')
    if crm_server:
        parts.append(f'**CRM:** `{crm_server}`')
    if ticket_key:
        parts.append(f'**Ticket:** `{ticket_key}`')
    return '  |  '.join(parts) if parts else ''
theme = gr.themes.Default(primary_hue='blue', neutral_hue='slate', font=[gr.themes.GoogleFont('Inter'), 'ui-sans-serif', 'system-ui', 'sans-serif'])
css = '\n.container { max-width: 1400px; margin: auto; padding-top: 20px; }\n.header-text { color: #111827; font-weight: 600; margin-bottom: 2px; }\n.sub-text { color: #4B5563; margin-bottom: 30px; }\n.gr-box { border-radius: 8px; }\n.streaming-badge { \n    background: linear-gradient(90deg, #3b82f6, #8b5cf6);\n    color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;\n}\ndiv[data-testid="example-btn"] { \n    white-space: nowrap !important; \n    overflow: hidden !important; \n    text-overflow: ellipsis !important; \n}\n'
with gr.Blocks(title='Agentic CRM Support', theme=theme, css=css) as demo:
    with gr.Column(elem_classes='container'):
        gr.Markdown('# Agentic CRM Support', elem_classes='header-text')
        gr.Markdown('**RAG** + **LangGraph** + **Multi-MCP CRM** (Jira · Linear)', elem_classes='sub-text')
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown('### Input Panel')
                with gr.Group():
                    streaming_toggle = gr.Checkbox(label='Enable Streaming Mode (WebSocket)', value=False, info='Live step-by-step agent feed via WebSocket')
                    token_mode_toggle = gr.Checkbox(label='Token Streaming (character-by-character LLM output)', value=False, info='Only active when Streaming Mode is on', interactive=True)
                query_input = gr.Textbox(label='Customer Query', placeholder='Enter the customer issue or request here...', lines=4)
                gr.Examples(examples=[['Need instructions to reset my API key.'], ['What is the policy for account suspension?'], ['I am unable to reset my API key, please create a Jira ticket to track this issue.'], ['I have a billing dispute on invoice #1234, create a support ticket.'], ['Request a new feature: dark mode for the dashboard.'], ['URGENT: Production is down, all users affected. Escalate immediately!']], inputs=query_input, label='Sample Queries')
                submit_btn = gr.Button('Process Ticket', variant='primary')
                score_output = gr.Textbox(label='Agentic Self-Critique Score', interactive=False)
                intent_output = gr.Markdown(label='Intent & CRM Routing', value='')
            with gr.Column(scale=2):
                gr.Markdown('### Execution Trace & Output')
                with gr.Tabs():
                    with gr.TabItem('Final Response'):
                        answer_output = gr.Markdown("Submit a query to see the agent's response.")
                    with gr.TabItem('Live Agent Steps'):
                        steps_output = gr.Markdown('Enable **Streaming Mode** and submit a query to see live steps.', label='Real-time step feed')
                    with gr.TabItem('Reasoning Plan'):
                        reasoning_output = gr.Code(language='json', label='LangGraph Steps')
                    with gr.TabItem('Retrieved Knowledge'):
                        knowledge_output = gr.Textbox(label='ChromaDB Context', lines=10, interactive=False)
                    with gr.TabItem('Tool Invocations'):
                        tools_output = gr.Code(language='json', label='MCP CRM Tool Payloads (Jira · Linear)')
    submit_btn.click(fn=dispatch, inputs=[query_input, streaming_toggle, token_mode_toggle], outputs=[answer_output, reasoning_output, knowledge_output, tools_output, score_output, intent_output, steps_output])
if __name__ == '__main__':
    demo.launch(server_name='0.0.0.0', server_port=7860, share=False)
