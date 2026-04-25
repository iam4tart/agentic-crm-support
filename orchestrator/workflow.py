from langgraph.graph import StateGraph, END
from orchestrator.state import GraphState
from agents.reasoning import Reasoner
from rag.retriever import Retriever
from tools.jira import JiraTools
from evaluation.evaluator import Evaluator
from config.settings import settings
from loguru import logger
import json

class WorkflowGraph:
    def __init__(self):
        self.reasoner = Reasoner()
        self.retriever = Retriever()
        self.jira = JiraTools()
        self.evaluator = Evaluator()
        
        self.workflow = StateGraph(GraphState)
        
        self.workflow.add_node("plan", self.plan_node)
        self.workflow.add_node("execute_steps", self.execute_steps_node)
        self.workflow.add_node("evaluate", self.evaluate_node)
        
        self.workflow.set_entry_point("plan")
        self.workflow.add_edge("plan", "execute_steps")
        self.workflow.add_edge("execute_steps", "evaluate")
        self.workflow.add_conditional_edges(
            "evaluate",
            self.should_continue,
            {
                "continue": "plan",
                "end": END
            }
        )
        
        self.app = self.workflow.compile()

    def plan_node(self, state: GraphState) -> dict:
        logger.info(f"Planning steps for query: {state['user_query']}")
        plan = self.reasoner.generate_plan(state["user_query"])
        return {"reasoning_steps": plan.get("steps", [])}

    def execute_steps_node(self, state: GraphState) -> dict:
        updates = {}
        retrieved_docs = list(state.get("retrieved_docs", []))
        tool_outputs = list(state.get("tool_outputs", []))
        
        for step in state["reasoning_steps"]:
            if step == "retrieve":
                docs = self.retriever.retrieve(state["user_query"])
                retrieved_docs.extend(docs)
                updates["retrieved_docs"] = retrieved_docs
                
            elif step == "tool_call":
                try:
                    issue_data = self.jira.get_issue("TEST-1")
                    tool_outputs.append({"type": "jira_get", "data": issue_data})
                except Exception as e:
                    tool_outputs.append({"type": "error", "message": str(e)})
                updates["tool_outputs"] = tool_outputs
                
            elif step == "respond":
                context = "\n".join(retrieved_docs)
                tools_out = json.dumps(tool_outputs)
                final_answer = self.reasoner.generate_response(state["user_query"], context, tools_out)
                updates["final_answer"] = final_answer
                
        return updates

    def evaluate_node(self, state: GraphState) -> dict:
        eval_result = self.evaluator.evaluate(
            state["user_query"], 
            state.get("final_answer", ""), 
            state.get("retrieved_docs", [])
        )
        return {"evaluation_score": eval_result["score"]}

    def should_continue(self, state: GraphState) -> str:
        score = state.get("evaluation_score", 0.0)
        retries = state.get("retry_count", 0)
        
        if score >= 0.7 or retries >= settings.max_retries:
            return "end"
        
        state["retry_count"] = retries + 1
        state["user_query"] = f"Refine the answer for: {state['user_query']}"
        return "continue"

    def run(self, query: str) -> GraphState:
        initial_state = {
            "user_query": query,
            "retrieved_docs": [],
            "reasoning_steps": [],
            "tool_outputs": [],
            "final_answer": "",
            "evaluation_score": 0.0,
            "retry_count": 0
        }
        return self.app.invoke(initial_state)
