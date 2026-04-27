import sys
import os
import traceback
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from orchestrator.workflow import WorkflowGraph
    from tools.jira import JiraTools
    from loguru import logger
    from typing import Dict, Any
    app = FastAPI()
    workflow = WorkflowGraph()
    jira_tools = JiraTools()
except Exception as e:
    print(f'\nCRITICAL STARTUP ERROR: {e}', flush=True)
    traceback.print_exc()
    sys.exit(1)
except BaseException as e:
    print(f'\nSYSTEM ERROR DURING STARTUP: {e}', flush=True)
    traceback.print_exc()
    sys.exit(1)


class QueryRequest(BaseModel):
    query: str


class PriorityUpdateRequest(BaseModel):
    issue_key: str
    priority_id: str


@app.post('/query')
async def process_query(request: QueryRequest):
    logger.info(f'Received query: {request.query}')
    try:
        result = workflow.run(request.query)
        logger.info(f'Workflow Result Keys: {result.keys()}')
        return {'final_answer': result.get('final_answer') or
            'No answer generated.', 'reasoning_steps': result.get(
            'reasoning_steps') or ['Starting analysis...'],
            'evaluation_score': result.get('evaluation_score') or 0.0,
            'retrieved_docs': result.get('retrieved_docs') or [],
            'tool_outputs': result.get('tool_outputs') or []}
    except Exception as e:
        logger.exception('Final error in process_query')
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/jira/issue/{issue_key}')
async def get_jira_issue(issue_key: str) ->Dict[str, Any]:
    try:
        return jira_tools.get_issue(issue_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put('/jira/issue/priority')
async def update_jira_priority(request: PriorityUpdateRequest) ->Dict[str, Any
    ]:
    try:
        return jira_tools.update_issue_priority(request.issue_key, request.
            priority_id)
    except Exception as e:
        logger.error(f'Error updating priority: {e}')
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
