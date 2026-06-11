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
