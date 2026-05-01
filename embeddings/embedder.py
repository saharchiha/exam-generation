import json
import re
import os
from typing import List, Dict
from sentence_transformers import SentenceTransformer


class MiniLMEmbedder:
    """
    Embeds your existing chunked data and converts it to the format expected by the Weaviate indexer.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)
        print(f"✅ Loaded embedding model: {model_name}")

    def embed_chunks_file(self, input_file: str, output_file: str = None):
        """
        Takes your existing chunked JSON file and converts it to the format needed by Weaviate indexer.

        Args:
            input_file: Path to your existing semantic_chunks_balanced.json
            output_file: Optional path to save the embedded chunks
        """
        # Load your existing chunks
        with open(input_file, "r", encoding="utf-8") as f:
            existing_chunks = json.load(f)

        print(f"📖 Loaded {len(existing_chunks)} chunks from {input_file}")

        # Convert to Weaviate format and extract metadata
        weaviate_chunks = self._convert_to_weaviate_format(existing_chunks)

        # Embed all texts
        texts = [chunk["text"] for chunk in weaviate_chunks]
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True,
            normalize_embeddings=True
        )

        # Add embeddings to chunks
        for i, chunk in enumerate(weaviate_chunks):
            chunk["embedding"] = embeddings[i].tolist()

        print(f"✅ Embedded {len(weaviate_chunks)} chunks")

        # Save if output file specified
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(weaviate_chunks, f, ensure_ascii=False, indent=2)
            print(f"💾 Saved embedded chunks to: {output_file}")

        return weaviate_chunks

    def embed_enriched_chunks(self, enriched_chunks: List[Dict]) -> List[Dict]:
        """
        NEW METHOD: Takes enriched chunks (with metadata) and adds embedding vectors to each.

        Args:
            enriched_chunks: List of dicts with 'text' and 'metadata' keys

        Returns:
            List of dicts with added 'embedding' key containing the vector
        """
        # Extract just the text for embedding
        texts = [chunk["text"] for chunk in enriched_chunks]

        # Generate embeddings for all texts
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True,
            normalize_embeddings=True
        )

        # Add embeddings back to the enriched chunks
        for i, chunk in enumerate(enriched_chunks):
            chunk["embedding"] = embeddings[i].tolist()

        print(f"✅ Added embeddings to {len(enriched_chunks)} enriched chunks")
        return enriched_chunks

    def _convert_to_weaviate_format(self, existing_chunks: List[Dict]) -> List[Dict]:
        """
        Converts your existing chunk format to the format expected by Weaviate indexer.

        Your format: {"file_name", "file_path", "chunk_id", "chunk_text"}
        Weaviate format: {"text", "metadata": {"subject", "year", "session", "section", "language"}}
        """
        weaviate_chunks = []

        for chunk in existing_chunks:
            # Extract metadata from file_name and chunk_text
            metadata = self._extract_metadata_from_chunk(chunk)

            weaviate_chunks.append({
                "text": chunk["chunk_text"],  # Your actual chunk content
                "metadata": metadata
            })

        return weaviate_chunks

    def _extract_metadata_from_chunk(self, chunk: Dict) -> Dict:
        """
        Extracts metadata from your existing chunk data.
        Uses file_name and chunk_text to determine subject, year, etc.
        """
        file_name = chunk["file_name"]
        chunk_text = chunk["chunk_text"]

        # Initialize metadata
        metadata = {
            "subject": "unknown",
            "year": "unknown",
            "session": "unknown",
            "section": "unknown",
            "language": "unknown"
        }

        # --- Extract from file_name ---
        # Example: "math_2024_main_sciences.txt" → Math, 2024, Main, Sciences
        file_lower = file_name.lower()

        # Year detection
        import re
        year_match = re.search(r"\b(20\d{2})\b", file_name)
        if year_match:
            metadata["year"] = year_match.group(1)

        # Subject detection from file_name
        subject_map = {
            "math": "Mathematics", "mathematiques": "Mathematics", "رياضيات": "Mathematics",
            "physics": "Physics", "physique": "Physics", "فيزياء": "Physics",
            "chemistry": "Chemistry", "chimie": "Chemistry", "كيمياء": "Chemistry",
            "biology": "Biology", "biologie": "Biology", "علوم": "Biology",
            "philosophy": "Philosophy", "philosophie": "Philosophy", "فلسفة": "Philosophy",
            "history": "History", "histoire": "History", "تاريخ": "History",
            "geography": "Geography", "géographie": "Geography", "جغرافيا": "Geography"
        }

        for key, value in subject_map.items():
            if key in file_lower:
                metadata["subject"] = value
                break

        # Session detection
        if "main" in file_lower or "principale" in file_lower or "رئيسية" in file_lower:
            metadata["session"] = "Main"
        elif "retake" in file_lower or "controle" in file_lower or "مراقبة" in file_lower:
            metadata["session"] = "Retake"

        # Section detection
        if "sciences" in file_lower or "علمي" in file_lower:
            metadata["section"] = "Sciences Expérimentales"
        elif "math" in file_lower or "رياضيات" in file_lower:
            metadata["section"] = "Mathématiques"
        elif "lettres" in file_lower or "آداب" in file_lower:
            metadata["section"] = "Lettres"
        elif "economie" in file_lower or "اقتصاد" in file_lower:
            metadata["section"] = "Économie et Gestion"

        # --- Language detection from chunk_text ---
        if re.search(r"[\u0600-\u06FF]", chunk_text):  # Arabic characters
            metadata["language"] = "Arabic"
        elif re.search(r"[éèàùç]", chunk_text):  # French accents
            metadata["language"] = "French"
        else:
            metadata["language"] = "English"

        return metadata

    def embed_single_query(self, query: str) -> List[float]:
        """
        Embed a single query for semantic search.
        """
        embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embedding[0].tolist()
