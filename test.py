import weaviate
import json

client = weaviate.Client("http://localhost:8080")

# Test ExamChunk specifically for physics
print("\n" + "="*60)
print("Testing ExamChunk with Physics filter")
print("="*60)

result = client.query.get(
    "ExamChunk",
    ["text", "subject", "field", "year", "session", "language", "content"]
).with_where({
    "path": ["subject"],
    "operator": "Equal",
    "valueText": "physics"
}).with_limit(3).do()

if result.get('data', {}).get('Get', {}).get('ExamChunk'):
    for i, doc in enumerate(result['data']['Get']['ExamChunk'], 1):
        print(f"\n--- Document {i} ---")
        print(f"Subject: {doc.get('subject')}")
        print(f"Field: {doc.get('field')}")
        print(f"Year: {doc.get('year')}")
        print(f"Session: {doc.get('session')}")
        print(f"Language: {doc.get('language')}")
        print(f"Content: {doc.get('content', doc.get('text', ''))[:300]}...")