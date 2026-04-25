from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator.workflow import WorkflowGraph
from tools.jira import JiraTools
from loguru import logger
from typing import Dict, Any

app = FastAPI()
workflow = WorkflowGraph()
jira_tools = JiraTools()

class QueryRequest(BaseModel):
    query: str

class PriorityUpdateRequest(BaseModel):
    issue_key: str
    priority_id: str

@app.post("/query")
async def process_query(request: QueryRequest):
    logger.info(f"Received query: {request.query}")
    try:
        result = workflow.run(request.query)
        return result
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jira/issue/{issue_key}")
async def get_jira_issue(issue_key: str) -> Dict[str, Any]:
    try:
        return jira_tools.get_issue(issue_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/jira/issue/priority")
async def update_jira_priority(request: PriorityUpdateRequest) -> Dict[str, Any]:
    try:
        return jira_tools.update_issue_priority(request.issue_key, request.priority_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
