import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger
sys.path.append('.')
from config.settings import settings
from orchestrator.workflow import WorkflowGraph, setup_crm_bridge
from utils.event_bus import event_bus
from utils.composio_bridge import get_composio_bridge
os.environ['LANGCHAIN_TRACING_V2'] = settings.LANGCHAIN_TRACING_V2
os.environ['LANGCHAIN_ENDPOINT'] = settings.LANGCHAIN_ENDPOINT
if settings.LANGCHAIN_API_KEY:
    os.environ['LANGCHAIN_API_KEY'] = settings.LANGCHAIN_API_KEY
os.environ['LANGCHAIN_PROJECT'] = settings.LANGCHAIN_PROJECT

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('[API] Starting up — initializing CRM bridge...')
    await setup_crm_bridge()
    logger.info('[API] Ready.')
    yield
    logger.info('[API] Shutting down...')
    bridge = await get_composio_bridge()
    await bridge.shutdown()
    logger.info('[API] Goodbye.')
app = FastAPI(title='Agentic CRM Support API', description='Multi-MCP CRM support agent with WebSocket streaming and webhook orchestration.', version='2.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
workflow = WorkflowGraph()

class QueryRequest(BaseModel):
    query: str

class WebSocketMessage(BaseModel):
    query: str
    streaming_mode: str = 'steps'

@app.get('/')
async def health_check():
    return {'status': 'healthy', 'version': '2.0.0'}

@app.get('/health/mcp')
async def mcp_health():
    bridge = await get_composio_bridge()
    report = await bridge.health_report()
    return {'mode': bridge.mode, 'servers': bridge.registered_servers(), 'health': report}

@app.post('/query')
async def process_query(request: QueryRequest):
    try:
        logger.info(f'[API /query] {request.query[:80]}')
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, workflow.run, request.query)
        logger.info(f'[API /query] Result keys: {list(result.keys())}')
        return {'final_answer': result.get('final_answer', ''), 'reasoning_steps': result.get('reasoning_steps', []), 'retrieved_docs': result.get('retrieved_docs', []), 'tool_outputs': result.get('tool_outputs', []), 'evaluation_score': result.get('evaluation_score', 0.0), 'intent': result.get('intent', 'general'), 'crm_server': result.get('crm_server', 'jira'), 'ticket_key': result.get('ticket_key', '')}
    except Exception as e:
        logger.error(f'[API /query] Error: {e}')
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket('/ws/{session_id}')
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()
    logger.info(f'[WS] Client connected: {session_id}')
    try:
        raw = await asyncio.wait_for(ws.receive_json(), timeout=30.0)
        query = raw.get('query', '')
        streaming_mode = raw.get('streaming_mode', 'steps')
        if not query:
            await ws.send_json({'type': 'fatal_error', 'data': {'message': 'Empty query'}})
            await ws.close()
            return
        asyncio.create_task(workflow.run_streaming(query, session_id, 'ui', streaming_mode))
        async for event in event_bus.stream(session_id):
            await ws.send_json(event)
            if event['type'] in ('done', 'fatal_error'):
                break
    except asyncio.TimeoutError:
        logger.warning(f'[WS] Timeout waiting for message from {session_id}')
        await ws.send_json({'type': 'fatal_error', 'data': {'message': 'Connection timeout'}})
    except WebSocketDisconnect:
        logger.info(f'[WS] Client disconnected: {session_id}')
    except Exception as e:
        logger.error(f'[WS] Error for session {session_id}: {e}')
        try:
            await ws.send_json({'type': 'fatal_error', 'data': {'message': str(e)}})
        except Exception:
            pass
    finally:
        await event_bus.close(session_id)
        logger.info(f'[WS] Session closed: {session_id}')

@app.get('/stream/{session_id}')
async def sse_stream(session_id: str):

    async def generate():
        async for event in event_bus.stream(session_id):
            yield f'data: {json.dumps(event)}\n\n'
            if event['type'] in ('done', 'fatal_error'):
                break
    return StreamingResponse(generate(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.post('/webhook/jira')
async def jira_webhook(payload: dict, background: BackgroundTasks):
    webhook_event = payload.get('webhookEvent', 'unknown')
    issue_key = payload.get('issue', {}).get('key', 'UNKNOWN')
    changelog = payload.get('changelog', {})
    session_id = f'webhook-{issue_key}-{int(time.time())}'
    logger.info(f"[Webhook] Jira event '{webhook_event}' for {issue_key} → session {session_id}")
    trigger_query = f"Jira issue {issue_key} triggered event '{webhook_event}'. Changelog: {json.dumps(changelog)[:200]}. Analyze this update and determine if any follow-up actions are needed."
    background.add_task(asyncio.run, workflow.run_streaming(trigger_query, session_id, 'webhook', 'steps'))
    return {'status': 'accepted', 'session_id': session_id, 'issue_key': issue_key, 'event': webhook_event, 'stream_url': f'/stream/{session_id}'}
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
