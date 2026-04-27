import chromadb
from config.settings import settings
from typing import List
from loguru import logger
from huggingface_hub import InferenceClient
from langsmith import traceable


class Retriever:

    def __init__(self):
        self.client = InferenceClient(token=settings.HF_TOKEN)
        if settings.CHROMA_API_KEY:
            self.client_db = chromadb.HttpClient(host=
                'https://api.trychroma.com', tenant=settings.CHROMA_TENANT,
                database=settings.CHROMA_DATABASE, headers={
                'X-Chroma-Token': settings.CHROMA_API_KEY})
        else:
            self.client_db = chromadb.PersistentClient(path=settings.
                CHROMA_DB_DIR)
        self.collection = self.client_db.get_or_create_collection(name=
            'crm_support')

    @traceable(name="Embedding_Generation")
    def _get_embeddings(self, texts: List[str]) ->List[List[float]]:
        try:
            embeddings = self.client.feature_extraction(texts, model=
                settings.EMBEDDING_MODEL)
            if hasattr(embeddings, 'tolist'):
                return embeddings.tolist()
            return embeddings
        except Exception as e:
            logger.error(f'Embedding API Error: {e}')
            return [[0.0] * 1024] * len(texts)

    def add_docs(self, docs: List[str], metadatas: List[dict], ids: List[str]):
        embeddings = self._get_embeddings(docs)
        self.collection.add(embeddings=embeddings, documents=docs,
            metadatas=metadatas, ids=ids)

    @traceable(name="Chroma_Retrieval")
    def retrieve(self, query: str, top_k: int=3) ->List[str]:
        query_embedding = self._get_embeddings([query])
        results = self.collection.query(query_embeddings=query_embedding,
            n_results=top_k)
        if results['documents']:
            return results['documents'][0]
        return []
