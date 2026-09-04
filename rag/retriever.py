import requests
import chromadb
from chromadb.config import Settings
from config.settings import settings
from typing import List
from loguru import logger
from huggingface_hub import InferenceClient
from langsmith import traceable

class Retriever:

    def __init__(self):
        self.client = InferenceClient(token=settings.HF_TOKEN)
        self.client_db = None
        if settings.CHROMA_API_KEY:
            try:
                logger.info('Attempting to connect to ChromaDB Cloud...')
                self.client_db = chromadb.HttpClient(host='https://api.trychroma.com', ssl=True, tenant=settings.CHROMA_TENANT, database=settings.CHROMA_DATABASE, headers={'X-Chroma-Token': settings.CHROMA_API_KEY}, settings=Settings(chroma_api_impl='chromadb.api.fastapi.FastAPI', anonymized_telemetry=False))
                self.client_db.heartbeat()
                logger.info('ChromaDB Cloud connected successfully.')
            except Exception as e:
                logger.error(f'ChromaDB Cloud connection failed: {e}. Falling back to local storage.')
                self.client_db = None
        if self.client_db is None:
            logger.warning('Using local PersistentClient.')
            self.client_db = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)
        self.collection = self.client_db.get_or_create_collection(name='crm_support')

    @traceable(name='Embedding_Generation')
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        try:
            url = f'https://router.huggingface.co/hf-inference/models/{settings.EMBEDDING_MODEL}'
            headers = {'Authorization': f'Bearer {settings.HF_TOKEN}'}
            resp = requests.post(url, headers=headers, json={'inputs': texts}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data and isinstance(data[0], list):
                    return data
                elif isinstance(data, list) and data and isinstance(data[0], (int, float)):
                    return [data]
            logger.warning(f'Router embedding returned status {resp.status_code}: {resp.text[:100]}')
            embeddings = self.client.feature_extraction(texts, model=settings.EMBEDDING_MODEL)
            if hasattr(embeddings, 'tolist'):
                return embeddings.tolist()
            return embeddings
        except Exception as e:
            logger.error(f'Embedding API Error: {e}')
            return [[0.0] * 1024] * len(texts)

    def add_docs(self, docs: List[str], metadatas: List[dict], ids: List[str]):
        embeddings = self._get_embeddings(docs)
        self.collection.add(embeddings=embeddings, documents=docs, metadatas=metadatas, ids=ids)

    @traceable(name='Chroma_Retrieval')
    def retrieve(self, query: str, top_k: int=3) -> List[str]:
        query_embedding = self._get_embeddings([query])
        results = self.collection.query(query_embeddings=query_embedding, n_results=top_k)
        if results['documents']:
            return results['documents'][0]
        return []
