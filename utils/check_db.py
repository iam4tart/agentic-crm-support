import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
tech_coll = client.get_collection("kb_technical")

results = tech_coll.get(limit=5, offset=70)

print(f"--- Total documents in Tech Collection: {tech_coll.count()} ---")
for i, doc in enumerate(results['documents']):
    print(f"\nDocument {i+1}:")
    print(doc[:100] + "...")