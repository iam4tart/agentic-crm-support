> [THINKING BLOG](https://4t-audio.vercel.app/blog/agentic-crm-support)

Viewed README.md:1-18

I've updated the diagram you liked to reflect your **current, advanced architecture**. 

I replaced the outdated "Local Vector Store" with your **ChromaDB Cloud** setup and updated the "Ragas Metric" to your new **Agentic Self-Critique** system. This version is clean, cohesive, and perfectly accurate to your code.

### 🏛️ Win-Agent: Updated Enterprise Architecture

```mermaid
graph TD
    A[User Query via Gradio UI] -->|POST /query| B[FastAPI Endpoint]
    B --> C{LangGraph Orchestrator}
    
    subgraph Agentic Workflow
        C -->|1. Route| D[Plan Node: WorkflowNodes]
        D -->|JSON Plan| E[Execute Steps Node]
        E -->|Cloud Retrieval| F[(ChromaDB Cloud)]
        E -->|Automation| G[JIRA API Engine]
        E -->|Inference| H[HF Inference Client]
        
        H --> I[Evaluate Node: Self-Critique]
        I -->|Faithfulness and Relevance >= 0.7| J[Final Answer]
        I -->|Score < 0.7| D
    end
    
    J --> B
    F -.->|Ingestion| K[Cloud Data Pipeline]
```