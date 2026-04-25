from transformers import pipeline
from config.settings import settings
import json

class Reasoner:
    def __init__(self):
        self.generator = pipeline("text-generation", model=settings.model_name, token=settings.hf_token)

    def generate_plan(self, query: str) -> dict:
        prompt = f"Given the query: '{query}', create a JSON plan with a list of steps from [retrieve, analyze, tool_call, respond]. Output ONLY JSON.\n{{\"steps\": ["
        result = self.generator(prompt, max_new_tokens=50, return_full_text=False)[0]['generated_text']
        try:
            return json.loads("{\"steps\": [" + result.split("]")[0] + "]}")
        except:
            return {"steps": ["retrieve", "respond"]}

    def generate_response(self, query: str, context: str, tools: str) -> str:
        prompt = f"Context: {context}\nTools Output: {tools}\nQuery: {query}\nResponse:"
        return self.generator(prompt, max_new_tokens=200, return_full_text=False)[0]['generated_text']
