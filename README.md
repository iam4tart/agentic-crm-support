I started with a sequential 100-row sample, but identified a data-skew issue where the agent only knew about Account Creation. I pivoted to a stratified sampling strategy across 27 intents and added a Relevance Grader to handle the synthetic placeholders in the Bitext dataset

Refined the system prompts to enforce Tool-Use Priority. I noticed the model was defaulting to conversational guidance (Knowledge Base) rather than executing functional logic. By restructuring the prompt hierarchy to prioritize tool-calling, I ensured the agent acts as an executor rather than just an information retriever


## 🧪 Test Scenarios

### 1. Identity Recall

**Input**
'''terminal
My name is Aarush
What is my name?
'''

**Execution**
'''terminal
--- LLM TRIAGE: categorized as Technical ---
--- RAG: Searching Technical Database ---
'''

**Output**
'''terminal
Hi Aarush, your name is Aarush. Feel free to reach out if you need any assistance or have any other questions.
'''

✅ **Result: Passed**

---

### 2. Technical RAG

**Input**
'''terminal
Details regarding my bloody free account
'''

**Execution**
'''terminal
--- LLM TRIAGE: categorized as Technical ---
--- RAG: Searching Technical Database ---
'''

**Output (truncated)**
'''terminal
I'm sorry to hear you're feeling frustrated. Thank you for bringing this up...
'''

✅ **Result: Passed**

