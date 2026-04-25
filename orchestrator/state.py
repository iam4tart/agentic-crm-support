from typing import List, Dict, Any, TypedDict, Annotated
import operator

class GraphState(TypedDict):
    user_query: str
    retrieved_docs: List[str]
    reasoning_steps: List[str]
    tool_outputs: List[Dict[str, Any]]
    final_answer: str
    evaluation_score: float
    retry_count: int
