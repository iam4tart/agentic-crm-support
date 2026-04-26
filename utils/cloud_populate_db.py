import os
import uuid
import pandas as pd
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
import torch
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings

class CloudDatabasePopulator:
    def __init__(self):
        self.data_dir = "data"
        if not settings.chroma_api_key:
            raise ValueError("CHROMA_API_KEY is not set.")
            
        self.client = chromadb.HttpClient(
            host="https://api.trychroma.com",
            tenant=settings.chroma_tenant,
            database=settings.chroma_database,
            headers={"X-Chroma-Token": settings.chroma_api_key}
        )
        self.collection = self.client.get_or_create_collection(name="crm_support")
        os.environ["HF_TOKEN"] = settings.hf_token
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer("BAAI/bge-large-en-v1.5", token=settings.hf_token, device=device)
        self.batch_size = 50

    def load_data(self):
        dataframes = []
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith(".csv"):
                    file_path = os.path.join(root, file)
                    try:
                        df = pd.read_csv(file_path)
                        df['source_dataset'] = file
                        dataframes.append(df)
                    except Exception:
                        pass
        return dataframes

    def normalize_row(self, row, source):
        row_dict = row.to_dict()
        title_candidates = ["title", "subject", "summary", "ticket_title"]
        issue_candidates = ["issue", "description", "body", "problem", "ticket_description"]
        category_candidates = ["category", "type", "topic"]
        priority_candidates = ["priority", "severity", "urgency"]
        resolution_candidates = ["resolution", "solution", "response", "reply"]

        def extract(candidates, default="Unknown"):
            for c in candidates:
                for k in row_dict.keys():
                    if c in str(k).lower():
                        val = row_dict[k]
                        return str(val).strip() if pd.notna(val) else default
            return default

        return {
            "title": extract(title_candidates, "No Title"),
            "issue": extract(issue_candidates, "No Issue Description"),
            "category": extract(category_candidates, "Uncategorized"),
            "priority": extract(priority_candidates, "Normal"),
            "resolution": extract(resolution_candidates, "No Resolution"),
            "source": source
        }

    def chunk_text(self, normalized_data):
        text = (
            f"Customer Issue:\n{normalized_data['issue']}\n\n"
            f"Category:\n{normalized_data['category']}\n\n"
            f"Priority:\n{normalized_data['priority']}\n\n"
            f"Resolution:\n{normalized_data['resolution']}"
        )
        words = text.split()
        chunk_size = 400
        overlap = 50
        chunks = []
        if len(words) <= chunk_size:
            chunks.append(text)
        else:
            for i in range(0, len(words), chunk_size - overlap):
                chunk = " ".join(words[i:i + chunk_size])
                chunks.append(chunk)
        return chunks

    def embed_and_store(self, records):
        docs = []
        metas = []
        ids = []
        seen_ids = set()

        for record in records:
            chunks = self.chunk_text(record)
            for i, chunk in enumerate(chunks):
                doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{record['source']}_{record['title']}_{i}_{hash(chunk)}"))
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    docs.append(chunk)
                    metas.append({
                        "title": record["title"],
                        "category": record["category"],
                        "priority": record["priority"],
                        "source": record["source"]
                    })
                    ids.append(doc_id)

        if not ids:
            return

        for i in range(0, len(docs), self.batch_size):
            b_docs = docs[i:i + self.batch_size]
            b_metas = metas[i:i + self.batch_size]
            b_ids = ids[i:i + self.batch_size]
            
            print(f"Uploading batch {i // self.batch_size + 1}/{(len(docs) + self.batch_size - 1) // self.batch_size}...")
            embeddings = self.model.encode(b_docs, show_progress_bar=True).tolist()
            self.collection.add(
                documents=b_docs,
                metadatas=b_metas,
                embeddings=embeddings,
                ids=b_ids
            )

    def run(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            return

        dataframes = self.load_data()
        all_normalized = []

        for df in dataframes:
            source = df['source_dataset'].iloc[0] if not df.empty else "unknown"
            for _, row in df.iterrows():
                all_normalized.append(self.normalize_row(row, source))

        self.embed_and_store(all_normalized)

if __name__ == "__main__":
    populator = CloudDatabasePopulator()
    populator.run()
