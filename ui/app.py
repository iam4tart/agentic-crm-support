import gradio as gr
import requests
import json


def process_ticket(query):
    if not query:
        return 'Please enter a query.', '', '', '', '0.0/1.0'
    try:
        response = requests.post('http://localhost:8000/query', json={
            'query': query})
        if response.status_code == 200:
            data = response.json()
            final_answer = data.get('final_answer', '')
            reasoning = json.dumps(data.get('reasoning_steps', []), indent=2)
            docs = data.get('retrieved_docs', [])
            knowledge = '\n\n'.join([f'Chunk {i + 1}:\n{doc}' for i, doc in
                enumerate(docs)]) if docs else 'No relevant documents found.'
            tools = json.dumps(data.get('tool_outputs', []), indent=2)
            score = f"{data.get('evaluation_score', 0.0):.2f}/1.0"
            return final_answer, reasoning, knowledge, tools, score
        else:
            return f'Backend Error: {response.status_code}', '', '', '', '0.0'
    except Exception as e:
        return f'Connection Error: {str(e)}', '', '', '', '0.0'


theme = gr.themes.Default(primary_hue='blue', neutral_hue='slate', font=[gr
    .themes.GoogleFont('Inter'), 'ui-sans-serif', 'system-ui', 'sans-serif'])
css = """
.container { max-width: 1400px; margin: auto; padding-top: 20px; }
.header-text { color: #111827; font-weight: 600; margin-bottom: 2px; }
.sub-text { color: #4B5563; margin-bottom: 30px; }
.gr-box { border-radius: 8px; }
div[data-testid="example-btn"] { white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }
"""
with gr.Blocks(title='Support Ticket Resolution') as demo:
    with gr.Column(elem_classes='container'):
        gr.Markdown('# Support Ticket Resolution', elem_classes='header-text')
        gr.Markdown(
            'Autonomous Agentic Workflow integrating RAG, LangGraph Orchestration, and JIRA Automation.'
            , elem_classes='sub-text')
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown('### Input Panel')
                query_input = gr.Textbox(label='Customer Query',
                    placeholder=
                    'Enter the customer issue or request here...', lines=4)
                gr.Examples(examples=[[
                    'Need instructions to reset my API key.'], [
                    'What is the policy for account suspension?'], [
                    'I am unable to reset my API key, please create a Jira ticket to track this issue.'
                    ]], inputs=query_input, label='Sample Queries')
                submit_btn = gr.Button('Process Ticket', variant='primary')
                score_output = gr.Textbox(label=
                    'Agentic Self-Critique Score', interactive=False)
            with gr.Column(scale=2):
                gr.Markdown('### Execution Trace & Output')
                with gr.Tabs():
                    with gr.TabItem('Final Response'):
                        answer_output = gr.Markdown(
                            "Submit a query to see the agent's response.")
                    with gr.TabItem('Reasoning Plan'):
                        reasoning_output = gr.Code(language='json', label=
                            'LangGraph Steps')
                    with gr.TabItem('Retrieved Knowledge'):
                        knowledge_output = gr.Textbox(label=
                            'ChromaDB Cloud Context', lines=10, interactive
                            =False)
                    with gr.TabItem('Tool Invocations'):
                        tools_output = gr.Code(language='json', label=
                            'JIRA API Live Payloads')
    submit_btn.click(fn=process_ticket, inputs=query_input, outputs=[
        answer_output, reasoning_output, knowledge_output, tools_output,
        score_output])
if __name__ == '__main__':
    demo.launch(server_name='0.0.0.0', server_port=8501, share=False, theme
        =theme, css=css)
