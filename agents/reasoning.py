import json
import time
from config.settings import settings
from loguru import logger
from huggingface_hub import InferenceClient

class Reasoner:

    def __init__(self):
        self.client = InferenceClient(api_key=settings.HF_TOKEN)

    def _query_api(self, messages: list, max_tokens: int=500) ->str:
        for _ in range(3):
            try:
                logger.info(
                    f'Calling HF chat.completions: {settings.MODEL_NAME}')
                completion = self.client.chat.completions.create(model=settings.MODEL_NAME, messages=messages, max_tokens=max_tokens)
                return completion.choices[0].message.content
            except Exception as e:
                if '503' in str(e) or 'Model loading' in str(e):
                    logger.warning('Model loading, waiting 15s...')
                    time.sleep(15)
                    continue
                logger.error(f'HF API Error: {e}')
                return f'Error: {e}'
        return ''

    def generate_plan(self, query: str) ->dict:
        messages = [{'role': 'system', 'content':
            'You are a CRM planner. Output ONLY JSON.'}, {'role': 'user',
            'content':
            f"""Given the query: '{query}', create a JSON plan with a list of steps from [retrieve, analyze, tool_call, respond]. 
CRITICAL: If the user explicitly asks to 'create a ticket' or 'use a tool', you MUST include 'tool_call' in the steps. 
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

    def generate_response(self, query: str, context: str, tools: str) ->str:
        messages = [{'role': 'system', 'content':
            """You are a Customer Support Expert. Use the provided Context and Tool results to give a DIRECT answer. 
IMPORTANT: If a Jira ticket was successfully created (check Tool Results), just provide the Ticket Key and a brief summary. DO NOT give manual instructions on how to create a ticket if you already did it."""
            }, {'role': 'user', 'content':
            f"""Context Knowledge Base:
{context}

Tool Results:
{tools}

User Question: {query}"""
            }]
        return self._query_api(messages, max_tokens=800)
