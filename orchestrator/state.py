from typing import List, Dict, Any, TypedDict, Optional

class GraphState(TypedDict):
    user_query: str
    retrieved_docs: List[str]
    reasoning_steps: List[str]
    tool_outputs: List[Dict[str, Any]]
    final_answer: str
    evaluation_score: float
    retry_count: int
    intent: str
    intent_confidence: float
    ticket_key: str
    crm_server: str
    event_source: str
    ws_session_id: str
    streaming_mode: str
    start_time: float
    total_latency_ms: float
    retrieval_latency_ms: float
    llm_latency_ms: float
    mcp_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    failure_reason: str
