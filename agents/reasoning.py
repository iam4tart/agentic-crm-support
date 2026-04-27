from transformers import pipeline
from config.settings import settings
import json

class Reasoner:
    def __init__(self):
        self.generator = pipeline(
            "text-generation", 
            model=settings.model_name, 
            token=settings.hf_token,
            device_map=None,  # Forces CPU if no GPU
        )

    def generate_plan(self, query: str) -> dict:
        prompt = f"<|im_start|>system\nYou are a CRM planner. Output ONLY JSON.<|im_end|>\n<|im_start|>user\nGiven the query: '{query}', create a JSON plan with a list of steps from [retrieve, analyze, tool_call, respond].\n<|im_end|>\n<|im_start|>assistant\n{{\"steps\": ["
        result = self.generator(prompt, max_new_tokens=50, return_full_text=False)[0]['generated_text']
        try:
            return json.loads("{\"steps\": [" + result.split("]")[0] + "]}")
        except:
            return {"steps": ["retrieve", "respond"]}

    def generate_response(self, query: str, context: str, tools: str) -> str:
        prompt = f"<|im_start|>system\nYou are a CRM support agent.<|im_end|>\n<|im_start|>user\nContext: {context}\nTools Output: {tools}\nQuery: {query}\n<|im_end|>\n<|im_start|>assistant\n"
        return self.generator(prompt, max_new_tokens=300, return_full_text=False)[0]['generated_text']
