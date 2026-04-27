import json
import time
from config.settings import settings
from loguru import logger
from huggingface_hub import InferenceClient
from langsmith import traceable


class Reasoner:

    def __init__(self):
        self.client = InferenceClient(token=settings.HF_TOKEN)

    @traceable(name="HF_Text_Inference")
    def _query_api(self, messages: list, max_tokens: int=500) ->str:
        # Convert messages to a single prompt string for text_generation stability
        prompt = ""
        for msg in messages:
            role = msg['role'].upper()
            content = msg['content']
            prompt += f"\n<|{role}|>\n{content}\n"
        prompt += "\n<|ASSISTANT|>\n"

        for _ in range(3):
            try:
                logger.info(f'Calling HF text_generation: {settings.MODEL_NAME}')
                response = self.client.text_generation(
                    prompt=prompt,
                    model=settings.MODEL_NAME,
                    max_new_tokens=max_tokens,
                    stop_sequences=["<|", "\n<|"],
                    temperature=0.1
                )
                return response
            except Exception as e:
                if '503' in str(e) or 'Model loading' in str(e):
                    logger.warning('Model loading, waiting 15s...')
                    time.sleep(15)
                    continue
                logger.error(f'HF API Error: {e}')
                return f'Error: {e}'
        return ''

    @traceable(name="Generate_Plan")
    def generate_plan(self, query: str) ->dict:
        messages = [{'role': 'system', 'content':
            'You are a CRM planner. Output ONLY JSON.'}, {'role': 'user',
            'content':
            f"""Given the query: '{query}', create a JSON plan with a list of steps from [retrieve, analyze, tool_call, respond]. 
Output format: {{"steps": [...]}}"""
            }]
        result = self._query_api(messages, max_tokens=150)
        if 'Error:' in result or not result:
            return {'steps': ['retrieve', 'respond']}
        try:
            start = result.find('{')
            end = result.rfind('}') + 1
            return json.loads(result[start:end])
        except:
            return {'steps': ['retrieve', 'respond']}

    @traceable(name="Generate_Final_Response")
    def generate_response(self, query: str, context: str, tools: str) ->str:
        messages = [{'role': 'system', 'content':
            'You are a Customer Support Expert. Use the provided Context and Tool results to give a DIRECT answer.'
            }, {'role': 'user', 'content':
            f'Context Knowledge Base:\n{context}\n\nTool Results:\n{tools}\n\nUser Question: {query}'
            }]
        return self._query_api(messages, max_tokens=800)
