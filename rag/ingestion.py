from notion_client import Client
from config.settings import settings
from rag.retriever import Retriever
from loguru import logger
import uuid

class NotionIngestor:
    def __init__(self):
        self.notion = Client(auth=settings.notion_api_key)
        self.retriever = Retriever()

    def fetch_and_ingest(self, page_id: str):
        logger.info(f"Ingesting Notion page {page_id}")
        blocks = self.notion.blocks.children.list(block_id=page_id)
        
        docs = []
        metadatas = []
        ids = []
        
        for block in blocks.get('results', []):
            if block['type'] == 'paragraph' and block['paragraph']['rich_text']:
                text = " ".join([t['plain_text'] for t in block['paragraph']['rich_text']])
                docs.append(text)
                metadatas.append({"source": f"notion_{page_id}"})
                ids.append(str(uuid.uuid4()))
                
        if docs:
            self.retriever.add_docs(docs, metadatas, ids)
            logger.info(f"Ingested {len(docs)} chunks")
