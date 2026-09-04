import json
import time
from typing import Generator
from config.settings import settings
from loguru import logger
from huggingface_hub import InferenceClient
from langsmith import traceable

class Reasoner:

    def __init__(self):
        self.client = InferenceClient(token=settings.HF_TOKEN)

    @traceable(name='HF_Chat_Inference')
    def _query_api(self, messages: list, max_tokens: int=500) -> str:
        last_error = ''
        for attempt in range(3):
            try:
                logger.info(f'[Reasoner] chat_completion attempt {attempt + 1}: {settings.MODEL_NAME}')
                response = self.client.chat_completion(messages=messages, model=settings.MODEL_NAME, max_tokens=max_tokens, temperature=0.1)
                return response.choices[0].message.content
            except Exception as e:
                last_error = str(e)
                if '503' in last_error or 'Model loading' in last_error:
                    wait = 15 * (attempt + 1)
                    logger.warning(f'[Reasoner] Model loading, waiting {wait}s...')
                    time.sleep(wait)
                    continue
                wait = 2 ** attempt
                logger.warning(f'[Reasoner] API error on attempt {attempt + 1}: {e}. Retrying in {wait}s...')
                time.sleep(wait)
        logger.error(f'[Reasoner] All retries exhausted. Last error: {last_error}')
        return f'Error: {last_error}'

    @traceable(name='HF_Token_Streaming')
    def stream_tokens(self, messages: list, max_tokens: int=800) -> Generator[str, None, None]:
        try:
            logger.info(f'[Reasoner] stream_tokens: {settings.MODEL_NAME}')
            for chunk in self.client.chat_completion(messages=messages, model=settings.MODEL_NAME, max_tokens=max_tokens, temperature=0.1, stream=True):
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.warning(f'[Reasoner] Streaming failed: {e}. Falling back to normal generation.')
            full = self._query_api(messages, max_tokens)
            yield full

    @traceable(name='Generate_Plan')
    def generate_plan(self, query: str) -> dict:
        messages = [{'role': 'system', 'content': 'You are a CRM planner. Output ONLY JSON.'}, {'role': 'user', 'content': f"""Given the query: '{query}', create a JSON plan with a list of steps from [retrieve, analyze, tool_call, respond].\nOutput format: {{"steps": [...]}}"""}]
        result = self._query_api(messages, max_tokens=150)
        if 'Error:' in result or not result:
            return {'steps': ['retrieve', 'respond']}
        try:
            start = result.find('{')
            end = result.rfind('}') + 1
            return json.loads(result[start:end])
        except Exception:
            return {'steps': ['retrieve', 'respond']}

    @traceable(name='Generate_Final_Response')
    def generate_response(self, query: str, context: str, tools: str) -> str:
        messages = [{'role': 'system', 'content': 'You are a Customer Support Expert. Use the provided Context and Tool results to give a DIRECT, concise answer.'}, {'role': 'user', 'content': f'Context Knowledge Base:\n{context}\n\nTool Results:\n{tools}\n\nUser Question: {query}'}]
        return self._query_api(messages, max_tokens=400)
