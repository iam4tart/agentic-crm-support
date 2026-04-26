from transformers import pipeline
from config.settings import settings
import json

class Reasoner:
    def __init__(self):
        self.generator = pipeline("text-generation", model=settings.model_name, token=settings.hf_token)

    def generate_plan(self, query: str) -> dict:
        prompt = f"<|user|>\nGiven the customer query: '{query}', create a JSON plan with a list of steps choosing from [retrieve, analyze, tool_call, respond]. Output ONLY raw JSON.\n<|end|>\n<|assistant|>\n{{\"steps\": ["
        result = self.generator(prompt, max_new_tokens=50, return_full_text=False)[0]['generated_text']
        try:
            return json.loads("{\"steps\": [" + result.split("]")[0] + "]}")
        except:
            return {"steps": ["retrieve", "respond"]}

    def generate_response(self, query: str, context: str, tools: str) -> str:
        prompt = f"<|user|>\nYou are a CRM support agent. Use the context and tools output to answer the query.\nContext: {context}\nTools Output: {tools}\nQuery: {query}\n<|end|>\n<|assistant|>\n"
        return self.generator(prompt, max_new_tokens=300, return_full_text=False)[0]['generated_text']
