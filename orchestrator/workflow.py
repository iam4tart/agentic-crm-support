from langgraph.graph import StateGraph, END
from orchestrator.state import GraphState
from orchestrator.nodes import WorkflowNodes


class WorkflowGraph:

    def __init__(self):
        self.nodes = WorkflowNodes()
        self.workflow = StateGraph(GraphState)
        self.workflow.add_node('plan', self.nodes.plan_node)
        self.workflow.add_node('execute_steps', self.nodes.execute_steps_node)
        self.workflow.add_node('evaluate', self.nodes.evaluate_node)
        self.workflow.set_entry_point('plan')
        self.workflow.add_edge('plan', 'execute_steps')
        self.workflow.add_edge('execute_steps', 'evaluate')
        self.workflow.add_conditional_edges('evaluate', self.nodes.
            should_continue, {'continue': 'plan', 'end': END})
        self.app = self.workflow.compile()

    def run(self, query: str) ->dict:
        initial_state = {'user_query': query, 'retrieved_docs': [],
            'reasoning_steps': [], 'tool_outputs': [], 'final_answer': '',
            'evaluation_score': 0.0, 'retry_count': 0}
        return self.app.invoke(initial_state)
