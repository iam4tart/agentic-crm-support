import chromadb
from sentence_transformers import SentenceTransformer
from config.settings import settings
from typing import List

class Retriever:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_db_dir)
        self.collection = self.client.get_or_create_collection(name="notion_docs")
        self.model = SentenceTransformer(settings.embedding_model)

    def add_docs(self, docs: List[str], metadatas: List[dict], ids: List[str]):
        embeddings = self.model.encode(docs).tolist()
        self.collection.add(
            embeddings=embeddings,
            documents=docs,
            metadatas=metadatas,
            ids=ids
        )

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        query_embedding = self.model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )
        if results['documents']:
            return results['documents'][0]
        return []
