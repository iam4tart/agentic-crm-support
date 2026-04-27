from loguru import logger
from typing import Dict
from agents.reasoning import Reasoner
import json

class Evaluator:
    def __init__(self):
        self.reasoner = Reasoner()

    def evaluate(self, query: str, response: str, context: list) -> Dict[str, float]:
        logger.info("Performing Agentic Self-Critique...")
        
        context_str = "\n".join(context)
        prompt = f"""
        Rate the following Customer Support Answer strictly.
        
        CRITERIA:
        1. Faithfulness: 1.0 if every fact is in the context. 0.0 if there is any hallucination.
        2. Relevance: 1.0 if it solves the user query perfectly. 0.0 if it is generic or unhelpful.

        Query: {query}
        Context: {context_str}
        Answer: {response}

        Output ONLY JSON in this format: {{"faithfulness": 0.0, "relevance": 0.0}}
        """
        
        critique_raw = self.reasoner._query_api([{"role": "user", "content": prompt}], max_tokens=100)
        
        try:
            start = critique_raw.find("{")
            end = critique_raw.rfind("}") + 1
            scores = json.loads(critique_raw[start:end])
            f_score = float(scores.get("faithfulness", 0.5))
            r_score = float(scores.get("relevance", 0.5))
            
            if len(response) < 50:
                f_score = min(f_score, 0.6)
                r_score = min(r_score, 0.6)

            return {
                "faithfulness": f_score,
                "relevance": r_score,
                "score": (f_score + r_score) / 2
            }
        except Exception as e:
            logger.error(f"Evaluation parsing error: {e}")
            return {"faithfulness": 0.4, "relevance": 0.4, "score": 0.4}
        
