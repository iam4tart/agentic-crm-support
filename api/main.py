from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
sys.path.append(".") 

from orchestrator.workflow import WorkflowGraph
from loguru import logger
from config.settings import settings

os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
if settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

app = FastAPI(title="Agentic CRM Support API")
workflow = WorkflowGraph()

class QueryRequest(BaseModel):
    query: str

@app.post("/query")
async def process_query(request: QueryRequest):
    try:
        logger.info(f"Received query: {request.query}")
        result = workflow.run(request.query)
        logger.info(f"Workflow Result Keys: {result.keys()}")
        
        return {
            "final_answer": result.get("final_answer", ""),
            "reasoning_steps": result.get("reasoning_steps", []),
            "retrieved_docs": result.get("retrieved_docs", []),
            "tool_outputs": result.get("tool_outputs", []),
            "evaluation_score": result.get("evaluation_score", 0.0)
        }
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
