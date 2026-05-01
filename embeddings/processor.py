#!/usr/bin/env python3
"""
Simplified Adaptive RAG Processor for single-file processing
Processes: semantic_chunks_balanced.json → Metadata → Embedding → Weaviate
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# Add src to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import your custom modules
from embeddings.embedder import MiniLMEmbedder
from embeddings.indexer_weaviate import index_to_weaviate


class SimpleRAGProcessor:
    """
    Simplified processor for your single-file structure.
    """

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.chunked_file = self.base_dir /"PythonProject"/"data"/ "semantic_chunks_balanced.json"
        self.weaviate_class = "ExamChunk"
        self.embedder = None

        self.stats = {
            'total_chunks': 0,
            'processed_chunks': 0,
            'start_time': None,
            'end_time': None
        }

    def _check_prerequisites(self) -> bool:
        """Check if the chunked file exists."""
        print("🔍 Checking prerequisites...")

        if not self.chunked_file.exists():
            print(f"❌ Chunked file not found: {self.chunked_file}")
            print("Please make sure semantic_chunks_balanced.json is in your project root")
            return False

        # Check Weaviate connection
        try:
            from embeddings.indexer_weaviate import index_to_weaviate
            print("✅ Weaviate module available")
        except ImportError as e:
            print(f"❌ Weaviate module error: {e}")
            return False

        print("✅ All prerequisites met")
        return True

    def extract_metadata(self, chunks: List[Dict]) -> List[Dict]:
        """
        Extract multilingual metadata directly from your existing chunks.
        Uses file_name and chunk_text to determine subject, year, etc.
        """
        print("\n" + "=" * 50)
        print("🔄 STEP 1: METADATA EXTRACTION")
        print("=" * 50)

        from data.metadata_extractor import extract_metadata_from_text

        enriched_chunks = []

        for chunk in chunks:
            # Combine file_name and chunk_text for metadata extraction
            combined_text = f"{chunk['file_name']} {chunk['chunk_text']}"

            # Extract metadata
            metadata = extract_metadata_from_text(combined_text)

            # Create enriched chunk
            enriched_chunks.append({
                'text': chunk['chunk_text'],
                'metadata': metadata
            })

        self.stats['total_chunks'] = len(enriched_chunks)
        print(f"✅ Metadata extraction complete: {len(enriched_chunks)} chunks enriched")

        return enriched_chunks

    def embed_chunks(self, enriched_chunks: List[Dict]) -> List[Dict]:
        """
        Embed all chunks using MiniLM model.
        """
        print("\n" + "=" * 50)
        print("🔄 STEP 2: EMBEDDING CHUNKS")
        print("=" * 50)

        # Initialize embedder
        self.embedder = MiniLMEmbedder()

        print(f"🔮 Embedding {len(enriched_chunks)} chunks...")

        # Embed all chunks
        embedded_chunks = self.embedder.embed_enriched_chunks(enriched_chunks)

        self.stats['processed_chunks'] = len(embedded_chunks)
        print(f"✅ Embedding complete: {len(embedded_chunks)} chunks embedded")

        return embedded_chunks

    def index_to_weaviate(self, embedded_chunks: List[Dict]):
        """
        Index all embedded chunks to Weaviate.
        """
        print("\n" + "=" * 50)
        print("🔄 STEP 3: WEAVIATE INDEXING")
        print("=" * 50)

        print(f"📚 Indexing {len(embedded_chunks)} chunks to Weaviate...")

        # Index to Weaviate
        index_to_weaviate(embedded_chunks, self.weaviate_class)

        print(f"✅ Indexing complete: {len(embedded_chunks)} chunks indexed")

    def run_complete_pipeline(self):
        """
        Run the complete simplified pipeline.
        """
        print("🚀 STARTING SIMPLIFIED RAG PROCESSOR")
        print("=" * 60)

        self.stats['start_time'] = time.time()

        try:
            # Step 0: Check prerequisites
            if not self._check_prerequisites():
                return False

            # Step 1: Load your existing chunks
            print(f"📖 Loading chunks from: {self.chunked_file}")
            with open(self.chunked_file, 'r', encoding='utf-8') as f:
                existing_chunks = json.load(f)

            print(f"📊 Found {len(existing_chunks)} chunks to process")

            # Step 2: Extract metadata
            enriched_chunks = self.extract_metadata(existing_chunks)
            if not enriched_chunks:
                print("❌ Metadata extraction failed")
                return False

            # Step 3: Embed chunks
            embedded_chunks = self.embed_chunks(enriched_chunks)
            if not embedded_chunks:
                print("❌ Embedding failed")
                return False

            # Step 4: Index to Weaviate
            self.index_to_weaviate(embedded_chunks)

            # Final statistics
            self.stats['end_time'] = time.time()
            self._print_summary()

            return True

        except Exception as e:
            print(f"❌ Pipeline failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _print_summary(self):
        """Print a summary of the pipeline execution."""
        duration = self.stats['end_time'] - self.stats['start_time']

        print("\n" + "=" * 60)
        print("🎉 SIMPLIFIED RAG PIPELINE COMPLETE!")
        print("=" * 60)
        print(f"📊 Execution Summary:")
        print(f"   • Total chunks processed: {self.stats['total_chunks']}")
        print(f"   • Duration: {duration:.2f} seconds")
        print(f"   • Speed: {self.stats['total_chunks'] / duration:.2f} chunks/second")
        print("\n🔍 Next steps:")
        print("   1. Your data is now searchable in Weaviate")
        print("   2. Run: python src/app/query_test.py to verify")
        print("=" * 60)


def main():
    """Main entry point for the simple processor."""
    processor = SimpleRAGProcessor()

    success = processor.run_complete_pipeline()

    if success:
        print("\n✅ Pipeline completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Pipeline failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
