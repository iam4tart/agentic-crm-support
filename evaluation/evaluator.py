from ragas.metrics import Faithfulness, AnswerRelevancy
from ragas import evaluate

# Initialize metric objects
faithfulness = Faithfulness()
answer_relevancy = AnswerRelevancy()
from datasets import Dataset
from loguru import logger
from typing import Dict

class Evaluator:
    def evaluate(self, query: str, response: str, context: list) -> Dict[str, float]:
        logger.info("Evaluating response using Ragas")
        
        data = {
            "question": [query],
            "answer": [response],
            "contexts": [context],
            "ground_truth": [""]
        }
        dataset = Dataset.from_dict(data)
        
        try:
            result = evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy],
            )
            score = (result.get("faithfulness", 0.0) + result.get("answer_relevancy", 0.0)) / 2.0
            return {
                "faithfulness": result.get("faithfulness", 0.0),
                "relevance": result.get("answer_relevancy", 0.0),
                "score": score
            }
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return {
                "faithfulness": 0.0,
                "relevance": 0.0,
                "score": 0.0
            }
