import weaviate
import os
from dotenv import load_dotenv

load_dotenv()

def index_to_weaviate(chunks_with_embeddings: list, class_name="ExamChunk"):
    """
    Weaviate indexer compatible with Python client 3.26+
    """
    try:
        client = weaviate.Client(url="http://localhost:8080")

        # ✅ Check if class exists
        if not client.schema.exists(class_name):
            # Create schema for Weaviate
            class_obj = {
                "class": class_name,
                "vectorizer": "none",  # we provide our own embeddings
                "properties": [
                    {"name": "text", "dataType": ["text"]},
                    {"name": "subject", "dataType": ["string"]},
                    {"name": "year", "dataType": ["string"]},
                    {"name": "session", "dataType": ["string"]},
                    {"name": "section", "dataType": ["string"]},
                    {"name": "language", "dataType": ["string"]}
                ]
            }
            client.schema.create_class(class_obj)
            print(f"✅ Created schema class: {class_name}")
        else:
            print(f"✅ Schema class already exists: {class_name}")

        # Configure batch
        client.batch.configure(batch_size=100, timeout_retries=3)

        print(f"📚 Indexing {len(chunks_with_embeddings)} chunks to Weaviate...")

        # Insert chunks in batch
        with client.batch as batch:
            for i, item in enumerate(chunks_with_embeddings):
                meta = item.get("metadata", {})

                # Convert year to integer safely
                year_value = meta.get("year")
                try:
                    year_value = int(year_value)
                except (TypeError, ValueError):
                    year_value = 0  # default integer

                data_object = {
                    "text": item["text"],
                    "subject": meta.get("subject", "unknown"),
                    "year": year_value,
                    "session": meta.get("session", "unknown"),
                    "section": meta.get("section", "unknown"),
                    "language": meta.get("language", "unknown")
                }

                batch.add_data_object(
                    data_object=data_object,
                    class_name=class_name,
                    vector=item["embedding"]
                )

                # Optional progress
                if (i + 1) % 1000 == 0:
                    print(f"   ... indexed {i + 1} chunks")

        print(f"✅ Successfully indexed {len(chunks_with_embeddings)} chunks into Weaviate")

    except Exception as e:
        print(f"❌ Error indexing to Weaviate: {e}")
        raise

