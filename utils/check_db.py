import chromadb
from sentence_transformers import SentenceTransformer


class DatabaseChecker:

    def __init__(self):
        self.client = chromadb.PersistentClient(path='./chroma_db')
        self.collection = self.client.get_collection(name='crm_support')
        self.model = SentenceTransformer('BAAI/bge-large-en-v1.5')

    def print_stats(self):
        count = self.collection.count()
        print(f'Total documents: {count}\n')
        if count > 0:
            sample = self.collection.peek(limit=5)
            print('Sample Documents:')
            for doc in sample.get('documents', []):
                print('-' * 40)
                print(doc)
            print('\n' + '=' * 40 + '\n')
            print('Metadata Preview:')
            for meta in sample.get('metadatas', []):
                print('-' * 40)
                print(meta)
            print('\n' + '=' * 40 + '\n')

    def query_db(self, query: str):
        print(f'Querying: {query}')
        embedding = self.model.encode([query]).tolist()
        results = self.collection.query(query_embeddings=embedding,
            n_results=3, include=['documents', 'metadatas', 'distances'])
        for i in range(len(results['documents'][0])):
            doc = results['documents'][0][i]
            meta = results['metadatas'][0][i]
            dist = results['distances'][0][i]
            print(f'\nResult {i + 1} (Distance: {dist:.4f})')
            print(f'Metadata: {meta}')
            print(f'Content:\n{doc}')

    def run(self):
        self.print_stats()
        while True:
            try:
                user_query = input("Enter query (or 'quit' to exit): ")
                if user_query.lower() in ['quit', 'exit']:
                    break
                if user_query.strip():
                    self.query_db(user_query)
            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    try:
        checker = DatabaseChecker()
        checker.run()
    except Exception as e:
        print(f'Error accessing DB: {e}')
